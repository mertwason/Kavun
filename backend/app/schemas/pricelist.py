"""Fiyat listesi import şemaları (spec §12A.2)."""

from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class RowResultOut(BaseModel):
    """Diff önizlemesindeki bir satır."""

    model_config = ConfigDict(from_attributes=True)

    row_no: int
    sku: str
    channel: str
    # yeni | guncelleme | degisiklik_yok | hata
    action: str
    message: str
    changes: dict[str, str]


class ImportSummaryOut(BaseModel):
    """Import sonucu — `dry_run=true` iken hiçbir yazma yapılmamıştır."""

    model_config = ConfigDict(from_attributes=True)

    dry_run: bool
    yeni: int
    guncelleme: int
    degisiklik_yok: int
    hata: int
    rows: list[RowResultOut]


class PriceRowOut(BaseModel):
    """Ürün çalışma alanı tablosunun bir satırı (spec §12A.5)."""

    model_config = ConfigDict(from_attributes=True)

    product_id: uuid.UUID
    sku: str
    name: str
    channel: str
    vat_rate: Decimal
    desi: Decimal | None
    unit_cost: Decimal | None
    price: Decimal | None
    commission_rate: Decimal | None
    service_fee: Decimal
    profit: Decimal
    margin_pct: Decimal
