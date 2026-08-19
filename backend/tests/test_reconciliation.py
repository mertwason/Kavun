"""KVN-EK-03: hakediş mutabakatı (spec §7).

Kabul: hakediş kalemi bizim hesabımızla karşılaştırılır; eşik üstü sapma
`reconciliation_diffs`'e düşer + uyarı üretir. Eşleşmeyen kalem ayrı kuyrukta gösterilir,
uydurma eşleştirme yapılmaz. Açıklamasız kapatma yoktur.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import deps
from app.core.context import RequestContext, system_scope, use_context
from app.main import create_app
from app.models.catalog import Product
from app.models.enums import (
    CostState,
    DiffStatus,
    SettlementRecordType,
    UserRole,
)
from app.models.identity import Store
from app.models.results import Alert, ReconciliationDiff
from app.models.transactions import Order, OrderLine, SettlementRecord, Shipment
from app.reconciliation.engine import DEFAULT_TOLERANCE, compare, normalise
from app.services import profit, reconciliation
from tests.profit_factories import make_order, make_product, make_store

D = Decimal
PERIOD = "2026-08"
TX_DATE = date(2026, 8, 14)


@pytest.fixture
def store(db_session: Session) -> Iterator[Store]:
    """Mağaza + marka bağlamı."""
    from app.models.identity import Brand

    with system_scope():
        store = make_store(db_session)
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
    """Maliyeti tanımlı ürün."""
    return make_product(db_session, store, "KHV-BLD-ESP", cost=D("580.0000"))


@pytest.fixture
def line(db_session: Session, store: Store, product: Product) -> OrderLine:
    """Kârı hesaplanmış tek satırlık sipariş."""
    order = make_order(db_session, store, [(product, 1, D("1000.00"))])
    row = db_session.scalar(select(OrderLine).where(OrderLine.order_id == order.id))
    assert row is not None
    row.commission_rate_used = D("0.2000")
    db_session.flush()
    with system_scope():
        profit.recompute_orders(db_session, order_ids=[order.id])
    return row


def _record(
    db_session: Session,
    store: Store,
    *,
    ref: str,
    record_type: SettlementRecordType,
    amount: Decimal,
) -> SettlementRecord:
    """Hakediş kalemi ekler (platform kesintileri negatif gelir)."""
    row = SettlementRecord(
        tenant_id=store.tenant_id,
        brand_id=store.brand_id,
        store_id=store.id,
        external_ref=ref,
        record_type=record_type,
        amount=amount,
        transaction_date=TX_DATE,
    )
    db_session.add(row)
    db_session.flush()
    return row


# --- motor (saf fonksiyonlar) ------------------------------------------------


def test_platform_sign_is_normalised() -> None:
    """Platform kesintileri negatif gelir; karşılaştırma mutlak büyüklükle yapılır."""
    assert normalise(D("-48.00")) == D("48.00")
    assert normalise(D("48.00")) == D("48.00")


def test_small_deviation_is_within_tolerance() -> None:
    """§7.3: 0,05 TL altındaki sapma yuvarlama gürültüsüdür, kayıt üretmez."""
    result = compare(expected=D("100.00"), actual=D("-100.04"))

    assert result.within_tolerance is True
    # Platform 4 kuruş fazla kesmiş: fark pozitif, ama eşiğin altında.
    assert result.diff == D("0.0400")


def test_deviation_above_tolerance_is_a_diff() -> None:
    """Eşiği aşan sapma fark sayılır."""
    result = compare(expected=D("100.00"), actual=D("-108.00"))

    assert result.within_tolerance is False
    assert result.diff == D("8.0000")


def test_tolerance_is_configurable_but_defaults_to_five_kurus() -> None:
    """Eşik tek yerden gelir; varsayılan spec'in verdiği değerdir."""
    assert D("0.05") == DEFAULT_TOLERANCE
    assert compare(expected=D("100"), actual=D("100.20"), tolerance=D("0.50")).within_tolerance


