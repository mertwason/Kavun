"""KVN-05: Trendyol adapter'i — kayıtlı yanıtlara karşı test (CLAUDE.md §3).

Canlı API'ye ÇIKILMAZ: tüm istekler `httpx.MockTransport` ile karşılanır ve fixture
dosyalarından beslenir.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.connectors import trendyol
from app.connectors.base import AuthenticationError, ConnectorError, RateLimitError
from app.connectors.http import ApiClient, RetryPolicy, parse_json
from app.connectors.trendyol import TrendyolConnector
from app.models.enums import OrderStatus

FIXTURES = Path(__file__).parent / "fixtures" / "trendyol"


def load_fixture(name: str) -> dict[str, Any]:
    """Fixture dosyasını okur."""
    body: dict[str, Any] = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    return body


def make_connector(handler: Any, **kwargs: Any) -> TrendyolConnector:
    """Sahte taşıma katmanına bağlı adapter."""
    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(
        base_url=trendyol.PRODUCTION_BASE_URL,
        transport=transport,
        headers={"User-Agent": "998877 - SelfIntegration", "storeFrontCode": "TR"},
        auth=("key", "secret"),
    )
    client = ApiClient(
        trendyol.PRODUCTION_BASE_URL,
        headers={},
        client=http_client,
        requests_per_minute=60_000,
        **kwargs,
    )
    return TrendyolConnector("998877", "key", "secret", client=client)


# --- ayrıştırma (saf fonksiyonlar) ------------------------------------------


def test_order_parsing_matches_documented_fields() -> None:
    """Doğrulanmış alan adları normalize modele birebir taşınır."""
    raw = load_fixture("orders_page0")["content"][0]
    order = trendyol.parse_order(raw)

    assert order.external_order_id == "TY-2026-0001"
    assert order.status is OrderStatus.DELIVERED
    assert order.customer_city == "İstanbul"
    assert order.cargo_provider == "Trendyol Express"
    assert order.order_date == datetime(2026, 8, 16, 10, 0, tzinfo=UTC)
    assert len(order.lines) == 2
    # Ham payload olduğu gibi taşınır — raw_events'e bu yazılır (spec §3.2).
    assert order.payload["shipmentNumber"] == "1234567890"


def test_money_fields_are_decimal_not_float() -> None:
    """Tutarlar `Decimal` olarak taşınır (CLAUDE.md §1)."""
    raw = load_fixture("orders_page0")["content"][0]
    order = trendyol.parse_order(raw)

    assert isinstance(order.gross_total, Decimal)
    assert order.gross_total == Decimal("1078.00")
    line = order.lines[0]
    assert isinstance(line.unit_price, Decimal)
    assert (line.unit_price, line.line_amount, line.discount) == (
        Decimal("449.00"),
        Decimal("898.00"),
        Decimal("50.00"),
    )


def test_json_parsing_keeps_precision() -> None:
    """Gövde ayrıştırması ondalıkları `Decimal` yapar — float yuvarlaması olmaz."""
    parsed = parse_json('{"amount": 1078.15, "qty": 2}')
    assert parsed["amount"] == Decimal("1078.15")
    assert isinstance(parsed["amount"], Decimal)
    assert parsed["qty"] == 2


@pytest.mark.parametrize(
    ("raw_status", "expected"),
    [
        ("Awaiting", OrderStatus.CREATED),
        ("Created", OrderStatus.CREATED),
        ("Picking", OrderStatus.PICKING),
        ("Invoiced", OrderStatus.PICKING),
        ("Shipped", OrderStatus.SHIPPED),
        ("AtCollectionPoint", OrderStatus.SHIPPED),
        ("UnDelivered", OrderStatus.SHIPPED),
        ("Delivered", OrderStatus.DELIVERED),
        ("Cancelled", OrderStatus.CANCELLED),
        ("UnSupplied", OrderStatus.CANCELLED),
        ("Returned", OrderStatus.RETURNED),
    ],
)
def test_status_normalization(raw_status: str, expected: OrderStatus) -> None:
    """Dokümandaki her statü içeri enum'a eşlenir (spec §4)."""
    assert trendyol.normalize_status(raw_status) is expected


