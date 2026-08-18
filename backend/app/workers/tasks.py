"""Celery görevleri — sync zamanlaması (spec §9).

Beat programı KVN-06'da (normalize pipeline) tamamlanacak; burada manuel/zamanlanmış
tetiklenebilen sync görevi tanımlıdır.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

from app.core.db import SessionLocal
from app.core.logging import get_logger
from app.models.partitions import ensure_monthly_partition, month_bounds
from app.services.normalize import normalize_pending
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
