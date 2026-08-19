"""Celery görevleri — sync, normalize, kâr hesabı ve tarife diff'i (spec §9, §12B.3)."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select

from app.core.context import system_scope
from app.core.db import SessionLocal
from app.core.logging import get_logger
from app.models.partitions import ensure_monthly_partition, month_bounds
from app.services.normalize import normalize_pending
from app.services.profit import recompute_pending
from app.services.sync import load_store_for_sync, sync_store
from app.workers.celery_app import celery_app

log = get_logger("workers.sync")


@celery_app.task(name="kavun.sync_store")
def sync_store_task(store_id: str, *, normalize: bool = True) -> dict[str, Any]:
    """Bir mağazayı senkronlar; başarılıysa normalize zincirini tetikler (spec §9)."""
    with SessionLocal() as session:
        store = load_store_for_sync(session, uuid.UUID(store_id))
        if store is None:
            log.warning("sync.store_not_found", store_id=store_id)
            return {"store_id": store_id, "error": "store_not_found"}
        summary = asyncio.run(sync_store(session, store))

    if normalize and summary.ok:
        normalize_pending_task.delay(store_id)
    return summary.as_dict()


@celery_app.task(name="kavun.normalize_pending")
def normalize_pending_task(store_id: str | None = None) -> dict[str, Any]:
    """İşlenmemiş ham olayları domain tablolarına aktarır (KVN-06)."""
    with SessionLocal() as session:
        summary = normalize_pending(session, store_id=uuid.UUID(store_id) if store_id else None)
    return summary.as_dict()


@celery_app.task(name="kavun.recompute_pending_profits")
def recompute_pending_profits_task() -> dict[str, Any]:
    """Kâr kaydı olmayan satırların kârını hesaplar (spec §9)."""
    with SessionLocal() as session:
        summary = recompute_pending(session)
    return summary.as_dict()


@celery_app.task(name="kavun.ensure_raw_event_partitions")
def ensure_raw_event_partitions_task(months_ahead: int = 3) -> dict[str, Any]:
    """`raw_events` için önümüzdeki ayların partition'larını açar.

    KVN-02'de not edilen riskin kapatılması: migration'ın açtığı pencere dolduğunda
    yazılan olaylar DEFAULT partition'a düşerdi.
    """
    created: list[str] = []
    with SessionLocal() as session:
        connection = session.connection()
        cursor = datetime.now(UTC).date()
        for _ in range(months_ahead + 1):
            created.append(ensure_monthly_partition(connection, cursor))
            cursor = month_bounds(cursor)[1]
        session.commit()
    log.info("partitions.ensured", partitions=created)
    return {"partitions": created}


@celery_app.task(name="kavun.detect_commission_changes")
def detect_commission_changes() -> dict[str, int]:
    """Günlük tarife diff'i: değişen oran → `commission_changes` + alert (spec §12B.3)."""
    from app.models.identity import Store
    from app.services import tariffs

    detected = 0
    alerts = 0
    with SessionLocal() as session, system_scope():
        for store in session.scalars(select(Store)).all():
            summary = tariffs.detect_changes(session, store=store, on_date=date.today())
            detected += summary.detected
            alerts += summary.alerts
        session.commit()

    log.info("tariffs.daily_diff", detected=detected, alerts=alerts)
    return {"detected": detected, "alerts": alerts}


@celery_app.task(name="kavun.record_stock_movements")
def record_stock_movements() -> dict[str, int]:
    """Satış ve iade hareketlerini stok defterine yazar (spec §12C.1)."""
    from app.services.inventory import record_returns, record_sales

    with SessionLocal() as session, system_scope():
        sales = record_sales(session)
        returns = record_returns(session)
        session.commit()

    log.info("inventory.movements_recorded", sale_out=sales.sale_out, return_in=returns.return_in)
    return {"sale_out": sales.sale_out, "return_in": returns.return_in}
