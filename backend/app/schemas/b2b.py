"""D2B kanal ve fiyat disiplini şemaları (spec §12C.9-10)."""

from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class RowErrorOut(BaseModel):
    """Reddedilen satır."""

    model_config = ConfigDict(from_attributes=True)

    row_no: int
    sku: str
    reason: str


class B2BImportOut(BaseModel):
    """Yükleme özeti — `dry_run` iken hiçbir sipariş yazılmaz."""

    model_config = ConfigDict(from_attributes=True)

    rows: int
    orders: int
    lines: int
    customers: int
    skipped: int
    gross_total: Decimal
    errors: list[RowErrorOut]
    dry_run: bool


class TierMarginOut(BaseModel):
    """Kademe bazlı satış özeti."""

    model_config = ConfigDict(from_attributes=True)

    tier: str
    customers: int
    orders: int
    qty: int
    revenue: Decimal
    avg_discount_pct: Decimal


class DamageIn(BaseModel):
    """Fire/hasar kaydı — gerekçe zorunlu (spec §12C.10)."""

    product_id: uuid.UUID
    qty: Decimal = Field(gt=0)
    reason: str = Field(min_length=3, max_length=300)


class DamageRowOut(BaseModel):
    """SKU bazlı hasar oranı."""

    model_config = ConfigDict(from_attributes=True)

    product_id: uuid.UUID
    sku: str
    name: str
    qty: Decimal
    cost: Decimal
    sold_qty: Decimal
    damage_rate_pct: Decimal


class ViolationOut(BaseModel):
    """MSRP / marj tabanı ihlali."""

    model_config = ConfigDict(from_attributes=True)

    product_id: uuid.UUID
    sku: str
    name: str
    channel: str
    price: Decimal
    msrp: Decimal | None
    msrp_gap_pct: Decimal | None
    margin_pct: Decimal
    floor_pct: Decimal | None
    kinds: list[str]