# --- eşleştirme ve fark üretimi ----------------------------------------------


def test_matching_commission_within_tolerance_writes_no_diff(
    db_session: Session, store: Store, line: OrderLine
) -> None:
    """Platform bizim hesapladığımız komisyonu kesmişse fark yoktur."""
    _record(
        db_session,
        store,
        ref=line.external_line_id,
        record_type=SettlementRecordType.COMMISSION,
        amount=D("-200.00"),
    )

    summary = reconciliation.run(db_session, store=store, period=PERIOD)

    assert summary.records == 1
    assert summary.matched == 1
    assert summary.within_tolerance == 1
    assert summary.diffs == 0
    assert db_session.scalars(select(ReconciliationDiff)).all() == []


def test_commission_mismatch_creates_a_diff_and_alert(
    db_session: Session, store: Store, line: OrderLine
) -> None:
    """§7.3: eşik üstü sapma fark kaydı + uyarı üretir."""
    _record(
        db_session,
        store,
        ref=line.external_line_id,
        record_type=SettlementRecordType.COMMISSION,
        amount=D("-216.00"),
    )

    summary = reconciliation.run(db_session, store=store, period=PERIOD)

    assert summary.diffs == 1
    diff = db_session.scalar(select(ReconciliationDiff))
    assert diff is not None
    assert diff.expected == D("200.0000")
    assert diff.actual == D("216.0000")
    assert diff.diff == D("16.0000")
    assert diff.status is DiffStatus.OPEN

    alerts = db_session.scalars(select(Alert).where(Alert.type == reconciliation.DIFF_ALERT)).all()
    assert len(alerts) == 1


def test_matched_record_is_linked_to_the_order_line(
    db_session: Session, store: Store, line: OrderLine
) -> None:
    """Eşleşen kalem sipariş satırına bağlanır (spec §7.1)."""
    record = _record(
        db_session,
        store,
        ref=line.external_line_id,
        record_type=SettlementRecordType.COMMISSION,
        amount=D("-200.00"),
    )

    reconciliation.run(db_session, store=store, period=PERIOD)

    assert record.order_line_id == line.id
    assert record.matched is True


def test_unmatched_record_goes_to_its_own_queue(
    db_session: Session, store: Store, line: OrderLine
) -> None:
    """§7.5: siparişi bulunamayan kalem ayrı kuyrukta; uydurma eşleştirme yok."""
    _record(
        db_session,
        store,
        ref="TY-YOK-123",
        record_type=SettlementRecordType.COMMISSION,
        amount=D("-99.00"),
    )

    summary = reconciliation.run(db_session, store=store, period=PERIOD)

    assert summary.unmatched == 1
    assert summary.unmatched_refs == ["TY-YOK-123"]
    diff = db_session.scalar(select(ReconciliationDiff))
    assert diff is not None
    assert diff.note == "Sipariş satırı eşleşmedi"


def test_penalty_without_an_order_is_not_a_diff(
    db_session: Session, store: Store, line: OrderLine
) -> None:
    """§6.3.7: ceza siparişe bağlanmaz, mağaza gideridir — fark sayılmaz."""
    _record(
        db_session,
        store,
        ref="CEZA-1",
        record_type=SettlementRecordType.PENALTY,
        amount=D("-350.00"),
    )

    summary = reconciliation.run(db_session, store=store, period=PERIOD)

    assert summary.diffs == 0
    assert summary.unmatched == 0


def test_order_reference_matches_single_line_orders(
    db_session: Session, store: Store, line: OrderLine
) -> None:
    """Kalem sipariş numarası taşıyorsa tek satırlı siparişte eşleşme kesindir."""
    order = db_session.scalar(select(Order).where(Order.id == line.order_id))
    assert order is not None
    _record(
        db_session,
        store,
        ref=order.external_order_id,
        record_type=SettlementRecordType.COMMISSION,
        amount=D("-200.00"),
    )

    summary = reconciliation.run(db_session, store=store, period=PERIOD)

    assert summary.matched == 1


