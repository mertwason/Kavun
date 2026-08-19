"""Kargo tarifesi şemaları (spec §6.1, §10.7)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class TariffCreate(BaseModel):
    """Yeni desi bandı. Üst sınır boşsa bant sınırsızdır ("10 desi ve üzeri")."""

    desi_min: Decimal = Field(ge=0)
    desi_max: Decimal | None = Field(default=None, gt=0)
    price: Decimal = Field(ge=0)
    carrier: str | None = Field(default=None, max_length=100)
    valid_from: date | None = None
    note: str | None = Field(default=None, max_length=300)


class TariffOut(BaseModel):
    """Tarife satırı."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    carrier: str | None
    desi_min: Decimal
    desi_max: Decimal | None
    price: Decimal
    valid_from: date
    valid_to: date | None
    note: str | None


class TariffPreview(BaseModel):
    """ "Bu desi kaça çıkar" sonucu."""

    desi: Decimal
    carrier: str | None
    amount: Decimal
    source: str
    """`tarife` = bant eşleşti, `varsayilan` = formüle düşüldü."""


class ReestimateOut(BaseModel):
    """Yeniden tahmin özeti."""

    dry_run: bool
    shipments: int
    changed: int
    skipped_actual: int
    delta: Decimal
