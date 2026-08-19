"""KVN-09: dashboard, SKU marj listesi ve sipariş detayı (spec §10).

Bu katman hesap yapmaz; motorun `line_profit`'e yazdığını toplar. Testler bunu
doğrular: ekrandaki rakam ile motorun rakamı BİREBİR aynı olmalı, aksi halde
mutabakat imkânsızlaşır.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import deps
from app.core.context import system_scope
from app.main import create_app
from app.models.enums import OrderStatus
from app.models.identity import Brand, Store
from app.models.results import LineProfit
from app.models.transactions import Order, OrderLine, Return
from app.seeds.base import seed_base
from app.services import analytics
from app.services import profit as profit_service
from tests.profit_factories import ORDER_DATE, make_commission, make_order, make_product

D = Decimal
PERIOD = analytics.Period(
    start=ORDER_DATE.date() - timedelta(days=30), end=ORDER_DATE.date() + timedelta(days=1)
)


@pytest.fixture(autouse=True)
def system_context() -> Iterator[None]:
    """Okuma sorguları test içinde sistem kapsamında çalışır."""
    with system_scope():
        yield


@pytest.fixture
def store(db_session: Session) -> Store:
    """Kahveji Trendyol mağazası + hizmet bedeli."""
    seed_base(db_session)
    kahveji = db_session.scalar(select(Brand).where(Brand.slug == "kahveji"))
    assert kahveji is not None
    store = db_session.scalar(
        select(Store).where(Store.brand_id == kahveji.id).order_by(Store.name)
    )
    assert store is not None
    store.service_fee_per_order = D("12.0000")
    db_session.flush()
    return store


def _computed_order(db_session: Session, store: Store, **kwargs: Any) -> Order:
    """Ürün + tarife + sipariş kur, kârını hesapla."""
    product = kwargs.pop("product", None) or make_product(
        db_session, store, f"SKU-{uuid.uuid4().hex[:6]}"
    )
    make_commission(db_session, store)
    order = make_order(db_session, store, [(product, 1, D("120.00"))], **kwargs)
    profit_service.recompute_orders(db_session, order_ids=[order.id])
    return order


# --- dashboard (spec §10.1) --------------------------------------------------


def test_dashboard_totals_match_engine_output(db_session: Session, store: Store) -> None:
    """§10.1: KPI'lar motorun yazdığı satırların toplamıdır — yeniden hesaplanmaz."""
    _computed_order(db_session, store)
    _computed_order(db_session, store)

    result = analytics.dashboard(db_session, PERIOD)

    expected_profit = sum(
        (record.profit for record in db_session.scalars(select(LineProfit)).all()),
        D("0"),
    )
    assert result.kpis.profit == expected_profit
    assert result.kpis.order_count == 2
    assert result.kpis.line_count == 2
    assert result.kpis.revenue_gross == D("240.0000")


def test_dashboard_margin_is_profit_over_revenue(db_session: Session, store: Store) -> None:
    """§10.1: marj = net kâr / ciro; sıfır ciroda bölme hatası değil sıfır döner."""
    _computed_order(db_session, store)
    result = analytics.dashboard(db_session, PERIOD)

    assert result.kpis.margin_pct == analytics._margin(
        result.kpis.profit, result.kpis.revenue_gross
    )

    empty = analytics.dashboard(
        db_session, analytics.Period(start=date(2020, 1, 1), end=date(2020, 2, 1))
    )
    assert empty.kpis.margin_pct == D("0")
    assert empty.kpis.line_count == 0


def test_dashboard_excludes_cancelled_orders(db_session: Session, store: Store) -> None:
    """§6.3.5 + §10.1: iptal siparişler ciroyu ve sipariş sayısını şişirmez."""
    _computed_order(db_session, store)
    _computed_order(db_session, store, status=OrderStatus.CANCELLED)

    result = analytics.dashboard(db_session, PERIOD)

    assert result.kpis.order_count == 1
    assert result.kpis.revenue_gross == D("120.0000")


