"""KVN-EK-05: Faz 2 veri borusu — iade, hakediş, kargo faturası (spec §4, §9).

Connector'ın ayrıştırdığı ham kayıtların domain tablolarına **doğru** düştüğünü doğrular.
Canlı API'ye çıkılmaz; olaylar `raw_events`'e yazılıp normalize edilir (KVN-06 disiplini).
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.context import system_scope
from app.models.enums import CostState, SettlementRecordType
from app.models.identity import Store, StoreCredential
from app.models.results import Alert
from app.models.transactions import (
    CargoInvoice,
    Order,
    OrderLine,
    RawEvent,
    Return,
    SettlementRecord,
    Shipment,
)
from app.services import alerts as alert_service
from app.services import normalize as normalize_service
from tests.profit_factories import make_order, make_product, make_store

D = Decimal
FIXTURES = Path(__file__).parent / "fixtures" / "trendyol"


def load_fixture(name: str) -> dict[str, Any]:
    body: dict[str, Any] = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    return body


@pytest.fixture(autouse=True)
def system_context() -> Iterator[None]:
    """Normalize bir sistem işidir (KVN-03 guard'ı)."""
    with system_scope():
        yield


@pytest.fixture
def store(db_session: Session) -> Store:
    return make_store(db_session)


def _event(store: Store, event_type: str, external_id: str, payload: dict[str, Any]) -> RawEvent:
    return RawEvent(
        tenant_id=store.tenant_id,
        store_id=store.id,
        event_type=event_type,
        external_id=external_id,
        payload=payload,
        fetched_at=datetime.now(UTC),
    )


def _normalize(db_session: Session, store: Store, event: RawEvent) -> Any:
    db_session.add(event)
    db_session.flush()
    return normalize_service.normalize_events(db_session, [event])


# --- iadeler -----------------------------------------------------------------


def _order_with_line(db_session: Session, store: Store, external_line_id: str) -> OrderLine:
    """Sipariş + satır kurar ve satırın kanal id'sini iade fixture'ıyla hizalar."""
    product = make_product(db_session, store, "KHV-BLD-ESP-250", cost=D("120.0000"))
    product.barcode = "8690000000011"
    order = make_order(db_session, store, [(product, 2, D("579.80"))])
    order.external_order_id = "TY-2026-000117"
    line = db_session.scalar(select(OrderLine).where(OrderLine.order_id == order.id))
    assert line is not None
    line.external_line_id = external_line_id
    db_session.flush()
    return line


def test_accepted_claim_becomes_a_return_row(db_session: Session, store: Store) -> None:
    """Kabul edilen iade `returns`'e düşer; adet ve tutar talepten gelir."""
    line = _order_with_line(db_session, store, "880001")
    claim = load_fixture("claims_page0")["content"][0]

    _normalize(db_session, store, _event(store, "return", "CLM-90010001", claim))

    saved = db_session.scalar(select(Return).where(Return.order_line_id == line.id))
    assert saved is not None
    assert saved.qty == 2
    assert saved.refund_amount == D("579.8000")
    assert saved.reason == "Beğenmedim"


def test_rejected_claim_writes_no_return(db_session: Session, store: Store) -> None:
    """Reddedilen talep iade sayılmaz — ciro haksız yere düşmemeli."""
    _order_with_line(db_session, store, "880002")
    claim = load_fixture("claims_page0")["content"][1]

    summary = _normalize(db_session, store, _event(store, "return", "CLM-90010002", claim))

    assert db_session.scalar(select(Return)) is None
    assert summary.skipped.get("iade_reddedildi") == 1


def test_claim_without_matching_line_is_counted_not_guessed(
    db_session: Session, store: Store
) -> None:
    """Satır bulunamazsa iade YAZILMAZ; sessizce de geçilmez."""
    claim = load_fixture("claims_page0")["content"][0]

    summary = _normalize(db_session, store, _event(store, "return", "CLM-X", claim))

    assert db_session.scalar(select(Return)) is None
    assert summary.skipped.get("iade_satir_yok") == 1


def test_same_claim_twice_does_not_duplicate(db_session: Session, store: Store) -> None:
    """Aynı iade iki kez işlenirse kopya kayıt oluşmaz (idempotency)."""
    _order_with_line(db_session, store, "880001")
    claim = load_fixture("claims_page0")["content"][0]

    _normalize(db_session, store, _event(store, "return", "CLM-90010001", claim))
    _normalize(db_session, store, _event(store, "return", "CLM-90010001-b", claim))

    assert len(list(db_session.scalars(select(Return)))) == 1


def test_return_defaults_to_not_restocked(db_session: Session, store: Store) -> None:
    """Malın yeniden satılabilirliği kanıtsız varsayılmaz (kârı şişirirdi)."""
    _order_with_line(db_session, store, "880001")
    claim = load_fixture("claims_page0")["content"][0]

    _normalize(db_session, store, _event(store, "return", "CLM-90010001", claim))

    saved = db_session.scalar(select(Return))
    assert saved is not None
    assert saved.restocked is False


# --- hakediş -----------------------------------------------------------------


def test_settlement_rows_are_written_with_signed_amounts(db_session: Session, store: Store) -> None:
    """Kesinti negatif, satış pozitif; tip içeri enum'a çevrilir."""
    for row in load_fixture("settlements_page0")["content"]:
        _normalize(db_session, store, _event(store, "settlement", str(row["id"]), row))

    saved = {record.external_ref: record for record in db_session.scalars(select(SettlementRecord))}
    assert saved["STL-2026-08-0001"].record_type is SettlementRecordType.SALE
    assert saved["STL-2026-08-0001"].amount == D("289.9000")
    assert saved["STL-2026-08-0002"].record_type is SettlementRecordType.COMMISSION
    assert saved["STL-2026-08-0002"].amount == D("-46.3800")
    assert saved["STL-2026-08-0004"].record_type is SettlementRecordType.CARGO


def test_settlement_is_upserted_not_duplicated(db_session: Session, store: Store) -> None:
    """Aynı `external_ref` ikinci kez gelirse güncellenir, kopyalanmaz."""
    row = load_fixture("settlements_page0")["content"][0]
    _normalize(db_session, store, _event(store, "settlement", "STL-1", row))

    changed = {**row, "credit": 300.0}
    _normalize(db_session, store, _event(store, "settlement", "STL-1b", changed))

    records = list(db_session.scalars(select(SettlementRecord)))
    assert len(records) == 1
    assert records[0].amount == D("300.0000")


def test_settlement_without_reference_is_skipped(db_session: Session, store: Store) -> None:
    """Referansı olmayan kalem yazılamaz — tekillik anahtarı odur."""
    summary = _normalize(db_session, store, _event(store, "settlement", "x", {"credit": 5}))

    assert db_session.scalar(select(SettlementRecord)) is None
    assert summary.skipped.get("hakedis_ref_yok") == 1


# --- kargo faturası ----------------------------------------------------------


def _cargo_event_payload() -> dict[str, Any]:
    return {
        "invoice": load_fixture("otherfinancials_deductions")["content"][0],
        "items": load_fixture("cargo_invoice_items")["content"],
    }


def _shipped_order(db_session: Session, store: Store, tracking: str) -> Order:
    product = make_product(db_session, store, f"SKU-{tracking}", cost=D("100.0000"))
    order = make_order(db_session, store, [(product, 1, D("500.00"))])
    order.external_order_id = "TY-2026-000117"
    shipment = db_session.scalar(select(Shipment).where(Shipment.order_id == order.id))
    assert shipment is not None
    shipment.tracking_no = tracking
    shipment.cost_state = CostState.ESTIMATED
    shipment.cargo_cost_estimated = D("40.0000")
    db_session.flush()
    return order


def test_cargo_invoice_finalises_matching_shipment(db_session: Session, store: Store) -> None:
    """Takip numarasıyla eşleşen gönderinin maliyeti kesinleşir (spec §6.2)."""
    order = _shipped_order(db_session, store, "7300000000011")

    _normalize(db_session, store, _event(store, "cargo_invoice", "KRG-1", _cargo_event_payload()))

    shipment = db_session.scalar(select(Shipment).where(Shipment.order_id == order.id))
    assert shipment is not None
    assert shipment.cost_state is CostState.ACTUAL
    assert shipment.cargo_cost_actual == D("54.9000")
    assert shipment.desi_invoiced == D("0.80")


def test_cargo_invoice_never_overwrites_finalised_cost(db_session: Session, store: Store) -> None:
    """Kesinleşmiş maliyet ikinci faturayla ezilmez (KVN-EK-02 kuralı)."""
    order = _shipped_order(db_session, store, "7300000000011")
    shipment = db_session.scalar(select(Shipment).where(Shipment.order_id == order.id))
    assert shipment is not None
    shipment.cost_state = CostState.ACTUAL
    shipment.cargo_cost_actual = D("99.0000")
    db_session.flush()

    _normalize(db_session, store, _event(store, "cargo_invoice", "KRG-1", _cargo_event_payload()))

    assert shipment.cargo_cost_actual == D("99.0000")


def test_cargo_invoice_records_unmatched_lines(db_session: Session, store: Store) -> None:
    """Eşleşmeyen kalem uydurulmaz; fatura kaydında "eslesmedi" olarak durur."""
    summary = _normalize(
        db_session, store, _event(store, "cargo_invoice", "KRG-1", _cargo_event_payload())
    )

    invoice = db_session.scalar(select(CargoInvoice))
    assert invoice is not None
    assert invoice.invoice_no == "KRG-2026-08-0001"
    assert summary.skipped.get("kargo_gonderi_yok") == 3
    assert all(row["sonuc"] == "eslesmedi" for row in invoice.lines)


def test_same_cargo_invoice_is_processed_once(db_session: Session, store: Store) -> None:
    """Aynı fatura ikinci kez gelirse yeniden işlenmez."""
    _shipped_order(db_session, store, "7300000000011")
    payload = _cargo_event_payload()

    _normalize(db_session, store, _event(store, "cargo_invoice", "KRG-1", payload))
    summary = _normalize(db_session, store, _event(store, "cargo_invoice", "KRG-1b", payload))

    assert len(list(db_session.scalars(select(CargoInvoice)))) == 1
    assert summary.skipped.get("kargo_faturasi_zaten_islenmis") == 1


def test_cargo_invoice_event_is_reparsed_from_raw_payload(
    db_session: Session, store: Store
) -> None:
    """Ham olaydan yeniden kurulabilir (replay disiplini)."""
    parsed = normalize_service._parse_cargo_invoice_event(_cargo_event_payload())

    assert parsed.invoice_no == "KRG-2026-08-0001"
    assert parsed.period == "2026-08"
    assert parsed.total == D("204.3")


# --- bayat senkron uyarısı ---------------------------------------------------


def _with_credentials(db_session: Session, store: Store) -> None:
    db_session.add(StoreCredential(store_id=store.id, encrypted_payload=b"x"))
    db_session.flush()


def test_stale_sync_raises_an_alert(db_session: Session, store: Store) -> None:
    """Uzun süredir senkronlanmayan mağaza uyarı üretir (spec §9 `alert_scan`)."""
    _with_credentials(db_session, store)
    store.last_synced_at = datetime.now(UTC) - timedelta(hours=12)
    db_session.flush()

    written = alert_service.scan_stale_syncs(db_session)

    assert written == 1
    alert = db_session.scalar(select(Alert).where(Alert.type == alert_service.STALE_SYNC_ALERT))
    assert alert is not None
    assert str(store.id) in (alert.entity_ref or "")


def test_fresh_sync_raises_no_alert(db_session: Session, store: Store) -> None:
    """Yeni senkronlanmış mağaza uyarı üretmez."""
    _with_credentials(db_session, store)
    store.last_synced_at = datetime.now(UTC)
    db_session.flush()

    assert alert_service.scan_stale_syncs(db_session) == 0


def test_store_without_credentials_is_not_alerted(db_session: Session, store: Store) -> None:
    """Bağlantısı hiç kurulmamış mağaza "senkron durdu" değildir."""
    store.last_synced_at = None
    db_session.flush()

    assert alert_service.scan_stale_syncs(db_session) == 0


def test_stale_sync_alert_is_not_repeated_every_hour(db_session: Session, store: Store) -> None:
    """Açık uyarı varken ikincisi yazılmaz — saatlik tarama tekrar bildirmez."""
    _with_credentials(db_session, store)
    store.last_synced_at = None
    db_session.flush()

    assert alert_service.scan_stale_syncs(db_session) == 1
    assert alert_service.scan_stale_syncs(db_session) == 0
    assert len(list(db_session.scalars(select(Alert)))) == 1


# --- zamanlama (spec §9) -----------------------------------------------------


def test_beat_schedule_covers_every_spec_job() -> None:
    """Spec §9'daki zamanlanmış işlerin tamamı beat programında olmalı."""
    from app.workers.celery_app import celery_app

    tasks = {entry["task"] for entry in celery_app.conf.beat_schedule.values()}

    assert {
        "kavun.sync_all_stores",
        "kavun.normalize_pending",
        "kavun.recompute_pending_profits",
        "kavun.reconciliation_run",
        "kavun.alert_scan",
        "kavun.detect_commission_changes",
        "kavun.record_stock_movements",
    } <= tasks


def test_sync_all_stores_skips_stores_without_credentials(
    db_session: Session, store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Credential'ı olmayan mağaza kuyruğa alınmaz — boşuna 401 toplanmaz."""
    from app.workers import tasks as worker_tasks

    queued: list[str] = []
    monkeypatch.setattr(
        worker_tasks.sync_store_task,
        "delay",
        lambda store_id, **kwargs: queued.append(store_id),
    )

    class _Session:
        def __enter__(self) -> Session:
            return db_session

        def __exit__(self, *args: object) -> None:
            return None

    monkeypatch.setattr("app.workers.tasks.SessionLocal", _Session)

    result = worker_tasks.sync_all_stores_task()

    assert result["queued"] == 0
    assert result["skipped"] >= 1
    assert queued == []


def test_sync_all_stores_queues_configured_store(
    db_session: Session, store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Credential'ı olan mağaza kuyruğa alınır."""
    from app.workers import tasks as worker_tasks

    _with_credentials(db_session, store)
    queued: list[str] = []

    class _Session:
        def __enter__(self) -> Session:
            return db_session

        def __exit__(self, *args: object) -> None:
            return None

    monkeypatch.setattr("app.workers.tasks.SessionLocal", _Session)
    monkeypatch.setattr(
        worker_tasks.sync_store_task,
        "delay",
        lambda store_id, **kwargs: queued.append(store_id),
    )

    result = worker_tasks.sync_all_stores_task()

    assert result["queued"] == 1
    assert queued == [str(store.id)]


def test_alert_scan_task_writes_alerts(
    db_session: Session, store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Saatlik tarama görevi uyarıyı gerçekten yazar."""
    from app.workers import tasks as worker_tasks

    _with_credentials(db_session, store)
    store.last_synced_at = None
    db_session.flush()

    class _Session:
        def __enter__(self) -> Session:
            return db_session

        def __exit__(self, *args: object) -> None:
            return None

    monkeypatch.setattr("app.workers.tasks.SessionLocal", _Session)

    assert worker_tasks.alert_scan_task()["alerts"] == 1


def test_reconciliation_task_defaults_to_current_period(
    db_session: Session, store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dönem verilmezse içinde bulunulan ay mutabakatlanır."""
    from app.workers import tasks as worker_tasks

    class _Session:
        def __enter__(self) -> Session:
            return db_session

        def __exit__(self, *args: object) -> None:
            return None

    monkeypatch.setattr("app.workers.tasks.SessionLocal", _Session)

    result = worker_tasks.reconciliation_run_task()

    assert result["period"] == datetime.now(UTC).strftime("%Y-%m")


# --- kalan worker görevleri (coverage hedefi: `workers/tasks.py` ≥ %80) ------


@pytest.fixture
def patched_session(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> Iterator[pytest.MonkeyPatch]:
    """Worker görevleri kendi oturumunu açar; testte mevcut oturuma bağlanır."""

    class _Session:
        def __enter__(self) -> Session:
            return db_session

        def __exit__(self, *args: object) -> None:
            return None

    monkeypatch.setattr("app.workers.tasks.SessionLocal", _Session)
    yield monkeypatch


def test_sync_store_task_reports_unknown_store(patched_session: pytest.MonkeyPatch) -> None:
    """Olmayan mağaza sessizce başarı sayılmaz."""
    from app.workers import tasks as worker_tasks

    result = worker_tasks.sync_store_task(str(uuid.uuid4()))

    assert result["error"] == "store_not_found"


def test_sync_store_task_chains_normalize(
    db_session: Session, store: Store, patched_session: pytest.MonkeyPatch
) -> None:
    """Başarılı sync normalize zincirini tetikler (spec §9)."""
    from app.workers import tasks as worker_tasks

    chained: list[str] = []
    patched_session.setattr(
        worker_tasks.normalize_pending_task, "delay", lambda store_id: chained.append(store_id)
    )

    async def _fake_sync(session: Session, target: Store, **kwargs: object) -> Any:
        from app.services.sync import SyncSummary

        return SyncSummary(store_id=target.id, channel="trendyol")

    patched_session.setattr("app.workers.tasks.sync_store", _fake_sync)

    worker_tasks.sync_store_task(str(store.id))

    assert chained == [str(store.id)]


def test_normalize_pending_task_runs(
    db_session: Session, store: Store, patched_session: pytest.MonkeyPatch
) -> None:
    """Normalize görevi özet döndürür."""
    from app.workers import tasks as worker_tasks

    result = worker_tasks.normalize_pending_task(str(store.id))

    assert "processed_events" in result


def test_recompute_pending_profits_task_runs(
    db_session: Session, store: Store, patched_session: pytest.MonkeyPatch
) -> None:
    """Kâr hesabı görevi özet döndürür."""
    from app.workers import tasks as worker_tasks

    result = worker_tasks.recompute_pending_profits_task()

    assert "orders" in result


def test_partition_task_creates_future_partitions(
    db_session: Session, patched_session: pytest.MonkeyPatch
) -> None:
    """Gelecek ayların partition'ları açılır (KVN-02 riski)."""
    from app.workers import tasks as worker_tasks

    result = worker_tasks.ensure_raw_event_partitions_task(months_ahead=1)

    assert len(result["partitions"]) == 2


def test_detect_commission_changes_task_runs(
    db_session: Session, store: Store, patched_session: pytest.MonkeyPatch
) -> None:
    """Tarife diff görevi sayaç döndürür."""
    from app.workers import tasks as worker_tasks

    result = worker_tasks.detect_commission_changes()

    assert set(result) == {"detected", "alerts"}


def test_check_price_discipline_task_runs(
    db_session: Session, store: Store, patched_session: pytest.MonkeyPatch
) -> None:
    """Fiyat disiplini taraması bayrağı kapalı markayı atlar, hata vermez."""
    from app.workers import tasks as worker_tasks

    result = worker_tasks.check_price_discipline()

    assert "alerts" in result


def test_record_stock_movements_task_runs(
    db_session: Session, store: Store, patched_session: pytest.MonkeyPatch
) -> None:
    """Stok hareketi görevi satış/iade sayaçlarını döndürür."""
    from app.workers import tasks as worker_tasks

    result = worker_tasks.record_stock_movements()

    assert set(result) == {"sale_out", "return_in"}
