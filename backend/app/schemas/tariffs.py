"""Komisyon tarifesi şemaları (spec §12B)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import CommissionScope, CommissionSource


class CommissionRateOut(BaseModel):
    """Geçerli tarife satırı."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    scope: CommissionScope
    category_code: str | None
    product_id: uuid.UUID | None
    rate: Decimal
    source: CommissionSource
    valid_from: date
    valid_to: date | None
    is_campaign_period: bool


class CommissionChangeOut(BaseModel):
    """Snapshot diff'inden doğan değişiklik (spec §12B.3)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category_code: str | None
    product_id: uuid.UUID | None
    old_rate: Decimal
    new_rate: Decimal
    detected_at: datetime
    monthly_profit_impact: Decimal | None


class TariffImpactIn(BaseModel):
    """Toplu tarife senaryosu girdisi (spec §12B.4)."""

    category: str | None = Field(default=None, description="Boşsa tüm katalog")
    new_rate: Decimal | None = Field(default=None, ge=0, le=1, description="Mutlak yeni oran")
    rate_delta: Decimal | None = Field(
        default=None, ge=-1, le=1, description="Mevcut orana eklenecek fark"
    )
    target_margin_pct: Decimal | None = Field(
        default=None, ge=-100, le=99, description="Verilirse bu marjı koruyan fiyat çözülür"
    )
    kargo_tahmini: Decimal | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _one_of_rate_inputs(self) -> TariffImpactIn:
        """`new_rate` ya da `rate_delta`'dan biri zorunlu."""
        if self.new_rate is None and self.rate_delta is None:
            raise ValueError("new_rate ya da rate_delta verilmeli")
        return self


class TariffImpactRowOut(BaseModel):
    """Etki analizinin bir SKU satırı."""

    model_config = ConfigDict(from_attributes=True)

    product_id: uuid.UUID
    sku: str
    name: str
    category: str | None
    old_rate: Decimal
    new_rate: Decimal
    current_price: Decimal | None
    current_margin_pct: Decimal
    projected_margin_pct: Decimal
    required_price: Decimal | None
    qty_sold: int
    revenue_gross: Decimal
    profit_impact: Decimal


class TariffImpactOut(BaseModel):
    """Toplu tarife senaryosunun sonucu."""

    scope: str
    target_margin_pct: Decimal | None
    monthly_profit_impact: Decimal
    rows: list[TariffImpactRowOut]


class TariffUploadOut(BaseModel):
    """Tarife yükleme yanıtı — eşleştirme + fark analizi (spec §12B.2)."""

    mapping: dict[str, object]
    """Parser'ın hangi sütunu ne olarak okuduğu; UI onay kutusunda gösterilir."""

    valid_from: date
    dry_run: bool
    total_rows: int
    matched: int
    unchanged: int
    changed: int
    new_categories: int
    written: int
    unmatched: list[str]
    errors: list[str]
    changes: list[dict[str, object]]
    affected_sku_count: int
    monthly_profit_impact: Decimal
