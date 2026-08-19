"""Celery uygulaması. Sync/hesap job'ları KVN-05'ten itibaren eklenir (spec §9)."""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

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


# Zamanlanmış işler (spec §9). Sipariş senkronu mağaza bazında tetiklendiğinden
# beat yalnızca zincirin ortak adımlarını çalıştırır; kanal bazlı sync programı
# mağaza sayısı arttığında KVN-20'de gözden geçirilecek.
celery_app.conf.beat_schedule = {
    "normalize-pending": {
        "task": "kavun.normalize_pending",
        "schedule": crontab(minute="*/15"),
    },
    "recompute-pending-profits": {
        "task": "kavun.recompute_pending_profits",
        "schedule": crontab(minute="*/30"),
    },
    # Spec §12C.1: satış/iade stok hareketleri (kâr hesabından sonra).
    "record-stock-movements": {
        "task": "kavun.record_stock_movements",
        "schedule": crontab(minute="*/45"),
    },
    # Spec §12B.3: günlük tarife snapshot diff'i (03:00 sync'in parçası).
    "detect-commission-changes": {
        "task": "kavun.detect_commission_changes",
        "schedule": crontab(hour=3, minute=0),
    },
    "check-price-discipline": {
        "task": "kavun.check_price_discipline",
        "schedule": crontab(hour=4, minute=0),
    },
    "ensure-raw-event-partitions": {
        "task": "kavun.ensure_raw_event_partitions",
        "schedule": crontab(hour=2, minute=30),
    },
}


@celery_app.task(name="kavun.ping")
def ping() -> str:
    """Worker'ın broker'a bağlı ve görev alabilir olduğunu doğrular."""
    log.info("worker.ping")
    return "pong"
