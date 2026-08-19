"""Taslak ürün akışı (spec §12A.3).

"Bu ürünü satsak ne kazanırız?" sorusunun cevabı. Taslak kaydı anında kâr analizi
döner; analiz **motorun kendisinden** gelir (`app/engine/profit.py`) — ikinci bir
formül yok (CLAUDE.md §1).

`promote` taslağı gerçek ürüne çevirir: `products` + `sku_costs` + `sku_logistics`
kayıtları doğar, taslak `promoted` olur ve hangi ürüne dönüştüğü saklanır.

Kargo tahmini: desi bazlı tarife tablosu KVN-14'te geliyor. O zamana kadar tutar
girdiden alınır; verilmezse SIFIR sayılır ve analiz `kargo_tarifesi_yok` uyarısı
taşır — uydurma tarife üretilmez.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.engine.profit import LineInput, ProfitBreakdown, compute_line_profit
from app.models.catalog import CommissionRate, Product, SkuCost, SkuLogistics, SkuPrice
from app.models.enums import (
    ChannelCode,
    CommissionScope,
    CommissionSource,
    CostSource,
    DraftStatus,
)
from app.models.identity import Channel, Store
from app.models.workspace import ProductDraft

log = get_logger("services.drafts")

ZERO = Decimal("0")


class DraftError(RuntimeError):
    """Taslak akışının reddettiği durum (ör. zaten dönüştürülmüş taslak)."""


@dataclass(frozen=True)
class DraftAnalysis:
    """Taslağın kâr analizi — form kaydedilmeden de hesaplanabilir."""

    breakdown: ProfitBreakdown
    commission_rate: Decimal | None
    commission_source: CommissionSource | None
    service_fee: Decimal
    cargo_cost: Decimal


def _store_for(session: Session, channel: str | None) -> Store | None:
    """Kanal koduna karşılık gelen mağaza; kanal verilmezse Trendyol (yoksa ilk mağaza)."""
    stores = list(session.scalars(select(Store).order_by(Store.name)).all())
    if not stores:
        return None
    channels = {row.id: row.code for row in session.scalars(select(Channel)).all()}
    if channel:
        for store in stores:
            if channels.get(store.channel_id) is not None and (
                str(channels[store.channel_id].value) == channel
            ):
                return store
        return None
    for store in stores:
        if channels.get(store.channel_id) is ChannelCode.TRENDYOL:
            return store
    return stores[0]


def _category_commission(
    session: Session, store: Store, category: str | None, on_date: date
) -> CommissionRate | None:
    """Kategori tarifesinden oran tahmini (taslakta henüz ürün yok)."""
    if not category:
        return None
    candidates = list(
        session.scalars(
            select(CommissionRate).where(
                CommissionRate.store_id == store.id,
                CommissionRate.scope == CommissionScope.CATEGORY,
                CommissionRate.category_code == category,
                CommissionRate.valid_from <= on_date,
                (CommissionRate.valid_to.is_(None)) | (CommissionRate.valid_to > on_date),
            )
        ).all()
    )
    if not candidates:
        return None
    return max(candidates, key=lambda rate: rate.valid_from)


def analyze(
    session: Session,
    *,
    price: Decimal,
    unit_cost: Decimal | None,
    vat_rate: Decimal,
    channel: str | None,
    category: str | None,
    cargo_cost: Decimal | None,
    on_date: date,
) -> DraftAnalysis:
    """Taslağın (ya da form girdisinin) kâr analizi — motoru çağırır."""
    store = _store_for(session, channel)
    service_fee = (store.service_fee_per_order or ZERO) if store else ZERO
    rate_row = _category_commission(session, store, category, on_date) if store else None
    cargo = cargo_cost if cargo_cost is not None else ZERO

    breakdown = compute_line_profit(
        LineInput(
            line_gross=price,
            qty=1,
            vat_percent=vat_rate,
            unit_cost_net=unit_cost,
            commission_rate=rate_row.rate if rate_row else None,
            commission_source=rate_row.source if rate_row else None,
            cargo_cost=cargo,
            service_fee=service_fee,
        )
    )
    if cargo_cost is None:
        breakdown = ProfitBreakdown(
            **{
                **breakdown.__dict__,
                "warnings": (*breakdown.warnings, "kargo_tarifesi_yok"),
            }
        )
    return DraftAnalysis(
        breakdown=breakdown,
        commission_rate=rate_row.rate if rate_row else None,
        commission_source=rate_row.source if rate_row else None,
        service_fee=service_fee,
        cargo_cost=cargo,
    )


def analyze_draft(
    session: Session, draft: ProductDraft, *, cargo_cost: Decimal | None, on_date: date
) -> DraftAnalysis:
    """Kayıtlı taslağın analizi."""
    return analyze(
        session,
        price=draft.hedef_satis_fiyati,
        unit_cost=draft.alis_maliyeti,
        vat_rate=draft.vat_rate,
        channel=draft.kanal,
        category=draft.kategori,
        cargo_cost=cargo_cost,
        on_date=on_date,
    )


def create_draft(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    brand_id: uuid.UUID,
    name: str,
    sku_onerisi: str | None,
    alis_maliyeti: Decimal,
    hedef_satis_fiyati: Decimal,
    kanal: str | None,
    kategori: str | None,
    vat_rate: Decimal,
    desi: Decimal | None,
) -> ProductDraft:
    """Taslağı kaydeder (analiz çağıran tarafta hesaplanır)."""
    draft = ProductDraft(
        tenant_id=tenant_id,
        brand_id=brand_id,
        name=name,
        sku_onerisi=sku_onerisi,
        alis_maliyeti=alis_maliyeti,
        hedef_satis_fiyati=hedef_satis_fiyati,
        kanal=kanal,
        kategori=kategori,
        vat_rate=vat_rate,
        desi=desi,
        status=DraftStatus.DRAFT,
    )
    session.add(draft)
    session.flush()
    return draft


def promote(
    session: Session, draft: ProductDraft, *, today: date, user: str | None = None
) -> Product:
    """Taslağı gerçek ürüne çevirir (spec §12A.3).

    Ürün + maliyet + desi + (kanal biliniyorsa) fiyat kayıtları doğar. SKU önerisi
    yoksa ya da çakışıyorsa akış reddedilir — sessizce başka bir SKU uydurulmaz.
    """
    if draft.status is not DraftStatus.DRAFT:
        raise DraftError(f"Taslak zaten '{draft.status.value}' durumunda")

    sku = (draft.sku_onerisi or "").strip()
    if not sku:
        raise DraftError("SKU önerisi boş — ürüne dönüştürmeden önce SKU verilmeli")
    if session.scalar(select(Product).where(Product.sku == sku)) is not None:
        raise DraftError(f"Bu SKU zaten kullanılıyor: {sku}")

    product = Product(
        tenant_id=draft.tenant_id,
        brand_id=draft.brand_id,
        sku=sku,
        name=draft.name,
        category=draft.kategori,
        vat_rate=draft.vat_rate,
    )
    session.add(product)
    session.flush()

    session.add(
        SkuCost(
            product_id=product.id,
            unit_cost=draft.alis_maliyeti,
            source=CostSource.MANUAL,
            effective_from=today,
            created_by=user,
        )
    )
    if draft.desi is not None:
        session.add(SkuLogistics(product_id=product.id, desi=draft.desi, effective_from=today))
    store = _store_for(session, draft.kanal)
    if store is not None:
        session.add(
            SkuPrice(
                product_id=product.id,
                store_id=store.id,
                price=draft.hedef_satis_fiyati,
                effective_from=today,
                created_by=user,
            )
        )

    draft.status = DraftStatus.PROMOTED
    draft.promoted_product_id = product.id
    session.flush()
    log.info("draft.promoted", draft_id=str(draft.id), product_id=str(product.id), sku=sku)
    return product


def discard(session: Session, draft: ProductDraft) -> ProductDraft:
    """Taslağı iptal eder; kayıt silinmez (geçmiş korunur)."""
    if draft.status is DraftStatus.PROMOTED:
        raise DraftError("Ürüne dönüştürülmüş taslak iptal edilemez")
    draft.status = DraftStatus.DISCARDED
    session.flush()
    return draft
