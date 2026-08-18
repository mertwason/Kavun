"""İşlem verisi tabloları (spec §5.3)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import (
    Desi,
    Money,
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
from app.models.enums import (
    CommissionSource,
    CostState,
    OrderStatus,
    SettlementRecordType,
)


class RawEvent(Base):
    """Ham API yanıtı — immutable (spec §3.2).

    Aya göre partition'lanır; birincil anahtar bu yüzden `(id, fetched_at)`.
    Normalize tablolar silinip buradan yeniden üretilebilir (`replay`, KVN-06).
    """

    __tablename__ = "raw_events"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "store_id",
            "event_type",
            "external_id",
            "fetched_at",
            name="uq_raw_events_identity",
        ),
        {"postgresql_partition_by": "RANGE (fetched_at)"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, nullable=False
    )
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    store_id: Mapped[uuid.UUID] = uuid_fk("stores.id")
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    external_id: Mapped[str] = mapped_column(String(120), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Order(Base, TimestampMixin):
    """Sipariş başlığı. Idempotency: `(tenant_id, store_id, external_order_id)` tekil (spec §3.7)."""

    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "store_id", "external_order_id", name="uq_orders_tenant_store_external"
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    brand_id: Mapped[uuid.UUID] = brand_fk()
    store_id: Mapped[uuid.UUID] = uuid_fk("stores.id")
    external_order_id: Mapped[str] = mapped_column(String(120), nullable=False)
    order_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    status: Mapped[OrderStatus] = mapped_column(
        pg_enum(OrderStatus, "order_status"), nullable=False
    )
    customer_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    gross_total: Mapped[Decimal] = mapped_column(Money, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="TRY")


class OrderLine(Base, TimestampMixin):
    """Sipariş satırı — kâr hesabının birimi (spec §6)."""

    __tablename__ = "order_lines"
    __table_args__ = (
        UniqueConstraint("order_id", "external_line_id", name="uq_order_lines_order_external"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    brand_id: Mapped[uuid.UUID] = brand_fk()
    order_id: Mapped[uuid.UUID] = uuid_fk("orders.id")
    product_id: Mapped[uuid.UUID | None] = uuid_fk_opt("products.id")
    external_line_id: Mapped[str] = mapped_column(String(120), nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_sale_price: Mapped[Decimal] = mapped_column(Money, nullable=False)
    line_gross: Mapped[Decimal] = mapped_column(Money, nullable=False)
    vat_rate: Mapped[Decimal] = mapped_column(VatRate, nullable=False)
    commission_rate_used: Mapped[Decimal | None] = mapped_column(Rate, nullable=True)
    commission_source: Mapped[CommissionSource | None] = mapped_column(
        pg_enum(CommissionSource, "commission_source"), nullable=True
    )
    status: Mapped[OrderStatus] = mapped_column(
        pg_enum(OrderStatus, "order_status"), nullable=False
    )


class Shipment(Base, TimestampMixin):
    """Gönderi ve kargo maliyeti — `estimated → actual` (spec §3.4)."""

    __tablename__ = "shipments"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    brand_id: Mapped[uuid.UUID] = brand_fk()
    order_id: Mapped[uuid.UUID] = uuid_fk("orders.id")
    carrier: Mapped[str | None] = mapped_column(String(100), nullable=True)
    desi_declared: Mapped[Decimal | None] = mapped_column(Desi, nullable=True)
    desi_invoiced: Mapped[Decimal | None] = mapped_column(Desi, nullable=True)
    cargo_cost_estimated: Mapped[Decimal] = mapped_column(Money, nullable=False)
    cargo_cost_actual: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    cost_state: Mapped[CostState] = mapped_column(
        pg_enum(CostState, "cost_state"), nullable=False, default=CostState.ESTIMATED
    )


class Return(Base, TimestampMixin):
    """İade kaydı (spec §5.3)."""

    __tablename__ = "returns"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    brand_id: Mapped[uuid.UUID] = brand_fk()
    order_line_id: Mapped[uuid.UUID] = uuid_fk("order_lines.id")
    return_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    refund_amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    return_cargo_cost_estimated: Mapped[Decimal] = mapped_column(Money, nullable=False)
    return_cargo_cost_actual: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    cost_state: Mapped[CostState] = mapped_column(
        pg_enum(CostState, "cost_state"), nullable=False, default=CostState.ESTIMATED
    )
    # İade edilen ürün tekrar satılabilir mi (spec §12C.4)
    restocked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class SettlementRecord(Base, TimestampMixin):
    """Hakediş kalemi — mutabakatın ground truth'u (spec §7). Faz 2'de doldurulur."""

    __tablename__ = "settlement_records"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "store_id", "external_ref", name="uq_settlement_tenant_store_ref"
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    brand_id: Mapped[uuid.UUID] = brand_fk()
    store_id: Mapped[uuid.UUID] = uuid_fk("stores.id")
    external_ref: Mapped[str] = mapped_column(String(160), nullable=False)
    record_type: Mapped[SettlementRecordType] = mapped_column(
        pg_enum(SettlementRecordType, "settlement_record_type"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    vat_amount: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    order_line_id: Mapped[uuid.UUID | None] = uuid_fk_opt("order_lines.id")
    matched: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class CargoInvoice(Base, TimestampMixin):
    """Kargo faturası — desi/tutar kesinleşmesi buradan gelir (spec §5.3). Faz 2."""

    __tablename__ = "cargo_invoices"
    __table_args__ = (
        UniqueConstraint("store_id", "invoice_no", name="uq_cargo_invoices_store_invoice"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    brand_id: Mapped[uuid.UUID] = brand_fk()
    store_id: Mapped[uuid.UUID] = uuid_fk("stores.id")
    invoice_no: Mapped[str] = mapped_column(String(120), nullable=False)
    period: Mapped[str] = mapped_column(String(20), nullable=False)
    total: Mapped[Decimal] = mapped_column(Money, nullable=False)
    lines: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)


class AdSpend(Base, TimestampMixin):
    """Reklam harcaması (spec §5.3) — Faz 4; şimdilik yalnızca şema."""

    __tablename__ = "ad_spend"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    brand_id: Mapped[uuid.UUID] = brand_fk()
    store_id: Mapped[uuid.UUID] = uuid_fk("stores.id")
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    campaign_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    campaign_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    spend: Mapped[Decimal] = mapped_column(Money, nullable=False)
    product_id: Mapped[uuid.UUID | None] = uuid_fk_opt("products.id")


class Promotion(Base, TimestampMixin):
    """Kampanya ve satıcı payı (spec §5.3) — Faz 4; şimdilik yalnızca şema."""

    __tablename__ = "promotions"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    brand_id: Mapped[uuid.UUID] = brand_fk()
    store_id: Mapped[uuid.UUID] = uuid_fk("stores.id")
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    seller_share_rate: Mapped[Decimal | None] = mapped_column(Rate, nullable=True)
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
