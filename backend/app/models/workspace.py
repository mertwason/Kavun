"""Ürün & fiyat çalışma alanı tabloları (spec §12A)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import (
    Desi,
    Money,
    Pct,
    Rate,
    TimestampMixin,
    VatRate,
    brand_fk,
    pg_enum,
    tenant_fk,
    uuid_fk,
    uuid_fk_opt,
    uuid_pk,
)
from app.models.enums import CommissionMode, DraftStatus, ShippingPayer


class ProductDraft(Base, TimestampMixin):
    """Taslak ürün — kayıt anında kâr analizi döner (spec §12A.3)."""

    __tablename__ = "product_drafts"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    brand_id: Mapped[uuid.UUID] = brand_fk()
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    sku_onerisi: Mapped[str | None] = mapped_column(String(100), nullable=True)
    alis_maliyeti: Mapped[Decimal] = mapped_column(Money, nullable=False)
    hedef_satis_fiyati: Mapped[Decimal] = mapped_column(Money, nullable=False)
    kanal: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Spec §12A.3'e ek (KVN-11): komisyon tahmini kategori tarifesinden çözülüyor,
    # kategori olmadan oran bulunamıyordu; promote'ta ürüne de taşınır.
    kategori: Mapped[str | None] = mapped_column(String(200), nullable=True)
    vat_rate: Mapped[Decimal] = mapped_column(VatRate, nullable=False)
    desi: Mapped[Decimal | None] = mapped_column(Desi, nullable=True)
    status: Mapped[DraftStatus] = mapped_column(
        pg_enum(DraftStatus, "draft_status"), nullable=False, default=DraftStatus.DRAFT
    )
    promoted_product_id: Mapped[uuid.UUID | None] = uuid_fk_opt("products.id")


class PricingScenario(Base, TimestampMixin):
    """Fiyat senaryosu — deterministik hesap, tahmin yok (spec §12A.4, §12B.4)."""

    __tablename__ = "pricing_scenarios"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    brand_id: Mapped[uuid.UUID] = brand_fk()
    product_id: Mapped[uuid.UUID] = uuid_fk("products.id")
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    satis_fiyati: Mapped[Decimal] = mapped_column(Money, nullable=False)
    kampanya_indirim_pct: Mapped[Decimal | None] = mapped_column(Pct, nullable=True)
    kampanya_satici_pay_pct: Mapped[Decimal | None] = mapped_column(Pct, nullable=True)
    kargo_kim_oder: Mapped[ShippingPayer] = mapped_column(
        pg_enum(ShippingPayer, "shipping_payer"), nullable=False, default=ShippingPayer.SATICI
    )
    adet_varsayimi: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    commission_mode: Mapped[CommissionMode] = mapped_column(
        pg_enum(CommissionMode, "commission_mode"), nullable=False, default=CommissionMode.CURRENT
    )
    pinned_commission_rate: Mapped[Decimal | None] = mapped_column(Rate, nullable=True)
    future_tariff_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(200), nullable=True)


class ImportBatch(Base, TimestampMixin):
    """Excel import logu (spec §12A.2)."""

    __tablename__ = "import_batches"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    brand_id: Mapped[uuid.UUID] = brand_fk()
    kind: Mapped[str] = mapped_column(String(50), nullable=False, default="price_list")
    filename: Mapped[str] = mapped_column(String(300), nullable=False)
    user: Mapped[str | None] = mapped_column(String(200), nullable=True)
    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    yeni: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    guncelleme: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hata: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