def test_order_reference_is_not_guessed_for_multi_line_orders(
    db_session: Session, store: Store, product: Product
) -> None:
    """Çok satırlı siparişte hangi satıra ait olduğu belirsizdir — eşleştirilmez."""
    second = make_product(db_session, store, "KHV-V60-02", cost=D("420.0000"))
    order = make_order(db_session, store, [(product, 1, D("1000.00")), (second, 1, D("890.00"))])
    with system_scope():
        profit.recompute_orders(db_session, order_ids=[order.id])
    _record(
        db_session,
        store,
        ref=order.external_order_id,
        record_type=SettlementRecordType.COMMISSION,
        amount=D("-200.00"),
    )

    summary = reconciliation.run(db_session, store=store, period=PERIOD)

    assert summary.unmatched == 1


def test_cargo_expectation_uses_the_finalised_cost(
    db_session: Session, store: Store, line: OrderLine
) -> None:
    """Kargo beklentisi kesinleşmiş maliyetten gelir; yoksa tahminden."""
    shipment = db_session.scalar(select(Shipment).where(Shipment.order_id == line.order_id))
    assert shipment is not None
    shipment.cargo_cost_actual = D("84.5000")
    shipment.cost_state = CostState.ACTUAL
    db_session.flush()
    _record(
        db_session,
        store,
        ref=line.external_line_id,
        record_type=SettlementRecordType.CARGO,
        amount=D("-84.50"),
    )

    summary = reconciliation.run(db_session, store=store, period=PERIOD)

    assert summary.diffs == 0
    assert summary.within_tolerance == 1


def test_service_fee_expectation_comes_from_the_store(
    db_session: Session, store: Store, line: OrderLine
) -> None:
    """Hizmet bedeli beklentisi mağaza ayarındandır."""
    _record(
        db_session,
        store,
        ref=line.external_line_id,
        record_type=SettlementRecordType.SERVICE_FEE,
        amount=-(store.service_fee_per_order or D("0")),
    )

    summary = reconciliation.run(db_session, store=store, period=PERIOD)

    assert summary.diffs == 0


def test_run_is_idempotent(db_session: Session, store: Store, line: OrderLine) -> None:
    """İkinci koşu aynı kalem için ikinci fark açmaz."""
    _record(
        db_session,
        store,
        ref=line.external_line_id,
        record_type=SettlementRecordType.COMMISSION,
        amount=D("-216.00"),
    )
    reconciliation.run(db_session, store=store, period=PERIOD)

    second = reconciliation.run(db_session, store=store, period=PERIOD)

    assert second.skipped == 1
    assert second.diffs == 0
    assert len(db_session.scalars(select(ReconciliationDiff)).all()) == 1


def test_dry_run_writes_nothing(db_session: Session, store: Store, line: OrderLine) -> None:
    """Önizleme sayar ama yazmaz."""
    _record(
        db_session,
        store,
        ref=line.external_line_id,
        record_type=SettlementRecordType.COMMISSION,
        amount=D("-216.00"),
    )

    summary = reconciliation.run(db_session, store=store, period=PERIOD, dry_run=True)

    assert summary.diffs == 1
    assert db_session.scalars(select(ReconciliationDiff)).all() == []


def test_other_periods_are_not_touched(db_session: Session, store: Store, line: OrderLine) -> None:
    """Dönem filtresi: başka ayın kalemi bu turda işlenmez."""
    _record(
        db_session,
        store,
        ref=line.external_line_id,
        record_type=SettlementRecordType.COMMISSION,
        amount=D("-216.00"),
    )

    summary = reconciliation.run(db_session, store=store, period="2026-07")

    assert summary.records == 0


# --- açıklama akışı (spec §7.4) ----------------------------------------------


