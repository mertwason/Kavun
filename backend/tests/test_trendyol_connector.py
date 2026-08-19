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
from app.models.enums import OrderStatus, SettlementRecordType

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
async def test_phase_two_endpoints_are_implemented_not_faked() -> None:
    """Faz 2 uçları artık gerçek servisi çağırıyor; sahte veri üretmiyor (KVN-EK-05).

    KVN-05'te bu test uçların `NotImplementedError` fırlattığını doğruluyordu — o dönemde
    doğru davranış buydu. Uçlar uygulandı; test yerini "boş yanıtta boş liste döner,
    uydurma kayıt üretmez" kontrolüne bıraktı.
    """
    connector = make_connector(
        lambda request: httpx.Response(200, json={"content": [], "totalPages": 0})
    )
    since = datetime(2026, 8, 1, tzinfo=UTC)
    until = datetime(2026, 8, 5, tzinfo=UTC)

    assert await connector.fetch_returns(since, until) == []
    assert await connector.fetch_settlements(since, until) == []
    assert await connector.fetch_cargo_invoices(since, until) == []


# --- Faz 2: iadeler, hakediş, kargo faturası (KVN-EK-05) ---------------------


def test_parse_claim_counts_quantity_from_claim_items() -> None:
    """Adet `claimItems` sayısından gelir; tutar birim fiyat × adettir."""
    claim = trendyol.parse_claim(load_fixture("claims_page0")["content"][0])

    assert claim.external_return_id == "CLM-90010001"
    assert claim.external_order_id == "TY-2026-000117"
    assert len(claim.lines) == 1
    line = claim.lines[0]
    assert line.quantity == 2
    assert line.refund_amount == Decimal("579.8000")
    assert line.seller_sku == "KHV-BLD-ESP-250"
    assert line.accepted is True


def test_rejected_claim_is_marked_not_accepted() -> None:
    """Reddedilen talep iade sayılmaz — kâr etkisi doğurmamalı."""
    claim = trendyol.parse_claim(load_fixture("claims_page0")["content"][1])

    assert [line.accepted for line in claim.lines] == [False]
    assert claim.lines[0].reason == "Hasarlı geldi"


def test_claim_carries_cargo_tracking_number() -> None:
    """İade gönderisinin takip numarası taşınır (kargo eşleştirmesi için)."""
    claim = trendyol.parse_claim(load_fixture("claims_page0")["content"][0])

    assert claim.cargo_tracking_no == "7300000000011"


def test_claim_without_items_yields_no_lines() -> None:
    """Kalemi olmayan talep satır üretmez (boş `claimItems`)."""
    assert trendyol.parse_claim_line({"orderLine": {"id": 1}, "claimItems": []}) == []


def test_partially_accepted_claim_splits_into_two_lines() -> None:
    """Aynı satırın kabul edilen ve edilmeyen adetleri ayrı kayda bölünür."""
    lines = trendyol.parse_claim_line(
        {
            "orderLine": {"id": 42, "price": 100, "barcode": "b", "merchantSku": "SKU"},
            "claimItems": [
                {"claimItemStatus": {"name": "Accepted"}},
                {"claimItemStatus": {"name": "Rejected"}},
                {"claimItemStatus": {"name": "Rejected"}},
            ],
        }
    )

    by_accepted = {line.accepted: line for line in lines}
    assert by_accepted[True].quantity == 1
    assert by_accepted[False].quantity == 2
    assert by_accepted[False].refund_amount == Decimal("200.0000")


@pytest.mark.asyncio
async def test_fetch_returns_uses_documented_path_and_size() -> None:
    """İade servisi doğrulanmış yolla ve 200'lük sayfayla çağrılır."""
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json=load_fixture("claims_page0"))

    connector = make_connector(handler)
    claims = await connector.fetch_returns(
        datetime(2026, 8, 10, tzinfo=UTC), datetime(2026, 8, 18, tzinfo=UTC)
    )

    assert captured["path"] == "/integration/order/sellers/998877/claims"
    assert captured["params"]["size"] == "200"
    assert len(claims) == 2


def test_settlement_amount_is_credit_minus_debt() -> None:
    """Borç/alacak tek tutara indirgenir: kesinti negatif, ödeme pozitif."""
    rows = [
        trendyol.parse_settlement_row(item) for item in load_fixture("settlements_page0")["content"]
    ]

    by_ref = {row.external_ref: row for row in rows}
    assert by_ref["STL-2026-08-0001"].amount == Decimal("289.9000")
    assert by_ref["STL-2026-08-0002"].amount == Decimal("-46.3800")
    assert by_ref["STL-2026-08-0002"].commission_rate == Decimal("16.0")


