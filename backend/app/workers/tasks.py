"""Celery görevleri — sync zamanlaması (spec §9).

Beat programı KVN-06'da (normalize pipeline) tamamlanacak; burada manuel/zamanlanmış
tetiklenebilen sync görevi tanımlıdır.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from app.core.db import SessionLocal
from app.core.logging import get_logger
from app.services.sync import load_store_for_sync, sync_store
from app.workers.celery_app import celery_app

log = get_logger("workers.sync")


@celery_app.task(name="kavun.sync_store")
def sync_store_task(store_id: str) -> dict[str, Any]:
    """Bir mağazayı senkronlar ve özet metriği döndürür."""
    with SessionLocal() as session:
        store = load_store_for_sync(session, uuid.UUID(store_id))
        if store is None:
            log.warning("sync.store_not_found", store_id=store_id)
            return {"store_id": store_id, "error": "store_not_found"}
        summary = asyncio.run(sync_store(session, store))
    return summary.as_dict()