def test_dashboard_splits_estimated_and_final_profit(db_session: Session, store: Store) -> None:
    """Tasarım brief'i kalıp 2: tahmini ve kesinleşmiş kâr ayrı gösterilir."""
    _computed_order(db_session, store)
    result = analytics.dashboard(db_session, PERIOD)

    # Kargo maliyeti tahmini olduğu sürece satır kesinleşmiş sayılmaz.
    assert result.kpis.final_line_count == 0
    assert result.kpis.estimated_profit == result.kpis.profit
    assert result.kpis.final_profit == D("0")


def test_dashboard_return_rate_uses_refunded_amount(db_session: Session, store: Store) -> None:
    """§10.1: iade oranı = iade tutarı / (kalan ciro + iade tutarı)."""
    order = _computed_order(db_session, store)
    order_line = db_session.scalar(select(OrderLine).where(OrderLine.order_id == order.id))
    assert order_line is not None
    db_session.add(
        Return(
            tenant_id=store.tenant_id,
            brand_id=store.brand_id,
            order_line_id=order_line.id,
            return_date=ORDER_DATE,
            qty=1,
            refund_amount=D("120.0000"),
            return_cargo_cost_estimated=D("24.0000"),
        )
    )
    db_session.flush()
    profit_service.recompute_orders(db_session, order_ids=[order.id])

    result = analytics.dashboard(db_session, PERIOD)

    assert result.kpis.revenue_gross == D("0.0000")  # iade edilen adedin geliri düşer
    assert result.kpis.return_rate_pct == D("100.0000")


def test_dashboard_daily_series_covers_only_days_with_orders(
    db_session: Session, store: Store
) -> None:
    """§10.1: günlük seri yalnızca sipariş olan günleri taşır (boş gün uydurulmaz)."""
    _computed_order(db_session, store)
    _computed_order(db_session, store, order_date=ORDER_DATE - timedelta(days=3))

    result = analytics.dashboard(db_session, PERIOD)

    assert len(result.daily) == 2
    assert [point.day for point in result.daily] == sorted(point.day for point in result.daily)


# --- SKU marj listesi (spec §10.2) ------------------------------------------


def test_sku_margins_are_sorted_worst_first(db_session: Session, store: Store) -> None:
    """§10.2: en düşük kâr üstte — zarar ettiren SKU ilk bakışta görünsün."""
    cheap = make_product(db_session, store, "IYI-1", cost=D("10.0000"))
    pricey = make_product(db_session, store, "KOTU-1", cost=D("200.0000"))
    _computed_order(db_session, store, product=cheap)
    _computed_order(db_session, store, product=pricey)

    rows = analytics.sku_margins(db_session, PERIOD)

    assert [row.sku for row in rows] == ["KOTU-1", "IYI-1"]
    assert rows[0].profit < 0 < rows[1].profit


def test_sku_margins_negative_filter(db_session: Session, store: Store) -> None:
    """§10.2: "yalnızca negatif marj" filtresi kârlı satırları dışarıda bırakır."""
    cheap = make_product(db_session, store, "IYI-2", cost=D("10.0000"))
    pricey = make_product(db_session, store, "KOTU-2", cost=D("200.0000"))
    _computed_order(db_session, store, product=cheap)
    _computed_order(db_session, store, product=pricey)

    rows = analytics.sku_margins(db_session, PERIOD, only_negative=True)

    assert [row.sku for row in rows] == ["KOTU-2"]


def test_sku_margins_aggregate_multiple_orders(db_session: Session, store: Store) -> None:
    """§10.2: aynı SKU'nun birden fazla siparişi tek satırda toplanır."""
    product = make_product(db_session, store, "TOPLA-1")
    _computed_order(db_session, store, product=product)
    _computed_order(db_session, store, product=product)

    rows = analytics.sku_margins(db_session, PERIOD)

    assert len(rows) == 1
    assert rows[0].qty_sold == 2
    assert rows[0].revenue_gross == D("240.0000")


# --- sipariş detayı (spec §10.3) --------------------------------------------