def test_diff_can_be_explained_with_a_note(
    db_session: Session, store: Store, line: OrderLine
) -> None:
    """Fark açıklanınca durumu değişir ve not saklanır."""
    _record(
        db_session,
        store,
        ref=line.external_line_id,
        record_type=SettlementRecordType.COMMISSION,
        amount=D("-216.00"),
    )
    reconciliation.run(db_session, store=store, period=PERIOD)
    diff = db_session.scalar(select(ReconciliationDiff))
    assert diff is not None

    updated = reconciliation.explain(
        db_session,
        diff_id=diff.id,
        note="Platform kampanya komisyonu uygulamış; e-posta ile teyit alındı.",
        status=DiffStatus.EXPLAINED,
    )

    assert updated.status is DiffStatus.EXPLAINED
    assert "kampanya" in (updated.note or "")


def test_closing_without_a_note_is_rejected(
    db_session: Session, store: Store, line: OrderLine
) -> None:
    """Açıklamasız kapatılan fark, kapatılmamış farktan daha tehlikelidir."""
    _record(
        db_session,
        store,
        ref=line.external_line_id,
        record_type=SettlementRecordType.COMMISSION,
        amount=D("-216.00"),
    )
    reconciliation.run(db_session, store=store, period=PERIOD)
    diff = db_session.scalar(select(ReconciliationDiff))
    assert diff is not None

    with pytest.raises(reconciliation.ReconciliationError, match="Açıklama zorunlu"):
        reconciliation.explain(db_session, diff_id=diff.id, note="  ", status=DiffStatus.RESOLVED)


def test_marking_back_to_open_is_rejected(
    db_session: Session, store: Store, line: OrderLine
) -> None:
    """`open`a geri döndürme akışı yok — makine insanın kararını geri almaz."""
    _record(
        db_session,
        store,
        ref=line.external_line_id,
        record_type=SettlementRecordType.COMMISSION,
        amount=D("-216.00"),
    )
    reconciliation.run(db_session, store=store, period=PERIOD)
    diff = db_session.scalar(select(ReconciliationDiff))
    assert diff is not None

    with pytest.raises(reconciliation.ReconciliationError, match="explained"):
        reconciliation.explain(db_session, diff_id=diff.id, note="olsun", status=DiffStatus.OPEN)


def test_period_summary_counts_by_status(
    db_session: Session, store: Store, line: OrderLine
) -> None:
    """Dönem özeti açık/açıklanmış/çözülmüş sayılarını verir."""
    _record(
        db_session,
        store,
        ref=line.external_line_id,
        record_type=SettlementRecordType.COMMISSION,
        amount=D("-216.00"),
    )
    reconciliation.run(db_session, store=store, period=PERIOD)

    summary = reconciliation.period_summary(db_session, period=PERIOD)

    assert summary.diff_count == 1
    assert summary.open_count == 1
    assert summary.total_diff == D("16.0000")


# --- API ---------------------------------------------------------------------


@pytest.fixture
def api(db_session: Session, store: Store) -> Iterator[TestClient]:
    """Test oturumuna bağlı API istemcisi."""

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


