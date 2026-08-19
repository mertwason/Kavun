"""Katalog, maliyet ve komisyon tarifesi tabloları (spec §5.2, §12B)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, String, UniqueConstraint
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
from app.models.enums import CommissionScope, CommissionSource, CostSource


class Product(Base, TimestampMixin):
    """Ürün. `brand_id` zorunlu — markalar arası sızıntı mimari olarak engellenir."""

    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("tenant_id", "brand_id", "sku", name="uq_products_brand_sku"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    brand_id: Mapped[uuid.UUID] = brand_fk()
    sku: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    barcode: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    category: Mapped[str | None] = mapped_column(String(200), nullable=True)
    vat_rate: Mapped[Decimal] = mapped_column(VatRate, nullable=False)
    # Marka fiyat disiplini (spec §12C.10)
    msrp: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    min_margin_floor_pct: Mapped[Decimal | None] = mapped_column(Pct, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ProductChannelMap(Base, TimestampMixin):
    """Ürünün kanaldaki karşılığı (spec §5.2)."""

    __tablename__ = "product_channel_map"
    __table_args__ = (
        UniqueConstraint("store_id", "external_product_id", name="uq_pcm_store_external"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    product_id: Mapped[uuid.UUID] = uuid_fk("products.id")
    store_id: Mapped[uuid.UUID] = uuid_fk("stores.id")
    external_product_id: Mapped[str] = mapped_column(String(120), nullable=False)
    external_barcode: Mapped[str | None] = mapped_column(String(64), nullable=True)


class SkuCost(Base, TimestampMixin):
    """Versiyonlu maliyet. Geçerli maliyet = `effective_from <= order_date` olan en güncel kayıt."""

    __tablename__ = "sku_costs"

    id: Mapped[uuid.UUID] = uuid_pk()
    product_id: Mapped[uuid.UUID] = uuid_fk("products.id")
    unit_cost: Mapped[Decimal] = mapped_column(Money, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="TRY")
    source: Mapped[CostSource] = mapped_column(pg_enum(CostSource, "cost_source"), nullable=False)
    invoice_ref: Mapped[str | None] = mapped_column(String(120), nullable=True)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    created_by: Mapped[str | None] = mapped_column(String(200), nullable=True)


class SkuPrice(Base, TimestampMixin):
    """Versiyonlu satış fiyatı — kanal (mağaza) bazlı (spec §12A.1).

    Spec §5.2'de ayrı bir fiyat tablosu tanımlı değil ama §12A.1 fiyat listesinin
    upsert anahtarı `(SKU, Kanal)`; yani fiyat ürünün değil, ürün-kanal çiftinin
    özelliğidir (Trendyol fiyatı ile D2B fiyatı aynı olmak zorunda değil). Maliyet
    gibi versiyonlanır: geçmiş kayıt güncellenmez, yeni `effective_from` eklenir —
    böylece eski siparişlerin fiyat bağlamı bozulmaz (CLAUDE.md §1).
    """

    __tablename__ = "sku_prices"

    id: Mapped[uuid.UUID] = uuid_pk()
    product_id: Mapped[uuid.UUID] = uuid_fk("products.id")
    store_id: Mapped[uuid.UUID] = uuid_fk("stores.id")
    price: Mapped[Decimal] = mapped_column(Money, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="TRY")
    effective_from: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    created_by: Mapped[str | None] = mapped_column(String(200), nullable=True)


class SkuLogistics(Base, TimestampMixin):
    """Desi ve varsayılan kargo firması (spec §5.2)."""

    __tablename__ = "sku_logistics"

    id: Mapped[uuid.UUID] = uuid_pk()
    product_id: Mapped[uuid.UUID] = uuid_fk("products.id")
    desi: Mapped[Decimal] = mapped_column(Desi, nullable=False)
    default_carrier: Mapped[str | None] = mapped_column(String(100), nullable=True)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)


class CommissionRate(Base, TimestampMixin):
    """Versiyonlu komisyon tarifesi — çözümleme hiyerarşisi için (spec §12B.1)."""

    __tablename__ = "commission_rates"

    id: Mapped[uuid.UUID] = uuid_pk()
    store_id: Mapped[uuid.UUID] = uuid_fk("stores.id")
    scope: Mapped[CommissionScope] = mapped_column(
        pg_enum(CommissionScope, "commission_scope"), nullable=False
    )
    product_id: Mapped[uuid.UUID | None] = uuid_fk_opt("products.id")
    category_code: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    rate: Mapped[Decimal] = mapped_column(Rate, nullable=False)
    source: Mapped[CommissionSource] = mapped_column(
        pg_enum(CommissionSource, "commission_source"), nullable=False
    )
    valid_from: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    snapshot_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_campaign_period: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    campaign_name: Mapped[str | None] = mapped_column(String(200), nullable=True)


class CommissionChange(Base, TimestampMixin):
    """Günlük snapshot diff'inden doğan oran değişikliği + etki analizi (spec §12B.3)."""

    __tablename__ = "commission_changes"

    id: Mapped[uuid.UUID] = uuid_pk()
    store_id: Mapped[uuid.UUID] = uuid_fk("stores.id")
    product_id: Mapped[uuid.UUID | None] = uuid_fk_opt("products.id")
    category_code: Mapped[str | None] = mapped_column(String(200), nullable=True)
    old_rate: Mapped[Decimal] = mapped_column(Rate, nullable=False)
    new_rate: Mapped[Decimal] = mapped_column(Rate, nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    monthly_profit_impact: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    alert_id: Mapped[uuid.UUID | None] = uuid_fk_opt("alerts.id")


class Supplier(Base, TimestampMixin):
    """Tedarikçi (spec §12C.2)."""

    __tablename__ = "suppliers"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_suppliers_tenant_name"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    vkn: Mapped[str | None] = mapped_column(String(20), nullable=True)
    default_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="TRY")


class Customer(Base, TimestampMixin):
    """B2B müşteri — kademe bazlı iskonto analizi için (spec §12C.9)."""

    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    brand_id: Mapped[uuid.UUID] = brand_fk()
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    tier: Mapped[str | None] = mapped_column(String(50), nullable=True)
    default_discount_pct: Mapped[Decimal | None] = mapped_column(Pct, nullable=True)
