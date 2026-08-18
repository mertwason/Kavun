"""Ortak sütun tipleri ve yardımcıları.

Para disiplini (CLAUDE.md §1): tutarlar `NUMERIC(14,4)`, ortalama maliyet `NUMERIC(14,6)`,
oranlar `NUMERIC(6,4)`. Python tarafında hepsi `Decimal`; `float` yasak.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

# --- parasal sütun tipleri ---------------------------------------------------

Money = Numeric(14, 4)
"""Tutar — kuruş hassasiyeti korunur (spec §3.3)."""

AvgCost = Numeric(14, 6)
"""Hareketli ağırlıklı ortalama maliyet — yuvarlama birikimi önlenir (spec §12C.1)."""

Rate = Numeric(6, 4)
"""Oran (komisyon vb.) — 0.2150 = %21,50."""

VatRate = Numeric(5, 2)
"""KDV oranı — 20.00 = %20."""

Pct = Numeric(6, 2)
"""Yüzde değeri — 12.50 = %12,50 (marj tabanı, iskonto vb.)."""

Qty = Numeric(12, 3)
"""Adet — kısmi adetli alımlar (kg/metre) için ondalık."""

FxRate = Numeric(12, 6)
"""Döviz kuru."""

Desi = Numeric(8, 2)
"""Desi/hacimsel ağırlık."""


def uuid_pk() -> Mapped[uuid.UUID]:
    """UUID birincil anahtar."""
    return mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def uuid_fk(target: str, *, ondelete: str = "CASCADE", index: bool = True) -> Mapped[uuid.UUID]:
    """Zorunlu UUID foreign key."""
    return mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(target, ondelete=ondelete),
        nullable=False,
        index=index,
    )


def uuid_fk_opt(
    target: str, *, ondelete: str = "SET NULL", index: bool = True
) -> Mapped[uuid.UUID | None]:
    """Opsiyonel UUID foreign key."""
    return mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(target, ondelete=ondelete),
        nullable=True,
        index=index,
    )


def tenant_fk() -> Mapped[uuid.UUID]:
    """`tenants.id`'ye zorunlu FK — her tabloda bulunur (spec §3.1)."""
    return uuid_fk("tenants.id")


def brand_fk() -> Mapped[uuid.UUID]:
    """`brands.id`'ye zorunlu FK — işlem verisi taşıyan her tabloda (spec §3A.2)."""
    return uuid_fk("brands.id", ondelete="RESTRICT")


def pg_enum(enum_cls: type[StrEnum], name: str) -> Enum:
    """Postgres native enum — DB'de enum'ın *değerleri* saklanır, isimleri değil."""
    return Enum(
        enum_cls,
        name=name,
        native_enum=True,
        values_callable=lambda cls: [member.value for member in cls],
    )


class TimestampMixin:
    """`created_at` sütunu — DB saatinden yazılır."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