def test_unknown_status_falls_back_to_created() -> None:
    """Bilinmeyen statü veriyi düşürmez; en muhafazakâr duruma çekilir."""
    assert trendyol.normalize_status("YeniBirStatu") is OrderStatus.CREATED


def test_product_parsing_expands_variants() -> None:
    """V2 yanıtında barkod/fiyat/stok varyantta; her varyant ayrı ürün olur."""
    content = load_fixture("products_approved")["content"]
    products = [product for item in content for product in trendyol.parse_product(item)]

    assert len(products) == 3
    first = products[0]
    assert first.barcode == "8690584683940"
    assert first.seller_sku == "KHV-BLD-ESP"
    assert first.name == "Kahveji Espresso Blend"
    assert first.category == "Kahve/Harman"
    assert first.sale_price == Decimal("1190.00")
    assert first.stock == 110
    # KDV ve desi V2 onaylı-ürün yanıtında yok (TODO(verify) — bkz. modül docstring).
    assert first.vat_rate is None
    assert first.desi is None


def test_date_windows_respect_two_week_limit() -> None:
    """Tarih aralığı servis sınırına (iki hafta) göre bölünür."""
    since = datetime(2026, 1, 1, tzinfo=UTC)
    until = datetime(2026, 2, 5, tzinfo=UTC)
    windows = list(trendyol.date_windows(since, until))

    assert len(windows) == 3
    assert windows[0] == (since, datetime(2026, 1, 15, tzinfo=UTC))
    assert windows[-1][1] == until
    assert all((end - start) <= timedelta(days=14) for start, end in windows)


def test_date_windows_empty_for_inverted_range() -> None:
    """Ters aralık için pencere üretilmez."""
    now = datetime.now(UTC)
    assert list(trendyol.date_windows(now, now - timedelta(days=1))) == []


# --- HTTP davranışı ---------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_orders_consumes_all_pages() -> None:
    """Sayfalama tüketilir: iki sayfa, üç sipariş."""
    seen_params: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_params.append(dict(request.url.params))
        page = int(request.url.params.get("page", 0))
        return httpx.Response(200, json=load_fixture(f"orders_page{page}"))

    connector = make_connector(handler)
    orders = await connector.fetch_orders(
        datetime(2026, 8, 15, tzinfo=UTC), datetime(2026, 8, 18, tzinfo=UTC)
    )

    assert [order.external_order_id for order in orders] == [
        "TY-2026-0001",
        "TY-2026-0002",
        "TY-2026-0003",
    ]
    assert seen_params[0]["size"] == "200"
    assert seen_params[0]["orderByField"] == "PackageLastModifiedDate"
    assert "startDate" in seen_params[0] and "endDate" in seen_params[0]


@pytest.mark.asyncio
async def test_request_uses_documented_path_and_headers() -> None:
    """Uç yolu ve zorunlu `User-Agent` başlığı dokümanla birebir."""
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["user_agent"] = request.headers.get("user-agent")
        captured["storefront"] = request.headers.get("storefrontcode")
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"content": [], "totalPages": 0})

    connector = make_connector(handler)
    await connector.fetch_orders(
        datetime(2026, 8, 17, tzinfo=UTC), datetime(2026, 8, 18, tzinfo=UTC)
    )

    assert captured["path"] == "/integration/order/sellers/998877/orders"
    assert captured["user_agent"] == "998877 - SelfIntegration"
    assert captured["storefront"] == "TR"
    assert captured["auth"].startswith("Basic ")


