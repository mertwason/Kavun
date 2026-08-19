"""Kargo faturası şemaları (spec §5.3, §6.2)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class CargoRowOut(BaseModel):
    """Fatura satırının eşleştirme sonucu."""

    model_config = ConfigDict(from_attributes=True)

    row_no: int
    reference: str
    action: str
    amount: Decimal
    previous: Decimal | None
    message: str


class CargoImportOut(BaseModel):
    """Yükleme özeti — `dry_run` iken hiçbir şey yazılmaz."""

    dry_run: bool
    rows: int
    kesinlesti: int
    zaten_kesin: int
    eslesmedi: int
    hata: int
    total_amount: Decimal
    delta: Decimal
    """Gerçek − tahmin farkı: pozitif ise tahmin düşük kalmış demektir."""

    invoice_id: uuid.UUID | None
    results: list[CargoRowOut]


class CargoInvoiceOut(BaseModel):
    """Kayıtlı kargo faturası."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    invoice_no: str
    period: str
    total: Decimal
    created_at: datetime


class CostStateOut(BaseModel):
    """Kargo maliyetinin kesinleşme durumu (tasarım brief'i, kalıp 2)."""

    model_config = ConfigDict(from_attributes=True)

    total: int
    actual: int
    estimated: int
    estimated_amount: Decimal
    actual_amount: Decimal
