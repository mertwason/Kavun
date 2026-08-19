"""İçe aktarım izolasyonu: başka markanın SKU'su reddedilir (spec §3A.2).

Bir workspace'ten yüklenen dosya **yalnızca o markaya** yazılır. Dosyada başka markaya ait
bir SKU varsa satır `cross_brand_rejected` ile reddedilir; sessizce o markada ikinci bir
ürün yaratılmaz — aksi halde aynı SKU iki markada birden yaşar ve maliyet/stok ikiye
bölünür (sessiz veri bozulması).

Kontrol **bilinçli** bir guard bypass'ı gerektirir: "bu SKU başka bir markada var mı?"
sorusu tanımı gereği marka dışına bakar. Bypass yalnızca bu tek soru için, salt okuma
amacıyla ve **boolean** dönerek yapılır — karşı markanın hiçbir alanı çağırana geçmez.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.context import system_scope
from app.models.catalog import Product

CROSS_BRAND_REJECTED = "cross_brand_rejected"
"""Hata kodu — hata sheet'inde ve API yanıtında birebir bu metin geçer (spec §3A.2)."""

CROSS_BRAND_MESSAGE = "cross_brand_rejected: bu SKU başka bir markaya ait"


def belongs_to_another_brand(
    session: Session, *, sku: str, tenant_id: uuid.UUID, brand_id: uuid.UUID
) -> bool:
    """Bu SKU aynı tenant'ta BAŞKA bir markada tanımlı mı?

    Yalnızca evet/hayır döner; karşı markanın ürün adı, id'si ya da fiyatı sızmaz.
    """
    if not sku:
        return False
    with system_scope():
        count = session.scalar(
            select(func.count(Product.id)).where(
                Product.tenant_id == tenant_id,
                Product.sku == sku,
                Product.brand_id != brand_id,
            )
        )
    return (count or 0) > 0
