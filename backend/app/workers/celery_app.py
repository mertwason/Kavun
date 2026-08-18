"""Celery uygulaması. Sync/hesap job'ları KVN-05'ten itibaren eklenir (spec §9)."""

from __future__ import annotations

from celery import Celery

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger

settings = get_settings()
configure_logging(settings.log_level)
log = get_logger("worker")

celery_app = Celery(
    "kavun",
    broker=settings.redis_url,
    backend=settings.redis_url,
    # Görev modülleri açıkça listelenir; aksi halde worker görevi "unregistered" sayar.
    include=["app.workers.tasks"],
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Europe/Istanbul",
    enable_utc=True,
    task_track_started=True,
    worker_hijack_root_logger=False,
)


@celery_app.task(name="kavun.ping")
def ping() -> str:
    """Worker'ın broker'a bağlı ve görev alabilir olduğunu doğrular."""
    log.info("worker.ping")
    return "pong"
