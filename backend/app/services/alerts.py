"""Uyarı taraması (spec §9 `alert_scan`).

Uyarıların çoğu **olay anında** yazılır: negatif stok stok hareketinde, tarife değişimi
günlük diff'te, MSRP ihlali disiplin taramasında, eşleşmeyen kargo satırı fatura
yüklemesinde, hakediş farkı mutabakat turunda. Bu modül onları tekrar taramaz — aynı uyarı
iki kez üretilirse ekran gürültüye boğulur ve gerçek sinyal kaybolur.

Buradaki tek kontrol, hiçbir akışın yazmadığı bir durumu görünür kılar: **senkron sessizce
durmuş olabilir.** Sync job'ı hata verirse log'a düşer ama kimse log'a bakmıyorsa mağaza
günlerce güncellenmez ve dashboard eski veriyle "doğru" görünür. Bayat `last_synced_at` bu
yüzden uyarı üretir.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.enums import AlertSeverity
from app.models.identity import Store, StoreCredential
from app.models.results import Alert

log = get_logger("services.alerts")

STALE_SYNC_ALERT = "stale_sync"
DEFAULT_STALE_HOURS = 6
"""Sipariş senkronu 15 dakikada bir koşuyor; 6 saat sessizlik arıza sayılır."""


def scan_stale_syncs(session: Session, *, older_than_hours: int = DEFAULT_STALE_HOURS) -> int:
    """Uzun süredir senkronlanmamış mağazalar için uyarı yazar.

    Yalnızca **credential'ı tanımlı** mağazalar taranır: bağlantısı hiç kurulmamış mağaza
    "senkron durdu" demek değildir, henüz başlamamıştır (Ayarlar ekranı zaten bunu
    "Girilmedi" olarak gösteriyor).

    Aynı mağaza için açık (acknowledge edilmemiş) bir uyarı varsa ikincisi yazılmaz —
    saatlik tarama aynı arızayı her saat tekrar bildirmez.
    """
    now = datetime.now(UTC)
    threshold = now - timedelta(hours=older_than_hours)
    written = 0

    rows = session.execute(
        select(Store, StoreCredential)
        .join(StoreCredential, StoreCredential.store_id == Store.id)
        .where(Store.is_active.is_(True))
    ).all()

    for store, _credential in rows:
        last_synced = store.last_synced_at
        if last_synced is not None and last_synced > threshold:
            continue
        if _has_open_alert(session, store):
            continue

        session.add(
            Alert(
                tenant_id=store.tenant_id,
                brand_id=store.brand_id,
                type=STALE_SYNC_ALERT,
                severity=AlertSeverity.WARNING,
                entity_ref=f"store:{store.id}",
                message=(
                    f"{store.name} mağazası {older_than_hours} saattir senkronlanmadı"
                    + (
                        f" (son senkron: {last_synced:%d.%m.%Y %H:%M})."
                        if last_synced
                        else " (hiç senkronlanmadı)."
                    )
                    + " Bağlantı bilgilerini ve worker'ı kontrol edin."
                ),
                created_at=now,
            )
        )
        written += 1

    log.info("alerts.stale_sync_scanned", scanned=len(rows), written=written)
    return written


def _has_open_alert(session: Session, store: Store) -> bool:
    """Bu mağaza için kapatılmamış bayat-senkron uyarısı var mı."""
    return (
        session.scalar(
            select(Alert.id).where(
                Alert.type == STALE_SYNC_ALERT,
                Alert.entity_ref == f"store:{store.id}",
                Alert.acknowledged_at.is_(None),
            )
        )
        is not None
    )
