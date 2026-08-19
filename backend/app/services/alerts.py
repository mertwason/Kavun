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

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
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


# --- listeleme, özet ve acknowledge (spec §10.6) -----------------------------


class AlertNotFoundError(LookupError):
    """Uyarı bulunamadı (ya da aktif markaya ait değil)."""


@dataclass(frozen=True)
class AlertCounts:
    """Uyarı özeti — ekranın KPI şeridi."""

    open: int
    acknowledged: int
    critical_open: int
    warning_open: int
    info_open: int

    @property
    def total(self) -> int:
        return self.open + self.acknowledged


def alerts(
    session: Session,
    *,
    severity: AlertSeverity | None = None,
    alert_type: str | None = None,
    acknowledged: bool | None = None,
    limit: int = 200,
) -> list[Alert]:
    """Aktif markanın uyarıları — en yeni önce.

    `acknowledged=None` hepsini getirir; `False` yalnızca açıkları, `True` kapatılmışları.
    Kapatılmış uyarı **silinmez**: filtreyle her zaman geri görülebilir.
    """
    statement = select(Alert).order_by(Alert.created_at.desc()).limit(limit)
    if severity is not None:
        statement = statement.where(Alert.severity == severity)
    if alert_type:
        statement = statement.where(Alert.type == alert_type)
    if acknowledged is True:
        statement = statement.where(Alert.acknowledged_at.is_not(None))
    elif acknowledged is False:
        statement = statement.where(Alert.acknowledged_at.is_(None))
    return list(session.scalars(statement))


def counts(session: Session) -> AlertCounts:
    """Seviye bazlı açık/kapalı sayımlar."""
    rows = session.execute(
        select(Alert.severity, Alert.acknowledged_at.is_(None), func.count()).group_by(
            Alert.severity, Alert.acknowledged_at.is_(None)
        )
    ).all()

    open_by_severity: dict[AlertSeverity, int] = {}
    open_total = 0
    acknowledged_total = 0
    for severity, is_open, count in rows:
        if is_open:
            open_by_severity[severity] = open_by_severity.get(severity, 0) + count
            open_total += count
        else:
            acknowledged_total += count

    return AlertCounts(
        open=open_total,
        acknowledged=acknowledged_total,
        critical_open=open_by_severity.get(AlertSeverity.CRITICAL, 0),
        warning_open=open_by_severity.get(AlertSeverity.WARNING, 0),
        info_open=open_by_severity.get(AlertSeverity.INFO, 0),
    )


def types(session: Session) -> list[tuple[str, int]]:
    """Markada geçen uyarı türleri ve **açık** sayıları — ekranın filtre şeridi.

    Sayı türün yanında durur ("Marj · 2"); kapatılmış uyarı sayıya girmez, çünkü şerit
    "şu an ilgilenilecek ne var" sorusunu yanıtlar. Hepsi kapatılmış bir tür listede
    kalır (0 ile), yoksa filtre kullanıcının altından kayar.
    """
    rows = session.execute(
        select(
            Alert.type,
            func.count().filter(Alert.acknowledged_at.is_(None)),
        )
        .group_by(Alert.type)
        .order_by(Alert.type)
    ).all()
    return [(alert_type, int(open_count)) for alert_type, open_count in rows]


def acknowledge(session: Session, alert_id: uuid.UUID, *, at: datetime | None = None) -> Alert:
    """Uyarıyı "görüldü" olarak işaretler.

    **Tek yönlüdür ve idempotenttir:** ikinci kez çağrılırsa ilk damga korunur, "görüldü"
    zamanı geriye alınmaz. Geri alma yok çünkü acknowledge bir karar değil, bir okuma
    kaydıdır; yanlışlıkla kapatılan uyarı silinmez, "Kapatılmış" filtresinde durur.
    """
    alert = session.scalar(select(Alert).where(Alert.id == alert_id))
    if alert is None:
        raise AlertNotFoundError(str(alert_id))
    if alert.acknowledged_at is None:
        alert.acknowledged_at = at or datetime.now(UTC)
        session.flush()
    return alert
