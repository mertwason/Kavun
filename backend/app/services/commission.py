"""Komisyon çözümleme hiyerarşisi (spec §12B.1).

`resolve_commission(...) -> (rate, source)` her zaman bir çift döner; UI'daki
"tahmini / kesinleşti" ayrımı bu `source` alanından beslenir.

Sıra (en güçlüden zayıfa):
1. `settlement_actual` — hakedişte kesinleşmiş oran (ground truth, Faz 2)
2. `api_product` — kanaldan gelen ürün bazlı oran
3. `api_category` / `manual_tariff_upload` — kategori tarifesi (daha güncel `valid_from` kazanır)
4. `manual` — kullanıcı override'ı (en son çare)

Tarih penceresi: `valid_from <= tarih < valid_to`. Kampanya dönemi kayıtları
(`is_campaign_period=True`) aynı pencerede normal tarifeyi ezer.

Not (KVN-05): Trendyol'da komisyon oranı döndüren bir API YOK. `api_product`/
`api_category` kayıtları yalnızca tarife Excel yüklemesiyle (KVN-14) ya da hakedişten
(Faz 2) doğar. Oran bulunamazsa fonksiyon `(None, None)` döner — motor uydurma oran
kullanmaz, satırı "komisyon oranı yok" uyarısıyla işaretler.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.catalog import CommissionRate, Product
from app.models.enums import CommissionScope, CommissionSource

# Küçük sayı = daha güçlü kaynak.
SOURCE_PRIORITY: dict[CommissionSource, int] = {
    CommissionSource.SETTLEMENT_ACTUAL: 0,
    CommissionSource.API_PRODUCT: 1,
    CommissionSource.API_CATEGORY: 2,
    CommissionSource.MANUAL_TARIFF_UPLOAD: 2,
    CommissionSource.MANUAL: 3,
}


def _sort_key(rate: CommissionRate) -> tuple[int, int, date, bool]:
    """Öncelik sırası: kaynak → ürün bazlı olması → güncellik → kampanya."""
    return (
        SOURCE_PRIORITY.get(rate.source, 9),
        0 if rate.scope is CommissionScope.PRODUCT else 1,
        rate.valid_from,
        rate.is_campaign_period,
    )


def resolve_commission(
    session: Session,
    *,
    store_id: uuid.UUID,
    product: Product | None,
    on_date: date,
) -> tuple[CommissionRate | None, CommissionSource | None]:
    """Verilen tarihte geçerli komisyon oranını ve kaynağını çözer."""
    candidates = list(
        session.scalars(
            select(CommissionRate).where(
                CommissionRate.store_id == store_id,
                CommissionRate.valid_from <= on_date,
                (CommissionRate.valid_to.is_(None)) | (CommissionRate.valid_to > on_date),
            )
        ).all()
    )
    if not candidates:
        return None, None

    matching: list[CommissionRate] = []
    for rate in candidates:
        if rate.scope is CommissionScope.PRODUCT:
            if product is not None and rate.product_id == product.id:
                matching.append(rate)
        elif rate.category_code and product is not None and rate.category_code == product.category:
            matching.append(rate)

    if not matching:
        return None, None

    # Kampanya kaydı normal tarifeyi ezer; ardından öncelik sırası uygulanır.
    campaign = [rate for rate in matching if rate.is_campaign_period]
    pool = campaign or matching
    best = sorted(pool, key=_sort_key)[0]
    # Aynı öncelikte birden fazla kayıt varsa en güncel `valid_from` kazanır (§12B.2).
    same_rank = [rate for rate in pool if _sort_key(rate)[:2] == _sort_key(best)[:2]]
    best = max(same_rank, key=lambda rate: rate.valid_from)
    return best, best.source