def test_run_endpoint_previews_then_applies(
    api: TestClient, db_session: Session, store: Store, line: OrderLine
) -> None:
    """Uç önce önizler, sonra yazar."""
    _record(
        db_session,
        store,
        ref=line.external_line_id,
        record_type=SettlementRecordType.COMMISSION,
        amount=D("-216.00"),
    )

    preview = api.post(
        f"/alessi/reconciliation/run?period={PERIOD}&dry_run=true", headers=_headers(api)
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["diffs"] == 1
    assert db_session.scalars(select(ReconciliationDiff)).all() == []

    applied = api.post(
        f"/alessi/reconciliation/run?period={PERIOD}&dry_run=false", headers=_headers(api)
    )
    assert applied.status_code == 200, applied.text
    assert applied.json()["match_rate_pct"] == "100.00"


def test_diffs_endpoint_filters_by_status(
    api: TestClient, db_session: Session, store: Store, line: OrderLine
) -> None:
    """Ekran açık farkları ayrı gösterebilmeli."""
    _record(
        db_session,
        store,
        ref=line.external_line_id,
        record_type=SettlementRecordType.COMMISSION,
        amount=D("-216.00"),
    )
    reconciliation.run(db_session, store=store, period=PERIOD)

    response = api.get(
        f"/alessi/reconciliation/diffs?period={PERIOD}&diff_status=open", headers=_headers(api)
    )

    assert response.status_code == 200, response.text
    assert len(response.json()) == 1


def test_explain_endpoint_requires_a_note(
    api: TestClient, db_session: Session, store: Store, line: OrderLine
) -> None:
    """Şema seviyesinde de not zorunlu (min 3 karakter)."""
    _record(
        db_session,
        store,
        ref=line.external_line_id,
        record_type=SettlementRecordType.COMMISSION,
        amount=D("-216.00"),
    )
    reconciliation.run(db_session, store=store, period=PERIOD)
    diff = db_session.scalar(select(ReconciliationDiff))
    assert diff is not None

    response = api.post(
        f"/alessi/reconciliation/diffs/{diff.id}/explain",
        json={"status": "explained", "note": "x"},
        headers=_headers(api),
    )

    assert response.status_code == 422


def test_explain_endpoint_marks_the_diff(
    api: TestClient, db_session: Session, store: Store, line: OrderLine
) -> None:
    """Açıklama ucu farkı işaretler."""
    _record(
        db_session,
        store,
        ref=line.external_line_id,
        record_type=SettlementRecordType.COMMISSION,
        amount=D("-216.00"),
    )
    reconciliation.run(db_session, store=store, period=PERIOD)
    diff = db_session.scalar(select(ReconciliationDiff))
    assert diff is not None

    response = api.post(
        f"/alessi/reconciliation/diffs/{diff.id}/explain",
        json={"status": "resolved", "note": "Platform düzeltme faturası kesti."},
        headers=_headers(api),
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "resolved"


def test_summary_endpoint(
    api: TestClient, db_session: Session, store: Store, line: OrderLine
) -> None:
    """Dönem özeti ucu."""
    _record(
        db_session,
        store,
        ref=line.external_line_id,
        record_type=SettlementRecordType.COMMISSION,
        amount=D("-216.00"),
    )
    reconciliation.run(db_session, store=store, period=PERIOD)

    response = api.get(f"/alessi/reconciliation/summary?period={PERIOD}", headers=_headers(api))

    assert response.status_code == 200, response.text
    assert response.json()["open_count"] == 1


def test_diff_of_other_brand_is_not_visible(
    api: TestClient, db_session: Session, store: Store, line: OrderLine
) -> None:
    """CLAUDE.md §2: farklar marka kapsamlıdır."""
    _record(
        db_session,
        store,
        ref=line.external_line_id,
        record_type=SettlementRecordType.COMMISSION,
        amount=D("-216.00"),
    )
    reconciliation.run(db_session, store=store, period=PERIOD)

    response = api.get(
        f"/kahveji/reconciliation/diffs?period={PERIOD}", headers=_headers(api, "kahveji")
    )

    assert response.status_code == 200, response.text
    assert response.json() == []


def test_match_rate_counts_previously_matched_records(
    db_session: Session, store: Store, line: OrderLine
) -> None:
    """İkinci koşuda oran düşmez: atlanan kalemler zaten eşleşmiş olanlardır.

    Aksi halde aynı dönemi tekrar koşmak "mutabakat bozuluyor" izlenimi verirdi.
    """
    _record(
        db_session,
        store,
        ref=line.external_line_id,
        record_type=SettlementRecordType.COMMISSION,
        amount=D("-216.00"),
    )
    first = reconciliation.run(db_session, store=store, period=PERIOD)

    second = reconciliation.run(db_session, store=store, period=PERIOD)

    assert first.match_rate_pct == D("100.00")
    assert second.skipped == 1
    assert second.match_rate_pct == D("100.00")