def test_settlement_types_map_to_internal_enum() -> None:
    """`transactionType` içeri tipe çevrilir; bilinmeyen tip sessizce ATILMAZ."""
    rows = [
        trendyol.parse_settlement_row(item) for item in load_fixture("settlements_page0")["content"]
    ]

    assert [row.record_type for row in rows] == ["sale", "commission", "refund", "cargo"]
    assert trendyol.normalize_settlement_type("ProvisionPositive") is SettlementRecordType.OTHER
    assert trendyol.normalize_settlement_type(None) is SettlementRecordType.OTHER


@pytest.mark.asyncio
async def test_fetch_settlements_requests_each_transaction_type() -> None:
    """Servis tek tip kabul ettiği için her tip ayrı istekle çekilir."""
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url.params.get("transactionType")))
        return httpx.Response(200, json={"content": [], "totalPages": 0})

    connector = make_connector(handler)
    await connector.fetch_settlements(
        datetime(2026, 8, 1, tzinfo=UTC), datetime(2026, 8, 10, tzinfo=UTC)
    )

    assert set(seen) == set(trendyol.SETTLEMENT_TRANSACTION_TYPES)


@pytest.mark.asyncio
async def test_settlement_window_never_exceeds_fifteen_days() -> None:
    """Aralık 15 günü aşamaz — uzun aralık pencerelere bölünür."""
    windows: set[tuple[str, str]] = set()

    def handler(request: httpx.Request) -> httpx.Response:
        params = request.url.params
        windows.add((str(params.get("startDate")), str(params.get("endDate"))))
        return httpx.Response(200, json={"content": [], "totalPages": 0})

    connector = make_connector(handler)
    await connector.fetch_settlements(
        datetime(2026, 7, 1, tzinfo=UTC), datetime(2026, 8, 15, tzinfo=UTC)
    )

    limit_ms = trendyol.SETTLEMENT_WINDOW_DAYS * 24 * 60 * 60 * 1000
    assert windows
    assert all(int(end) - int(start) <= limit_ms for start, end in windows)


def test_cargo_invoice_row_is_recognised_by_label() -> None:
    """Kesinti faturaları arasından yalnızca kargo faturası seçilir."""
    content = load_fixture("otherfinancials_deductions")["content"]

    assert [trendyol.is_cargo_invoice_row(row) for row in content] == [True, False]


def test_parse_cargo_invoice_line_reads_documented_fields() -> None:
    """`parcelUniqueId`, `orderNumber`, `amount`, `desi` okunur."""
    line = trendyol.parse_cargo_invoice_line(load_fixture("cargo_invoice_items")["content"][1])

    assert line.parcel_id == "7300000000022"
    assert line.external_order_id == "TY-2026-000203"
    assert line.amount == Decimal("94.5")
    assert line.desi == Decimal("3.4")


@pytest.mark.asyncio
async def test_fetch_cargo_invoices_follows_the_two_step_chain() -> None:
    """otherfinancials → seri numarası → cargo-invoice/{seri}/items zinciri."""
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path.endswith("/otherfinancials"):
            return httpx.Response(200, json=load_fixture("otherfinancials_deductions"))
        return httpx.Response(200, json=load_fixture("cargo_invoice_items"))

    connector = make_connector(handler)
    invoices = await connector.fetch_cargo_invoices(
        datetime(2026, 8, 1, tzinfo=UTC), datetime(2026, 8, 10, tzinfo=UTC)
    )

    # Yalnızca kargo faturası için kalem çağrısı yapılır; iade faturası atlanır.
    assert invoices[0].invoice_no == "KRG-2026-08-0001"
    assert "/integration/finance/che/sellers/998877/cargo-invoice/KRG-2026-08-0001/items" in paths
    assert not any("IAD-2026-08-0009" in path for path in paths)
    assert invoices[0].total == Decimal("204.3")
    assert len(invoices[0].lines) == 3
    assert invoices[0].period == "2026-08"


def test_order_carries_cargo_tracking_number() -> None:
    """`cargoTrackingNumber` artık taşınıyor (KVN-EK-02'de doğrulanamamıştı)."""
    order = trendyol.parse_order(
        {
            "orderNumber": "TY-1",
            "cargoTrackingNumber": 7300000000011,
            "cargoProviderName": "Trendyol Express",
            "lines": [],
        }
    )

    assert order.cargo_tracking_no == "7300000000011"
