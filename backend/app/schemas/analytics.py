"""Dashboard, SKU marj listesi ve sipariş detayı şemaları (spec §10).

Şelale adımları `[{"key": "komisyon", "amount": -24.0}]` biçiminde döner; Türkçe
etiketler frontend'in `locales/tr.json` dosyasından gelir (CLAUDE.md §4 — backend
yanıtında UI metni taşınmaz).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.enums import CommissionSource, OrderStatus


class PeriodOut(BaseModel):
    """Rapor dönemi (`start` dahil, `end` hariç)."""

    start: date
    end: date


class WaterfallStep(BaseModel):
    """Şelale grafiğinin bir adımı (tasarım brief'i, kalıp 4)."""

    key: str
    amount: Decimal


class KpisOut(BaseModel):
    """Dashboard üst şeridi."""

    revenue_gross: Decimal
    revenue_net_vat: Decimal
    profit: Decimal
    margin_pct: Decimal
    return_rate_pct: Decimal
    order_count: int
    line_count: int
    final_profit: Decimal
    estimated_profit: Decimal
    final_line_count: int


class DailyPointOut(BaseModel):
    """Günlük kâr grafiğinin bir noktası."""

    day: date
    revenue_gross: Decimal
    profit: Decimal


class StoreBreakdownOut(BaseModel):
    """Mağaza/kanal kırılımı."""

    store_id: uuid.UUID
    store_name: str
    revenue_gross: Decimal
    profit: Decimal
    margin_pct: Decimal


class DashboardOut(BaseModel):
    """Dashboard yanıtı (spec §10.1)."""

    period: PeriodOut
    kpis: KpisOut
    daily: list[DailyPointOut]
    stores: list[StoreBreakdownOut]


class SkuMarginOut(BaseModel):
    """SKU marj listesi satırı (spec §10.2)."""

    model_config = ConfigDict(from_attributes=True)

    product_id: uuid.UUID
    sku: str
    name: str
    category: str | None
    qty_sold: int
    revenue_gross: Decimal
    cost_cogs: Decimal
    profit: Decimal
    margin_pct: Decimal
    is_final: bool


class OrderRowOut(BaseModel):
    """Sipariş listesi satırı."""

    model_config = ConfigDict(from_attributes=True)

    order_id: uuid.UUID
    external_order_id: str
    order_date: datetime
    status: OrderStatus
    store_name: str
    gross_total: Decimal
    profit: Decimal
    margin_pct: Decimal
    is_final: bool


class OrderLineDetailOut(BaseModel):
    """Sipariş satırı + şelale dökümü."""

    order_line_id: uuid.UUID
    sku: str | None
    name: str | None
    qty: int
    line_gross: Decimal
    vat_rate: Decimal
    profit: Decimal
    margin_pct: Decimal
    is_final: bool
    commission_source: CommissionSource | None
    waterfall: list[WaterfallStep]


class OrderDetailOut(BaseModel):
    """Sipariş detayı (spec §10.3)."""

    order_id: uuid.UUID
    external_order_id: str
    order_date: datetime
    status: OrderStatus
    store_name: str
    gross_total: Decimal
    profit: Decimal
    margin_pct: Decimal
    is_final: bool
    lines: list[OrderLineDetailOut]
    waterfall: list[WaterfallStep]