def test_order_detail_waterfall_sums_to_profit(db_session: Session, store: Store) -> None:
    """§10.3 + tasarım brief'i kalıp 4: şelale adımları net kâra iner."""
    order = _computed_order(db_session, store)

    detail = analytics.order_detail(db_session, order.id)

    assert detail is not None
    steps = {step.key: step.amount for step in detail.waterfall}
    total = sum((step.amount for step in detail.waterfall if step.key != "kar"), D("0"))
    assert total == steps["kar"] == detail.profit


def test_order_detail_line_waterfall_matches_line_profit(db_session: Session, store: Store) -> None:
    """§10.3: satır şelalesi `line_profit` kaydından birebir üretilir."""
    order = _computed_order(db_session, store)
    detail = analytics.order_detail(db_session, order.id)
    assert detail is not None

    line = detail.lines[0]
    record = db_session.scalar(
        select(LineProfit).where(LineProfit.order_line_id == line.order_line_id)
    )
    assert record is not None
    steps = {step.key: step.amount for step in line.waterfall}
    assert steps["satis"] == record.revenue_gross
    assert steps["komisyon"] == -record.cost_commission
    assert steps["maliyet"] == -record.cost_cogs
    assert steps["kar"] == record.profit
    assert line.profit == record.profit


def test_order_detail_returns_none_for_unknown_order(db_session: Session, store: Store) -> None:
    """§10.3: olmayan sipariş `None` döner — API bunu 404'e çevirir."""
    assert analytics.order_detail(db_session, uuid.uuid4()) is None


# --- API katmanı: yetki, izolasyon, doğrulama -------------------------------


@pytest.fixture
def api(db_session: Session, store: Store) -> Iterator[TestClient]:
    """Kâr kaydı hesaplanmış, test oturumuna bağlı API istemcisi."""
    _computed_order(db_session, store)

    async def session_override() -> Any:
        yield db_session

    app = create_app()
    app.dependency_overrides[deps.get_session] = session_override
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def _headers(api: TestClient, brand: str) -> dict[str, str]:
    response = api.post("/auth/dev-login", json={"email": "mert@mokkalabs.com", "brand": brand})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_dashboard_endpoint_requires_authentication(api: TestClient) -> None:
    """Spec §3A: token'sız istek 401."""
    assert api.get("/kahveji/dashboard").status_code == 401


def test_dashboard_endpoint_returns_kpis(api: TestClient) -> None:
    """§10.1: uç, dönem KPI'larını ve serileri döner."""
    response = api.get(
        "/kahveji/dashboard",
        params={"from": str(PERIOD.start), "to": str(PERIOD.end)},
        headers=_headers(api, "kahveji"),
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert Decimal(payload["kpis"]["revenue_gross"]) == D("120.0000")
    assert payload["period"]["start"] == str(PERIOD.start)


def test_order_detail_of_other_brand_returns_404(api: TestClient, db_session: Session) -> None:
    """§3A.6: başka markanın siparişi 403 değil 404 döner — varlığı sızdırılmaz."""
    order = db_session.scalar(select(Order))
    assert order is not None

    response = api.get(f"/alessi/orders/{order.id}", headers=_headers(api, "alessi"))

    assert response.status_code == 404


def test_period_longer_than_limit_is_rejected(api: TestClient) -> None:
    """Aşırı geniş dönem 422 döner — kazara tüm veriyi tarayan sorgu atılmaz."""
    response = api.get(
        "/kahveji/dashboard",
        params={"from": "2020-01-01", "to": "2026-01-01"},
        headers=_headers(api, "kahveji"),
    )

    assert response.status_code == 422


def test_reversed_period_is_rejected(api: TestClient) -> None:
    """Bitişi başlangıçtan önce olan dönem 422 döner."""
    response = api.get(
        "/kahveji/dashboard",
        params={"from": "2026-08-10", "to": "2026-08-01"},
        headers=_headers(api, "kahveji"),
    )

    assert response.status_code == 422
