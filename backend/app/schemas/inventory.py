"""Stok ve maliyet şemaları (spec §12C.4, §12C.5)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import InventoryMovement


class StockRowOut(BaseModel):
    """Stok & maliyet ekranının bir satırı."""

    model_config = ConfigDict(from_attributes=True)

    product_id: uuid.UUID
    sku: str
    name: str
    category: str | None
    on_hand: Decimal
    avg_cost: Decimal
    stock_value: Decimal
    last_movement_at: datetime | None


class LedgerEntryOut(BaseModel):
    """Hareket defteri kaydı (append-only)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: uuid.UUID
    movement: InventoryMovement
    qty_delta: Decimal
    unit_cost_at_movement: Decimal | None
    avg_cost_after: Decimal
    on_hand_after: Decimal
    ref_type: str | None
    ref_id: str | None
    reason: str | None
    moved_at: datetime


class OpeningStockIn(BaseModel):
    """Açılış (devir) girişi — ürün başına tek seferlik (spec §12C.4)."""

    product_id: uuid.UUID
    qty: Decimal = Field(gt=0)
    unit_cost: Decimal = Field(ge=0, description="KDV hariç birim maliyet")
    on_date: date | None = None


class AdjustmentIn(BaseModel):
    """Stok düzeltmesi — gerekçe zorunlu."""

    product_id: uuid.UUID
    qty_delta: Decimal = Field(description="Pozitif = giriş, negatif = çıkış")
    reason: str = Field(min_length=3, max_length=300)
    unit_cost: Decimal | None = Field(default=None, ge=0)


class RebuildOut(BaseModel):
    """Replay sonucu (spec §12C.11)."""

    products: int
    movements: int
    mismatches: list[str]
    dry_run: bool
