"""Alış faturası şemaları (spec §12C.3, §12C.5)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.enums import InvoiceStatus, MatchStatus


class UploadResultOut(BaseModel):
    """Yükleme sonucu — stoka hiçbir şey yazılmadı (spec §12C.3)."""

    invoice_id: uuid.UUID
    status: InvoiceStatus
    lines: int
    unmatched: int
    totals_ok: bool
    lines_total: Decimal
    invoice_total: Decimal | None
    message: str


class SuggestionOut(BaseModel):
    """Fuzzy SKU önerisi — kullanıcı onayı şart (spec §12C.3.4)."""

    product_id: uuid.UUID
    sku: str
    name: str
    confidence: Decimal


class InvoiceLineOut(BaseModel):
    """Fatura satırı + eşleştirme durumu."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    raw_text: str
    product_id: uuid.UUID | None
    sku: str | None
    product_name: str | None
    qty: Decimal
    unit_price_original: Decimal
    unit_price_try: Decimal
    vat_rate: Decimal
    landed_unit_cost_try: Decimal | None
    match_status: MatchStatus
    suggestions: list[SuggestionOut]


class InvoiceSummaryOut(BaseModel):
    """Fatura listesi satırı."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    supplier_id: uuid.UUID
    invoice_no: str
    invoice_date: date
    currency: str
    total: Decimal | None
    status: InvoiceStatus
    confirmed_at: datetime | None


class InvoiceDetailOut(BaseModel):
    """Fatura onay ekranının kaynağı (tasarım brief'i, kalıp 6)."""

    id: uuid.UUID
    supplier_id: uuid.UUID
    supplier_name: str
    invoice_no: str
    invoice_date: date
    currency: str
    fx_rate: Decimal | None
    landed_cost_extra: Decimal
    total: Decimal | None
    status: InvoiceStatus
    confirmed_at: datetime | None
    lines: list[InvoiceLineOut]


class ConfirmMatchIn(BaseModel):
    """Kullanıcının onayladığı SKU eşleştirmesi."""

    product_id: uuid.UUID


class SupplierOut(BaseModel):
    """Fatura formundaki tedarikçi seçeneği."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    default_currency: str
