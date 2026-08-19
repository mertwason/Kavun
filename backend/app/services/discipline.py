"""Marka fiyat disiplini: MSRP ve minimum marj tabanı (spec §12C.10).

İki ayrı disiplin, tek ekranda:

1. **MSRP disiplini.** Alessi gibi markalarda tavsiye edilen perakende fiyatının *altına*
   inmek marka değerini aşındırır ve bayi ilişkisini bozar. Bu yüzden ihlal "MSRP'nin
   altında satış"tır; üstünde fiyatlamak ihlal sayılmaz (pazaryeri fiyatı serbesttir).
2. **Marj tabanı.** Ürün bazlı `min_margin_floor_pct` yoksa markanın varsayılanı geçerlidir.
   Hesaplanan marj tabanın altındaysa uyarı üretilir.

Kural **uyarır, engellemez**: senaryo motoru ve hedef marj çözücü tabanı gösterir ama
fiyat yazmayı durdurmaz (spec §12C.10). Karar insanındır; Kavun görünür kılar.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import textfmt
from app.core.context import current_context
from app.core.logging import get_logger
from app.models.catalog import Product
from app.models.enums import AlertSeverity
from app.models.identity import Brand
from app.models.results import Alert
from app.services.pricelist import price_rows

log = get_logger("services.discipline")

ZERO = Decimal("0")

MSRP_ALERT = "msrp_ihlali"
MARGIN_FLOOR_ALERT = "marj_tabani"


@dataclass(frozen=True)
class Violation:
    """Bir kanal-fiyat satırının disiplin ihlali."""

    product_id: uuid.UUID
    sku: str
    name: str
    channel: str
    price: Decimal
    msrp: Decimal | None
    msrp_gap_pct: Decimal | None
    """Fiyat MSRP'nin ne kadar altında (yüzde). Negatif değer üstünde demektir."""

    margin_pct: Decimal
    floor_pct: Decimal | None
    kinds: tuple[str, ...]
    """`msrp` ve/veya `margin_floor`."""


def _active_brand(session: Session) -> Brand | None:
    """Bağlamdaki markayı çözer.

    `brands` tablosu marka-kapsamlı DEĞİLDİR (markanın kendisidir), bu yüzden guard onu
    filtrelemez: `select(Brand)` gelişigüzel bir marka döndürür. Marj tabanı gibi marka
    ayarları mutlaka aktif markadan okunmalı — aksi halde Alessi'nin tabanı Kahveji'nin
    değeriyle ölçülür.
    """
    context = current_context()
    if context is None or context.brand_id is None:
        return None
    return session.scalar(select(Brand).where(Brand.id == context.brand_id))


def _floor_for(product: Product, brand: Brand | None) -> Decimal | None:
    """Ürün bazlı taban yoksa marka varsayılanı devralınır (spec §12C.10)."""
    if product.min_margin_floor_pct is not None:
        return product.min_margin_floor_pct
    return brand.min_margin_floor_pct if brand else None


def violations(session: Session, *, today: date | None = None) -> list[Violation]:
    """Aktif markanın MSRP ve marj tabanı ihlalleri."""
    on_date = today or datetime.now(UTC).date()
    products = {product.id: product for product in session.scalars(select(Product)).all()}
    brand = _active_brand(session)

    found: list[Violation] = []
    for row in price_rows(session, today=on_date):
        if not row.price or row.price <= ZERO:
            continue
        product = products.get(row.product_id)
        if product is None:
            continue

        kinds: list[str] = []
        gap: Decimal | None = None
        if product.msrp is not None and product.msrp > ZERO and row.price < product.msrp:
            gap = ((product.msrp - row.price) / product.msrp * Decimal("100")).quantize(
                Decimal("0.01")
            )
            kinds.append("msrp")

        floor = _floor_for(product, brand)
        if floor is not None and row.margin_pct < floor:
            kinds.append("margin_floor")

        if not kinds:
            continue
        found.append(
            Violation(
                product_id=row.product_id,
                sku=row.sku,
                name=row.name,
                channel=row.channel,
                price=row.price,
                msrp=product.msrp,
                msrp_gap_pct=gap,
                margin_pct=row.margin_pct,
                floor_pct=floor,
                kinds=tuple(kinds),
            )
        )
    return found


def _message(violation: Violation) -> str:
    parts: list[str] = []
    if "msrp" in violation.kinds and violation.msrp is not None and violation.msrp_gap_pct:
        parts.append(
            f"{violation.channel} fiyatı {textfmt.money(violation.price)}, "
            f"MSRP {textfmt.money(violation.msrp)} — "
            f"{textfmt.percent(violation.msrp_gap_pct)} altında"
        )
    if "margin_floor" in violation.kinds and violation.floor_pct is not None:
        parts.append(
            f"marj {textfmt.percent(violation.margin_pct)} < "
            f"taban {textfmt.percent(violation.floor_pct)}"
        )
    return f"{violation.sku}: " + "; ".join(parts)


def raise_alerts(session: Session, *, today: date | None = None) -> int:
    """İhlalleri uyarıya çevirir; aynı gün aynı ihlal için ikinci uyarı yazılmaz."""
    found = violations(session, today=today)
    if not found:
        return 0

    brand = _active_brand(session)
    if brand is None:
        return 0

    now = datetime.now(UTC)
    day_start = datetime.combine(now.date(), datetime.min.time(), tzinfo=UTC)
    written = 0
    for violation in found:
        for kind in violation.kinds:
            alert_type = MSRP_ALERT if kind == "msrp" else MARGIN_FLOOR_ALERT
            entity = f"{violation.sku}:{violation.channel}"
            existing = session.scalar(
                select(Alert).where(
                    Alert.type == alert_type,
                    Alert.entity_ref == entity,
                    Alert.created_at >= day_start,
                )
            )
            if existing is not None:
                continue
            session.add(
                Alert(
                    tenant_id=brand.tenant_id,
                    brand_id=brand.id,
                    type=alert_type,
                    severity=AlertSeverity.WARNING,
                    entity_ref=entity,
                    message=_message(violation),
                    created_at=now,
                )
            )
            written += 1
    session.flush()
    log.info("discipline.alerts_raised", violations=len(found), alerts=written)
    return written
