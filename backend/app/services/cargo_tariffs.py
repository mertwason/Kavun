"""Kargo tarifesi servisi — DB katmanı (spec §6.1, §10.7).

Hesap `app/engine/cargo.py`'de saf fonksiyonlarda; burada yalnızca okuma/yazma ve
tarife değişikliğinin etkisini gösteren "yeniden tahmin" akışı var (CLAUDE.md §1).

## Tarife değişikliği geçmişi ezmez

Bir bant eklendiğinde/kapatıldığında **geçmiş gönderilerin tahmini kendiliğinden
değişmez**. Spec §6.2 yeniden hesap tetikleyicilerini sayıyor ve tarife değişikliği o
listede yok; sessizce geçmişe dokunmak "dün gördüğüm kâr bugün neden farklı" sorusunu
doğurur. Bunun yerine **açık bir eylem** var: `reestimate()` — yalnızca `ESTIMATED`
durumdaki gönderileri yeniler, `ACTUAL` olanlara ASLA dokunmaz ve değişen kârı
`profit_revisions`'a `kargo_tarifesi` gerekçesiyle yazar.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.context import current_context
from app.core.logging import get_logger
from app.engine import cargo as engine
from app.models.catalog import CargoTariff
from app.models.enums import CostState
from app.models.transactions import Order, Shipment
from app.services.profit import recompute_orders

log = get_logger("services.cargo_tariffs")

ZERO = Decimal("0")
REESTIMATE_REASON = "kargo_tarifesi"


class TariffNotFoundError(LookupError):
    """Tarife satırı bulunamadı (ya da aktif markaya ait değil)."""


class InvalidBandError(ValueError):
    """Bant aralığı geçersiz."""


@dataclass
class ReestimateSummary:
    """Yeniden tahmin sonucu — `dry_run` ile gerçek koşuda aynı yapı."""

    dry_run: bool = True
    shipments: int = 0
    """Taranan `ESTIMATED` gönderi sayısı."""

    changed: int = 0
    skipped_actual: int = 0
    """Kesinleşmiş olduğu için dokunulmayan gönderi sayısı."""

    delta: Decimal = ZERO
    """Yeni tahmin − eski tahmin toplamı. Pozitif = kargo gideri arttı, kâr düşecek."""

    orders: list[uuid.UUID] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "dry_run": self.dry_run,
            "shipments": self.shipments,
            "changed": self.changed,
            "skipped_actual": self.skipped_actual,
            "delta": str(self.delta),
        }


def _brand_id() -> uuid.UUID | None:
    context = current_context()
    return None if context is None else context.brand_id


def tariffs(session: Session, *, include_closed: bool = False) -> list[CargoTariff]:
    """Aktif markanın tarife bantları; varsayılan olarak yalnızca yürürlükte olanlar."""
    statement = select(CargoTariff).order_by(
        CargoTariff.carrier.nulls_first(), CargoTariff.desi_min
    )
    if not include_closed:
        statement = statement.where(CargoTariff.valid_to.is_(None))
    return list(session.scalars(statement))


def bands_for_brand(
    session: Session, brand_id: uuid.UUID, *, on: date | None = None
) -> list[engine.Band]:
    """Belirtilen markanın bantları — markayı AÇIKÇA filtreler.

    Normalize/sync gibi işler `system_scope()` altında koşar; orada guard marka filtresi
    aramaz, dolayısıyla `select(CargoTariff)` tüm markaların bantlarını getirir. Kahveji'nin
    tarifesiyle Alessi'nin kargosunu hesaplamak sessiz ve ölçülemez bir hata olurdu.
    """
    rows = session.scalars(
        select(CargoTariff).where(CargoTariff.brand_id == brand_id).order_by(CargoTariff.desi_min)
    )
    return _to_bands(rows, on=on)


def bands(session: Session, *, on: date | None = None) -> list[engine.Band]:
    """Aktif markanın bantları (istek bağlamı içinde kullanılır)."""
    return _to_bands(tariffs(session, include_closed=True), on=on)


def _to_bands(rows: Iterable[CargoTariff], *, on: date | None = None) -> list[engine.Band]:
    """Tarife satırlarını motorun anlayacağı banda çevirir; kapanmış bantlar elenir."""
    today = on or date.today()
    return [
        engine.Band(
            desi_min=row.desi_min,
            desi_max=row.desi_max,
            price=row.price,
            carrier=row.carrier,
            valid_from=row.valid_from,
        )
        for row in rows
        if row.valid_to is None or row.valid_to > today
    ]


def add_band(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    brand_id: uuid.UUID,
    desi_min: Decimal,
    desi_max: Decimal | None,
    price: Decimal,
    carrier: str | None = None,
    valid_from: date | None = None,
    note: str | None = None,
) -> CargoTariff:
    """Yeni bant ekler. Geçersiz aralık ve negatif fiyat reddedilir."""
    if desi_min < ZERO:
        raise InvalidBandError("Desi alt sınırı negatif olamaz")
    if desi_max is not None and desi_max <= desi_min:
        raise InvalidBandError("Desi üst sınırı alt sınırdan büyük olmalı")
    if price < ZERO:
        raise InvalidBandError("Tarife tutarı negatif olamaz")

    row = CargoTariff(
        tenant_id=tenant_id,
        brand_id=brand_id,
        carrier=(carrier or None),
        desi_min=desi_min,
        desi_max=desi_max,
        price=price,
        valid_from=valid_from or date.today(),
        note=note,
    )
    session.add(row)
    session.flush()
    return row


def close_band(session: Session, tariff_id: uuid.UUID, *, on: date | None = None) -> CargoTariff:
    """Bandı kapatır (silmez): geçmiş tahminin hangi tarifeden çıktığı kaybolmasın."""
    row = session.scalar(select(CargoTariff).where(CargoTariff.id == tariff_id))
    if row is None:
        raise TariffNotFoundError(str(tariff_id))
    row.valid_to = on or date.today()
    session.flush()
    return row


def preview(session: Session, *, desi: Decimal, carrier: str | None = None) -> engine.Estimate:
    """ "Bu desi bugün kaça çıkar" — ekranda tarifeyi denemek için."""
    return engine.estimate(desi=desi, bands=bands(session), carrier=carrier, on=date.today())


def reestimate(
    session: Session, *, store_id: uuid.UUID | None = None, dry_run: bool = True
) -> ReestimateSummary:
    """Tahmini gönderileri güncel tarifeyle yeniler (spec §6.2 disipliniyle).

    `ACTUAL` gönderilere dokunulmaz: kargo faturasından gelen gerçek tutar, tarifeden
    hesaplanan tahminle ezilemez — bu, KVN-EK-02'de konan kuralın aynısıdır.
    """
    summary = ReestimateSummary(dry_run=dry_run)
    statement = select(Shipment).join(Order, Order.id == Shipment.order_id)
    if store_id is not None:
        statement = statement.where(Order.store_id == store_id)

    band_list = bands(session)
    for shipment in session.scalars(statement):
        if shipment.cost_state is not CostState.ESTIMATED:
            summary.skipped_actual += 1
            continue
        summary.shipments += 1
        result = engine.estimate(
            desi=shipment.desi_declared,
            bands=band_list,
            carrier=shipment.carrier,
            on=date.today(),
        )
        if result.amount == shipment.cargo_cost_estimated:
            continue
        summary.changed += 1
        summary.delta += result.amount - shipment.cargo_cost_estimated
        summary.orders.append(shipment.order_id)
        if dry_run:
            continue
        shipment.cargo_cost_estimated = result.amount

    if dry_run:
        return summary

    session.flush()
    if summary.orders:
        # Tahmin değişti → kâr değişti; revizyonlar tetikleyici gerekçesiyle loglanır (§6.2).
        recompute_orders(session, order_ids=summary.orders, reason=REESTIMATE_REASON)
    log.info("cargo_tariff.reestimated", brand_id=str(_brand_id()), **summary.as_dict())
    return summary
