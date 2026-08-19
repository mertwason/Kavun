"""Fiyat senaryosu şemaları (spec §12A.4)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CommissionMode, CommissionSource, ShippingPayer


class ScenarioInputIn(BaseModel):
    """Senaryo girdisi (kaydedilmemiş de olabilir)."""

    name: str = Field(min_length=1, max_length=200)
    product_id: uuid.UUID
    satis_fiyati: Decimal = Field(gt=0, description="Liste fiyatı, KDV dahil")
    kampanya_indirim_pct: Decimal | None = Field(default=None, ge=0, le=100)
    kampanya_satici_pay_pct: Decimal | None = Field(default=None, ge=0, le=100)
    kargo_kim_oder: ShippingPayer = ShippingPayer.SATICI
    adet_varsayimi: int = Field(default=1, ge=1)
    commission_mode: CommissionMode = CommissionMode.CURRENT
    pinned_commission_rate: Decimal | None = Field(default=None, ge=0, le=1)
    future_tariff_date: date | None = Field(
        default=None, description="`future_tariff` modunda hangi tarihteki tarife kullanılsın"
    )
    kargo_tahmini: Decimal | None = Field(default=None, ge=0)


class ScenarioResultOut(BaseModel):
    """Senaryo sonucu."""

    model_config = ConfigDict(from_attributes=True)

    scenario_id: uuid.UUID | None
    name: str
    product_id: uuid.UUID
    sku: str
    satis_fiyati: Decimal
    musteri_odedigi: Decimal
    adet: int
    birim_kar: Decimal
    marj_pct: Decimal
    toplam_kar: Decimal
    basabas_fiyat: Decimal | None
    commission_rate: Decimal | None
    commission_source: CommissionSource | None
    cargo_cost: Decimal
    service_fee: Decimal
    warnings: list[str]
    waterfall: list[dict[str, object]]


class CompareIn(BaseModel):
    """Karşılaştırma isteği — en fazla 3 senaryo (spec §12A.4)."""

    scenario_ids: list[uuid.UUID] = Field(default_factory=list, max_length=3)
    inputs: list[ScenarioInputIn] = Field(default_factory=list, max_length=3)


class TargetMarginIn(ScenarioInputIn):
    """Hedef marj çözücüsü girdisi; `satis_fiyati` başlangıç değeri olarak taşınır."""

    hedef_marj_pct: Decimal = Field(ge=-100, le=99, description="Hedeflenen marj yüzdesi")


class TargetMarginOut(BaseModel):
    """Çözücü sonucu."""

    target_margin_pct: Decimal
    price: Decimal | None
    reachable: bool
    message: str
    result: ScenarioResultOut | None
