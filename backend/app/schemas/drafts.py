"""Taslak ürün şemaları (spec §12A.3)."""

from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CommissionSource, DraftStatus


class DraftInput(BaseModel):
    """Yeni ürün değerlendirme formu."""

    name: str = Field(min_length=1, max_length=300)
    sku_onerisi: str | None = Field(default=None, max_length=100)
    alis_maliyeti: Decimal = Field(ge=0, description="KDV hariç birim maliyet")
    hedef_satis_fiyati: Decimal = Field(gt=0, description="KDV dahil satış fiyatı")
    kanal: str | None = None
    kategori: str | None = Field(default=None, max_length=200)
    vat_rate: Decimal = Field(ge=0, le=100)
    desi: Decimal | None = Field(default=None, ge=0)
    kargo_tahmini: Decimal | None = Field(
        default=None, ge=0, description="Verilmezse 0 sayılır ve analiz uyarı taşır"
    )


class AnalysisOut(BaseModel):
    """Kâr analizi — motorun çıktısı."""

    revenue_gross: Decimal
    cost_cogs: Decimal
    cost_commission: Decimal
    cost_cargo: Decimal
    cost_service_fee: Decimal
    vat_net: Decimal
    profit: Decimal
    margin_pct: Decimal
    commission_rate: Decimal | None
    commission_source: CommissionSource | None
    warnings: list[str]
    waterfall: list[dict[str, object]]


class DraftOut(BaseModel):
    """Kayıtlı taslak + güncel analizi."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    sku_onerisi: str | None
    alis_maliyeti: Decimal
    hedef_satis_fiyati: Decimal
    kanal: str | None
    kategori: str | None
    vat_rate: Decimal
    desi: Decimal | None
    status: DraftStatus
    promoted_product_id: uuid.UUID | None
    analysis: AnalysisOut


class PromotedOut(BaseModel):
    """`promote` yanıtı."""

    product_id: uuid.UUID
    sku: str
    name: str
