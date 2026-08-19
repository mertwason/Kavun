"""KVN-EK-04: kargo tarife tablosu + Ayarlar uçları (spec §6.1, §10.7).

Kabul: kargo tahmini **tarife tablosundan** çözülür (`desi_bazli_tahmin(desi, carrier_tarife)`),
tarife yoksa varsayılan formüle düşülür, tarife değişikliği geçmişi sessizce ezmez ve
kesinleşmiş (`actual`) maliyet yeniden tahminle ASLA değiştirilmez.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import deps
from app.core.context import RequestContext, system_scope, use_context
from app.engine import cargo as engine
from app.main import create_app
from app.models.catalog import CargoTariff, Product
from app.models.enums import CostState, UserRole
from app.models.identity import Brand, Store
from app.models.results import ProfitRevision
from app.models.transactions import Order, OrderLine, Shipment
from app.services import cargo_tariffs, profit
from tests.profit_factories import make_order, make_product, make_store

D = Decimal
TODAY = date(2026, 8, 19)


# --- motor: saf bant çözümlemesi ---------------------------------------------


def band(
    lo: str,
    hi: str | None,
    price: str,
    *,
    carrier: str | None = None,
    valid_from: date | None = None,
) -> engine.Band:
    """Test bandı."""
    return engine.Band(
        desi_min=D(lo),
        desi_max=D(hi) if hi is not None else None,
        price=D(price),
        carrier=carrier,
        valid_from=valid_from,
    )


BANDS = [band("0", "1", "54.90"), band("1", "3", "78.00"), band("3", None, "128.00")]


def test_band_lower_bound_is_inclusive_upper_is_exclusive() -> None:
    """Bitişik bantlar boşluk ve çakışma üretmez: 1,00 desi ikinci banda düşer."""
    assert engine.estimate(desi=D("0.99"), bands=BANDS).amount == D("54.9000")
    assert engine.estimate(desi=D("1.00"), bands=BANDS).amount == D("78.0000")


def test_unbounded_band_catches_everything_above() -> None:
    """Üst sınırsız bant "10 desi ve üzeri" durumunu karşılar."""
    assert engine.estimate(desi=D("250"), bands=BANDS).amount == D("128.0000")


def test_missing_tariff_falls_back_to_default_formula() -> None:
    """Tarife yoksa sessizce sıfır değil, varsayılan formül yazılır."""
    result = engine.estimate(desi=D("2"), bands=[])

    assert result.source == "varsayilan"
    assert result.amount == engine.default_estimate(D("2"))
    assert result.amount > D("0")


def test_unknown_desi_falls_back_to_default() -> None:
    """Desi bilinmiyorsa bant uygulanamaz; taban ücret yazılır."""
    result = engine.estimate(desi=None, bands=BANDS)

    assert result.source == "varsayilan"
    assert result.amount == engine.DEFAULT_BASE.quantize(D("0.0001"))


def test_carrier_specific_band_beats_wildcard() -> None:
    """Firma bandı, "tüm firmalar" bandını yener (spec §6.1 çözümleme sırası)."""
    bands = [*BANDS, band("0", "1", "49.90", carrier="Trendyol Express")]

    assert engine.estimate(desi=D("0.5"), bands=bands, carrier="Trendyol Express").amount == D(
        "49.9000"
    )
    assert engine.estimate(desi=D("0.5"), bands=bands, carrier="Aras Kargo").amount == D("54.9000")


def test_carrier_match_is_case_insensitive() -> None:
    """Kanal "Yurtiçi Kargo" derken tarifeye "yurtiçi kargo" yazılmışsa eşleşme bozulmaz."""
    bands = [band("0", "5", "60.00", carrier="yurtiçi kargo")]

    assert engine.estimate(desi=D("1"), bands=bands, carrier="Yurtiçi Kargo").source == "tarife"


def test_newer_valid_from_wins() -> None:
    """Aynı aralıkta iki bant varsa yürürlüğe en son giren kazanır."""
    bands = [
        band("0", "5", "60.00", valid_from=date(2026, 1, 1)),
        band("0", "5", "72.00", valid_from=date(2026, 6, 1)),
    ]

    assert engine.estimate(desi=D("2"), bands=bands, on=TODAY).amount == D("72.0000")


def test_future_band_is_not_applied_yet() -> None:
    """Yürürlük tarihi gelecekte olan bant bugünün gönderisine uygulanmaz."""
    bands = [
        band("0", "5", "60.00", valid_from=date(2026, 1, 1)),
        band("0", "5", "999.00", valid_from=date(2027, 1, 1)),
    ]

    assert engine.estimate(desi=D("2"), bands=bands, on=TODAY).amount == D("60.0000")


# --- DB katmanı ---------------------------------------------------------------


@pytest.fixture
def store(db_session: Session) -> Iterator[Store]:
    """Mağaza + marka bağlamı."""
    with system_scope():
        record = make_store(db_session)
        brand = db_session.get(Brand, record.brand_id)
    assert brand is not None
    context = RequestContext(
        tenant_id=brand.tenant_id,
        user_id=None,
        brand_id=brand.id,
        brand_slug=brand.slug,
        role=UserRole.ADMIN,
    )
    with use_context(context):
        yield record


@pytest.fixture
def product(db_session: Session, store: Store) -> Product:
    return make_product(db_session, store, "KHV-TRF-01", cost=D("300.0000"), desi=D("2.00"))


def _add(
    db_session: Session, store: Store, lo: str, hi: str | None, price: str, **kw: object
) -> CargoTariff:
    return cargo_tariffs.add_band(
        db_session,
        tenant_id=store.tenant_id,
        brand_id=store.brand_id,
        desi_min=D(lo),
        desi_max=D(hi) if hi is not None else None,
        price=D(price),
        **kw,  # type: ignore[arg-type]
    )


def test_band_is_read_back_through_the_engine(db_session: Session, store: Store) -> None:
    """Yazılan bant, motorun çözümlemesinde görünür."""
    _add(db_session, store, "0", "5", "88.00")

    result = cargo_tariffs.preview(db_session, desi=D("3"))

    assert result.source == "tarife"
    assert result.amount == D("88.0000")


def test_invalid_band_is_rejected(db_session: Session, store: Store) -> None:
    """Üst sınır alt sınırdan küçükse bant yazılmaz."""
    with pytest.raises(cargo_tariffs.InvalidBandError):
        _add(db_session, store, "5", "2", "88.00")

    with pytest.raises(cargo_tariffs.InvalidBandError):
        _add(db_session, store, "0", "5", "-1.00")


def test_closed_band_is_kept_but_no_longer_applied(db_session: Session, store: Store) -> None:
    """Bant silinmez, kapatılır: geçmiş tahminin dayanağı kayıtta kalır."""
    row = _add(db_session, store, "0", "5", "88.00")

    cargo_tariffs.close_band(db_session, row.id, on=date.today() - timedelta(days=1))

    assert cargo_tariffs.preview(db_session, desi=D("3")).source == "varsayilan"
    assert db_session.get(CargoTariff, row.id) is not None
    assert len(cargo_tariffs.tariffs(db_session, include_closed=True)) == 1
    assert cargo_tariffs.tariffs(db_session) == []


def test_bands_for_brand_does_not_leak_across_brands(db_session: Session, store: Store) -> None:
    """`system_scope` altında bile başka markanın tarifesi okunmaz (CLAUDE.md §2)."""
    _add(db_session, store, "0", "5", "88.00")
    with system_scope():
        other = db_session.scalar(select(Brand).where(Brand.id != store.brand_id))
    assert other is not None

    with system_scope():
        mine = cargo_tariffs.bands_for_brand(db_session, store.brand_id)
        theirs = cargo_tariffs.bands_for_brand(db_session, other.id)

    assert len(mine) == 1
    assert theirs == []


# --- yeniden tahmin -----------------------------------------------------------


@pytest.fixture
def order(db_session: Session, store: Store, product: Product) -> Order:
    """Gönderisi tahmini maliyetle duran sipariş."""
    record = make_order(db_session, store, [(product, 1, D("1000.00"))])
    shipment = db_session.scalar(select(Shipment).where(Shipment.order_id == record.id))
    assert shipment is not None
    shipment.desi_declared = D("2.00")
    shipment.carrier = "Trendyol Express"
    shipment.cargo_cost_estimated = D("24.0000")
    shipment.cost_state = CostState.ESTIMATED
    db_session.flush()
    profit.recompute_orders(db_session, order_ids=[record.id])
    return record


def test_reestimate_dry_run_writes_nothing(db_session: Session, store: Store, order: Order) -> None:
    """Önizleme farkı gösterir ama hiçbir tahmini değiştirmez."""
    _add(db_session, store, "0", "5", "88.00")

    summary = cargo_tariffs.reestimate(db_session, dry_run=True)

    assert summary.changed == 1
    assert summary.delta == D("64.0000")
    shipment = db_session.scalar(select(Shipment).where(Shipment.order_id == order.id))
    assert shipment is not None
    assert shipment.cargo_cost_estimated == D("24.0000")


def test_reestimate_updates_estimate_and_logs_the_trigger(
    db_session: Session, store: Store, order: Order
) -> None:
    """Uygulandığında tahmin güncellenir ve kâr revizyonu gerekçesiyle loglanır (§6.2)."""
    _add(db_session, store, "0", "5", "88.00")

    summary = cargo_tariffs.reestimate(db_session, dry_run=False)

    assert summary.changed == 1
    shipment = db_session.scalar(select(Shipment).where(Shipment.order_id == order.id))
    assert shipment is not None
    assert shipment.cargo_cost_estimated == D("88.0000")

    line_ids = list(db_session.scalars(select(OrderLine.id).where(OrderLine.order_id == order.id)))
    revisions = list(
        db_session.scalars(select(ProfitRevision).where(ProfitRevision.order_line_id.in_(line_ids)))
    )
    assert revisions, "tahmin değişince revizyon yazılmalı"
    assert all(row.reason == cargo_tariffs.REESTIMATE_REASON for row in revisions)


def test_reestimate_never_touches_finalised_cost(
    db_session: Session, store: Store, order: Order
) -> None:
    """Kargo faturasından gelen gerçek tutar tarifeyle ezilmez (KVN-EK-02 kuralı)."""
    shipment = db_session.scalar(select(Shipment).where(Shipment.order_id == order.id))
    assert shipment is not None
    shipment.cargo_cost_actual = D("101.0000")
    shipment.cost_state = CostState.ACTUAL
    db_session.flush()
    _add(db_session, store, "0", "5", "88.00")

    summary = cargo_tariffs.reestimate(db_session, dry_run=False)

    assert summary.changed == 0
    assert summary.skipped_actual == 1
    assert shipment.cargo_cost_actual == D("101.0000")


def test_tariff_change_alone_does_not_rewrite_history(
    db_session: Session, store: Store, order: Order
) -> None:
    """Bant eklemek geçmiş tahminleri kendiliğinden değiştirmez — eylem açıktır."""
    _add(db_session, store, "0", "5", "88.00")

    shipment = db_session.scalar(select(Shipment).where(Shipment.order_id == order.id))
    assert shipment is not None
    assert shipment.cargo_cost_estimated == D("24.0000")


# --- API ----------------------------------------------------------------------


@pytest.fixture
def api(db_session: Session, store: Store) -> Iterator[TestClient]:
    """Test oturumuna bağlı API istemcisi (seed edilmiş mağaza/kullanıcıyla)."""

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


def test_api_lists_and_creates_bands(api: TestClient) -> None:
    """Bant ekleme ve listeleme uçları çalışır."""
    headers = _headers(api)

    created = api.post(
        "/alessi/settings/cargo-tariffs",
        json={"desi_min": "0", "desi_max": "5", "price": "88.00"},
        headers=headers,
    )
    assert created.status_code == 201, created.text

    listed = api.get("/alessi/settings/cargo-tariffs", headers=headers)
    assert listed.status_code == 200
    assert [row["price"] for row in listed.json()] == ["88.0000"]


def test_api_rejects_invalid_band(api: TestClient) -> None:
    """Geçersiz aralık 422 döner; sessizce kabul edilmez."""
    response = api.post(
        "/alessi/settings/cargo-tariffs",
        json={"desi_min": "5", "desi_max": "2", "price": "88.00"},
        headers=_headers(api),
    )

    assert response.status_code == 422


def test_api_preview_reports_the_source(api: TestClient) -> None:
    """Önizleme tutarın tarifeden mi varsayılandan mı geldiğini söyler."""
    headers = _headers(api)

    empty = api.get("/alessi/settings/cargo-tariffs/preview?desi=2", headers=headers)
    assert empty.json()["source"] == "varsayilan"

    api.post(
        "/alessi/settings/cargo-tariffs",
        json={"desi_min": "0", "desi_max": "5", "price": "88.00"},
        headers=headers,
    )
    filled = api.get("/alessi/settings/cargo-tariffs/preview?desi=2", headers=headers)
    assert filled.json()["source"] == "tarife"
    assert filled.json()["amount"] == "88.0000"


def test_api_band_of_another_brand_is_invisible(api: TestClient) -> None:
    """Alessi'nin bandı Kahveji'nin listesinde görünmez (CLAUDE.md §2)."""
    api.post(
        "/alessi/settings/cargo-tariffs",
        json={"desi_min": "0", "desi_max": "5", "price": "88.00"},
        headers=_headers(api),
    )

    other = api.get("/kahveji/settings/cargo-tariffs", headers=_headers(api, "kahveji"))

    assert other.status_code == 200
    assert other.json() == []