@pytest.mark.asyncio
async def test_fetch_products_follows_next_page_token() -> None:
    """10.000 üstü için `nextPageToken` zinciri izlenir (V2)."""
    calls: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        calls.append(params)
        if "nextPageToken" not in params:
            body = load_fixture("products_approved")
            body["nextPageToken"] = "TOKEN-2"
            body["totalPages"] = 2
            return httpx.Response(200, json=body)
        body = load_fixture("products_approved")
        body["nextPageToken"] = None
        body["totalPages"] = 2
        return httpx.Response(200, json=body)

    connector = make_connector(handler)
    products = await connector.fetch_products()

    assert len(calls) == 2
    assert calls[0]["size"] == "100"
    assert calls[1]["nextPageToken"] == "TOKEN-2"
    assert len(products) == 6


@pytest.mark.asyncio
async def test_rate_limit_is_retried_then_succeeds() -> None:
    """429 sonrası yeniden denenir (spec §4: backoff + jitter)."""
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, json={"content": [], "totalPages": 0})

    connector = make_connector(handler, retry=RetryPolicy(max_attempts=3, base_delay=Decimal("0")))
    await connector.fetch_orders(
        datetime(2026, 8, 17, tzinfo=UTC), datetime(2026, 8, 18, tzinfo=UTC)
    )
    assert attempts["count"] == 2


@pytest.mark.asyncio
async def test_rate_limit_exhausted_raises() -> None:
    """Denemeler tükenince açık hata verilir, sessizce boş dönülmez."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "0"})

    connector = make_connector(handler, retry=RetryPolicy(max_attempts=2, base_delay=Decimal("0")))
    with pytest.raises(RateLimitError):
        await connector.fetch_orders(
            datetime(2026, 8, 17, tzinfo=UTC), datetime(2026, 8, 18, tzinfo=UTC)
        )


@pytest.mark.asyncio
async def test_server_error_is_retried() -> None:
    """5xx geçici sayılır ve yeniden denenir."""
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] < 3:
            return httpx.Response(503)
        return httpx.Response(200, json={"content": [], "totalPages": 0})

    connector = make_connector(handler, retry=RetryPolicy(max_attempts=4, base_delay=Decimal("0")))
    await connector.fetch_orders(
        datetime(2026, 8, 17, tzinfo=UTC), datetime(2026, 8, 18, tzinfo=UTC)
    )
    assert attempts["count"] == 3


@pytest.mark.asyncio
async def test_auth_failure_is_not_retried_and_hides_credentials() -> None:
    """401 yeniden denenmez; hata mesajı credential sızdırmaz (CLAUDE.md §2)."""
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        return httpx.Response(
            401, json={"errors": [{"message": "ClientApiAuthenticationException"}]}
        )

    connector = make_connector(handler)
    with pytest.raises(AuthenticationError) as exc_info:
        await connector.fetch_orders(
            datetime(2026, 8, 17, tzinfo=UTC), datetime(2026, 8, 18, tzinfo=UTC)
        )

    assert attempts["count"] == 1
    assert "secret" not in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_client_error_raises_connector_error() -> None:
    """4xx (400 vb.) kurtarılamaz hata olarak yükselir."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"errors": ["bad request"]})

    connector = make_connector(handler)
    with pytest.raises(ConnectorError):
        await connector.fetch_products()


@pytest.mark.asyncio
async def test_commission_service_absence_is_explicit() -> None:
    """Trendyol'da komisyon servisi yok: boş liste döner, uydurma oran üretilmez."""
    connector = make_connector(lambda request: httpx.Response(200, json={}))
    assert await connector.fetch_commission_rates() == []


@pytest.mark.asyncio
async def test_phase_two_endpoints_are_declared_not_faked() -> None:
    """Faz 2 uçları sahte veri döndürmez; açıkça uygulanmadığını söyler (spec §12.1)."""
    connector = make_connector(lambda request: httpx.Response(200, json={}))
    now = datetime.now(UTC)

    for coroutine in (
        connector.fetch_returns(now),
        connector.fetch_settlements(now),
        connector.fetch_cargo_invoices(now),
    ):
        with pytest.raises(NotImplementedError):
            await coroutine
