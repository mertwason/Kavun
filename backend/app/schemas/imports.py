"""İthalat dosyası ve kur farkı şemaları (spec §12C.7-8)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ImportCostItemType, ImportFileStatus


class ImportFileIn(BaseModel):
    """Yeni ithalat dosyası."""

    supplier_id: uuid.UUID
    file_no: str = Field(min_length=1, max_length=120)
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    beyanname_no: str | None = Field(default=None, max_length=120)
    beyanname_date: date | None = None
    fx_rate_beyanname: Decimal | None = Field(default=None, gt=0)
    import_vat_paid: Decimal | None = Field(
        default=None, ge=0, description="Gümrükte ödenen KDV — maliyete GİRMEZ"
    )


class CostItemIn(BaseModel):
    """Masraf kalemi. İthalat KDV'si buraya GİRMEZ (spec §12C.7)."""

    item_type: ImportCostItemType
    amount_original: Decimal = Field(gt=0)
    currency: str = Field(default="TRY", min_length=3, max_length=3)
    fx_rate: Decimal | None = Field(default=None, gt=0)
    vendor: str | None = Field(default=None, max_length=200)
    doc_ref: str | None = Field(default=None, max_length=120)


class CostItemOut(BaseModel):
    """Kaydedilmiş masraf kalemi."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    item_type: ImportCostItemType
    amount_original: Decimal
    currency: str
    amount_try: Decimal
    vendor: str | None
    doc_ref: str | None


class LandedLineOut(BaseModel):
    """Dağıtım önizlemesi — henüz stoka yazılmadı."""

    model_config = ConfigDict(from_attributes=True)

    line_id: uuid.UUID
    product_id: uuid.UUID | None
    raw_text: str
    qty: Decimal
    goods_total_try: Decimal
    extra_share_try: Decimal
    landed_unit_cost_try: Decimal


class PaymentIn(BaseModel):
    """Tedarikçi ödemesi — kur farkı otomatik hesaplanır (spec §12C.8)."""

    pay_date: date
    amount_original: Decimal = Field(gt=0)
    fx_rate_payment: Decimal = Field(gt=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)


class PaymentOut(BaseModel):
    """Ödeme kaydı ve kur farkı."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    pay_date: date
    amount_original: Decimal
    currency: str
    fx_rate_payment: Decimal
    fx_diff_try: Decimal | None


class ImportFileSummaryOut(BaseModel):
    """Dosya listesi satırı."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    supplier_id: uuid.UUID
    file_no: str
    beyanname_no: str | None
    beyanname_date: date | None
    currency: str
    fx_rate_beyanname: Decimal | None
    import_vat_paid: Decimal | None
    status: ImportFileStatus


class ImportFileDetailOut(BaseModel):
    """Dosya detayı: masraf kalemleri + dağıtım önizlemesi + ödemeler."""

    file: ImportFileSummaryOut
    supplier_name: str
    cost_items: list[CostItemOut]
    cost_total_try: Decimal
    """Landed cost'a giren masraf toplamı — ithalat KDV'si dahil DEĞİL."""

    goods_total_try: Decimal
    lines: list[LandedLineOut]
    payments: list[PaymentOut]
    invoice_ids: list[uuid.UUID]


class ConfirmResultOut(BaseModel):
    """Onay sonucu."""

    invoices: int
    lines: int
    ledger_entries: int


class FxExposureOut(BaseModel):
    """Açık döviz pozisyonu (spec §12C.8 raporu)."""

    model_config = ConfigDict(from_attributes=True)

    currency: str
    open_amount: Decimal
    cost_fx_rate: Decimal | None
    paid_amount: Decimal
    realized_fx_diff_try: Decimal
