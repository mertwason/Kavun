"""KVN-13: komisyon snapshot/diff, etki analizi ve toplu tarife senaryosu (spec §12B).

Kabul kriterleri (§12B.5) birebir test edilir:
- üç kaynaktan çözümleme hiyerarşisi doğru (KVN-07'de kurulmuştu, burada da tutuluyor)
- snapshot diff: oran değişince change kaydı + DOĞRU etki tutarı
- tariff-impact round-trip: önerilen fiyat motorla geri hesaplanınca hedef marjı ±0,01 tutturur
- settlement'tan gelen gerçek oran çelişkisi sessiz geçilmez
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import deps
from app.core.context import RequestContext, system_scope, use_context
from app.engine.profit import LineInput, compute_line_profit
from app.main import create_app
from app.models.catalog import CommissionChange, CommissionRate, Product, SkuPrice
from app.models.enums import CommissionScope, CommissionSource, UserRole
from app.models.identity import Brand, Store
from app.models.results import Alert
from app.services import profit as profit_service
from app.services import tariffs
from app.services.commission import resolve_commission
from tests.profit_factories import ORDER_DATE, make_commission, make_order, make_product, make_store

D = Decimal
TODAY = ORDER_DATE.date()
CATEGORY = "Kahve/Harman"


@pytest.fixture
def store(db_session: Session) -> Iterator[Store]:
    """Mağaza + hizmet bedeli; marka bağlamı kurulur."""
    with system_scope():
        store = make_store(db_session)
        store.service_fee_per_order = D("12.0000")
        db_session.flush()
        brand = db_session.get(Brand, store.brand_id)
    assert brand is not None
    context = RequestContext(
        tenant_id=brand.tenant_id,
        user_id=None,
        brand_id=brand.id,
        brand_slug=brand.slug,
        role=UserRole.ADMIN,
    )
    with use_context(context):
        yield store


@pytest.fixture
def product(db_session: Session, store: Store) -> Product:
    """Satışı olan, fiyatı ve maliyeti tanımlı ürün."""
    product = make_product(db_session, store, "TARIFE-1", cost=D("50.0000"), category=CATEGORY)
    db_session.add(
        SkuPrice(
            product_id=product.id,
            store_id=store.id,
            price=D("199.0000"),
            effective_from=TODAY - timedelta(days=60),
        )
    )
    db_session.flush()
    return product


def _sold(db_session: Session, store: Store, product: Product, *, qty: int = 10) -> None:
    """Son 30 günde satış üretir ve kârını hesaplar."""
    order = make_order(db_session, store, [(product, qty, D("199.0000") * qty)])
    profit_service.recompute_orders(db_session, order_ids=[order.id])


# --- çözümleme hiyerarşisi (spec §12B.1, §12B.5) ----------------------------


def test_hierarchy_prefers_settlement_over_api_and_manual(
    db_session: Session, store: Store, product: Product
) -> None:
    """§12B.5: aynı ürün için üç kaynak varsa `settlement_actual` kazanır."""
    make_commission(db_session, store, rate=D("0.2000"), category=CATEGORY)
    for source, rate in (
        (CommissionSource.MANUAL, D("0.1000")),
        (CommissionSource.API_PRODUCT, D("0.1800")),
        (CommissionSource.SETTLEMENT_ACTUAL, D("0.2350")),
    ):
        db_session.add(
            CommissionRate(
                store_id=store.id,
                scope=CommissionScope.PRODUCT,
                product_id=product.id,
                rate=rate,
                source=source,
                valid_from=TODAY - timedelta(days=10),
            )
        )
    db_session.flush()

    resolved, resolved_source = resolve_commission(
        db_session, store_id=store.id, product=product, on_date=TODAY
    )

    assert resolved is not None
    assert resolved.rate == D("0.2350")
    assert resolved_source is CommissionSource.SETTLEMENT_ACTUAL


# --- etki formülü (spec §12B.3) ---------------------------------------------


def test_profit_delta_matches_the_engine() -> None:
    """Etki formülü motorla BİREBİR aynı sonucu vermeli — yaklaşık hesap yok."""
    line = LineInput(
        line_gross=D("1990.00"),
        qty=1,
        vat_percent=D("20.00"),
        unit_cost_net=D("500.00"),
        commission_rate=D("0.2000"),
        cargo_cost=D("50.00"),
        service_fee=D("12.00"),
    )
    higher = LineInput(**{**line.__dict__, "commission_rate": D("0.2300")})

    engine_delta = compute_line_profit(higher).profit - compute_line_profit(line).profit
    formula_delta = tariffs.profit_delta(D("1990.00"), D("0.2000"), D("0.2300"))

    assert abs(engine_delta - formula_delta) <= D("0.0001")


def test_rate_increase_reduces_profit(db_session: Session, store: Store, product: Product) -> None:
    """Oran artışı negatif etki üretir (işaret hatası olmasın)."""
    assert tariffs.profit_delta(D("1000"), D("0.20"), D("0.25")) < 0
    assert tariffs.profit_delta(D("1000"), D("0.25"), D("0.20")) > 0


# --- snapshot diff (spec §12B.3, kabul §12B.5) ------------------------------


def test_rate_change_creates_change_record_and_alert(
    db_session: Session, store: Store, product: Product
) -> None:
    """§12B.5: oran değişince `commission_changes` + alert üretilir, etki tutarı doğru."""
    make_commission(
        db_session,
        store,
        rate=D("0.2150"),
        category=CATEGORY,
        valid_from=ORDER_DATE - timedelta(days=60),
    )
    _sold(db_session, store, product, qty=10)
    # Bugünden geçerli yeni tarife: %21,5 → %23,0
    make_commission(db_session, store, rate=D("0.2300"), category=CATEGORY, valid_from=ORDER_DATE)

    summary = tariffs.detect_changes(db_session, store=store, on_date=TODAY)

    assert summary.detected == 1
    assert summary.alerts == 1
    change = db_session.scalar(select(CommissionChange))
    assert change is not None
    assert change.old_rate == D("0.2150")
    assert change.new_rate == D("0.2300")

    revenue = D("199.0000") * 10
    assert change.monthly_profit_impact == tariffs.profit_delta(revenue, D("0.2150"), D("0.2300"))
    assert change.monthly_profit_impact is not None and change.monthly_profit_impact < 0


def test_alert_message_carries_the_numbers(
    db_session: Session, store: Store, product: Product
) -> None:
    """§12B.3: alert mesajı oranları ve parasal etkiyi metin olarak taşır."""
    make_commission(
        db_session,
        store,
        rate=D("0.2150"),
        category=CATEGORY,
        valid_from=ORDER_DATE - timedelta(days=60),
    )
    _sold(db_session, store, product)
    make_commission(db_session, store, rate=D("0.2300"), category=CATEGORY, valid_from=ORDER_DATE)

    tariffs.detect_changes(db_session, store=store, on_date=TODAY)

    alert = db_session.scalar(select(Alert).where(Alert.type == tariffs.ALERT_TYPE))
    assert alert is not None
    assert CATEGORY in alert.message
    assert "%21.5" in alert.message or "%21,5" in alert.message
    assert "aylık kâr etkisi" in alert.message


def test_unchanged_rate_produces_nothing(
    db_session: Session, store: Store, product: Product
) -> None:
    """Oran değişmediyse gürültü üretilmez (her gün alert yağmuru olmaz)."""
    make_commission(
        db_session,
        store,
        rate=D("0.2000"),
        category=CATEGORY,
        valid_from=ORDER_DATE - timedelta(days=60),
    )
    _sold(db_session, store, product)

    summary = tariffs.detect_changes(db_session, store=store, on_date=TODAY)

    assert summary.detected == 0
    assert db_session.scalar(select(CommissionChange)) is None


def test_sku_falling_to_negative_margin_is_flagged(
    db_session: Session, store: Store, product: Product
) -> None:
    """§12B.3: negatife düşen SKU sayılır ve alert kritik seviyeye çıkar."""
    make_commission(
        db_session,
        store,
        rate=D("0.2000"),
        category=CATEGORY,
        valid_from=ORDER_DATE - timedelta(days=60),
    )
    _sold(db_session, store, product, qty=1)
    # Kârı sıfırın altına indirecek kadar sert bir artış.
    make_commission(db_session, store, rate=D("0.9000"), category=CATEGORY, valid_from=ORDER_DATE)

    summary = tariffs.detect_changes(db_session, store=store, on_date=TODAY)

    assert summary.impact is not None
    assert summary.impact.negative_margin_sku_count >= 1
    alert = db_session.scalar(select(Alert).where(Alert.type == tariffs.ALERT_TYPE))
    assert alert is not None
    assert "Negatif marja düşen SKU" in alert.message


# --- toplu tarife senaryosu (spec §12B.4, kabul §12B.5) ---------------------


def test_tariff_impact_round_trip_hits_target_margin(
    db_session: Session, store: Store, product: Product
) -> None:
    """§12B.5 kabul kriteri: önerilen fiyat motorla geri hesaplanınca hedef marj ±0,01."""
    make_commission(
        db_session,
        store,
        rate=D("0.2000"),
        category=CATEGORY,
        valid_from=ORDER_DATE - timedelta(days=60),
    )
    _sold(db_session, store, product)

    result = tariffs.tariff_impact(
        db_session,
        store=store,
        on_date=TODAY,
        category=CATEGORY,
        rate_delta=D("0.0150"),
        target_margin_pct=D("20"),
        cargo_estimate=D("24.00"),
    )

    row = next(item for item in result.rows if item.sku == "TARIFE-1")
    assert row.required_price is not None
    recomputed = compute_line_profit(
        LineInput(
            line_gross=row.required_price,
            qty=1,
            vat_percent=product.vat_rate,
            unit_cost_net=D("50.0000"),
            commission_rate=row.new_rate,
            cargo_cost=D("24.00"),
            service_fee=D("12.0000"),
        )
    )
    assert abs(recomputed.margin_pct - D("20")) <= D("0.01")


def test_tariff_impact_reports_margin_drop(
    db_session: Session, store: Store, product: Product
) -> None:
    """§12B.4: mevcut fiyatla yeni marj, eski marjdan düşük olmalı."""
    make_commission(
        db_session,
        store,
        rate=D("0.2000"),
        category=CATEGORY,
        valid_from=ORDER_DATE - timedelta(days=60),
    )
    _sold(db_session, store, product)

    result = tariffs.tariff_impact(
        db_session,
        store=store,
        on_date=TODAY,
        rate_delta=D("0.0150"),
        cargo_estimate=D("24.00"),
    )

    row = next(item for item in result.rows if item.sku == "TARIFE-1")
    assert row.new_rate == D("0.2150")
    assert row.projected_margin_pct < row.current_margin_pct
    assert result.monthly_profit_impact < 0


def test_tariff_impact_requires_a_rate_input(db_session: Session, store: Store) -> None:
    """Oran verilmeden etki hesaplanamaz."""
    with pytest.raises(ValueError, match="new_rate ya da rate_delta"):
        tariffs.tariff_impact(db_session, store=store, on_date=TODAY)


def test_absolute_new_rate_overrides_current(
    db_session: Session, store: Store, product: Product
) -> None:
    """`new_rate` mutlak orandır; mevcut orana bakılmaz."""
    make_commission(
        db_session,
        store,
        rate=D("0.2000"),
        category=CATEGORY,
        valid_from=ORDER_DATE - timedelta(days=60),
    )

    result = tariffs.tariff_impact(
        db_session, store=store, on_date=TODAY, category=CATEGORY, new_rate=D("0.1000")
    )

    row = next(item for item in result.rows if item.sku == "TARIFE-1")
    assert row.old_rate == D("0.2000")
    assert row.new_rate == D("0.1000")
    assert row.profit_impact >= 0  # oran düştü → kâr artar


# --- hakediş çelişkisi (spec §12B.3, kabul §12B.5) --------------------------


def test_settlement_conflict_writes_actual_rate(
    db_session: Session, store: Store, product: Product
) -> None:
    """§12B.5: hakedişteki gerçek oran tarifeden farklıysa sessiz geçilmez."""
    make_commission(
        db_session,
        store,
        rate=D("0.2000"),
        category=CATEGORY,
        valid_from=ORDER_DATE - timedelta(days=60),
    )

    record = tariffs.settlement_conflict(
        db_session, store=store, product=product, settlement_rate=D("0.2350"), on_date=TODAY
    )

    assert record is not None
    assert record.source is CommissionSource.SETTLEMENT_ACTUAL
    assert record.rate == D("0.2350")
    resolved, source = resolve_commission(
        db_session, store_id=store.id, product=product, on_date=TODAY
    )
    assert resolved is not None and resolved.rate == D("0.2350")
    assert source is CommissionSource.SETTLEMENT_ACTUAL


def test_matching_settlement_rate_creates_nothing(
    db_session: Session, store: Store, product: Product
) -> None:
    """Oran zaten aynıysa gereksiz kayıt açılmaz."""
    make_commission(
        db_session,
        store,
        rate=D("0.2000"),
        category=CATEGORY,
        valid_from=ORDER_DATE - timedelta(days=60),
    )

    assert (
        tariffs.settlement_conflict(
            db_session, store=store, product=product, settlement_rate=D("0.2000"), on_date=TODAY
        )
        is None
    )


# --- API katmanı -------------------------------------------------------------


@pytest.fixture
def api(db_session: Session, store: Store, product: Product) -> Iterator[TestClient]:
    """Tarifesi ve satışı olan, test oturumuna bağlı API istemcisi."""
    make_commission(
        db_session,
        store,
        rate=D("0.2000"),
        category=CATEGORY,
        valid_from=ORDER_DATE - timedelta(days=60),
    )
    _sold(db_session, store, product)

    async def session_override() -> Any:
        yield db_session

    app = create_app()
    app.dependency_overrides[deps.get_session] = session_override
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def _headers(api: TestClient, brand: str = "alessi") -> dict[str, str]:
    response = api.post("/auth/dev-login", json={"email": "mert@mokkalabs.com", "brand": brand})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_rates_endpoint_lists_current_tariffs(api: TestClient) -> None:
    """Geçerli tarifeler listelenir."""
    response = api.get("/alessi/tariffs", params={"on_date": str(TODAY)}, headers=_headers(api))

    assert response.status_code == 200, response.text
    assert any(row["category_code"] == CATEGORY for row in response.json())


def test_impact_endpoint_returns_rows(api: TestClient) -> None:
    """§12B.4: uç etkilenen SKU'ları ve toplam etkiyi döner."""
    response = api.post(
        "/alessi/tariffs/impact",
        json={"rate_delta": "0.015", "target_margin_pct": "20", "kargo_tahmini": "24.00"},
        headers=_headers(api),
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert Decimal(payload["monthly_profit_impact"]) < 0
    assert any(row["sku"] == "TARIFE-1" for row in payload["rows"])


def test_impact_endpoint_requires_rate_input(api: TestClient) -> None:
    """Oran verilmezse 422."""
    response = api.post("/alessi/tariffs/impact", json={}, headers=_headers(api))

    assert response.status_code == 422


def test_detect_changes_endpoint(api: TestClient, db_session: Session, store: Store) -> None:
    """Günlük job elle tetiklenebilir ve değişikliği raporlar.

    Uç `date.today()` ile çalışır; değişiklik ancak tarifenin YÜRÜRLÜĞE GİRDİĞİ gün
    tespit edilir — dünkü geçerli oran bugünkü ile karşılaştırıldığı için.
    """
    make_commission(
        db_session, store, rate=D("0.2300"), category=CATEGORY, valid_from=datetime.now(UTC)
    )

    response = api.post("/alessi/tariffs/detect-changes", headers=_headers(api))

    assert response.status_code == 200, response.text
    assert response.json()["detected"] == 1
    listed = api.get("/alessi/tariffs/changes", headers=_headers(api))
    assert listed.status_code == 200
    assert listed.json()[0]["new_rate"] == "0.2300"
