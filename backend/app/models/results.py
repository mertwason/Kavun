"""Hesap sonuçları ve uyarılar (spec §5.4)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import (
    Money,
    Pct,
    TimestampMixin,
    brand_fk,
    pg_enum,
    tenant_fk,
    uuid_fk,
    uuid_fk_opt,
    uuid_pk,
)
from app.models.enums import AlertSeverity, CommissionSource, DiffStatus


class LineProfit(Base):
    """Sipariş satırı kâr dökümü — motorun çıktısı (spec §6.1)."""

    __tablename__ = "line_profit"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    brand_id: Mapped[uuid.UUID] = brand_fk()
    order_line_id: Mapped[uuid.UUID] = uuid_fk("order_lines.id")
    revenue_net_vat: Mapped[Decimal] = mapped_column(Money, nullable=False)
    cost_cogs: Mapped[Decimal] = mapped_column(Money, nullable=False)
    cost_commission: Mapped[Decimal] = mapped_column(Money, nullable=False)
    cost_cargo: Mapped[Decimal] = mapped_column(Money, nullable=False)
    cost_service_fee: Mapped[Decimal] = mapped_column(Money, nullable=False)
    cost_return: Mapped[Decimal] = mapped_column(Money, nullable=False)
    cost_ad_alloc: Mapped[Decimal] = mapped_column(Money, nullable=False)
    # Spec §5.4'e ek (KVN-08): §6.3.3 ve §6.3.7 senaryolarının sonucu kaybolmasın diye.
    cost_penalty: Mapped[Decimal] = mapped_column(Money, nullable=False, server_default="0")
    revenue_campaign_support: Mapped[Decimal] = mapped_column(
        Money, nullable=False, server_default="0"
    )
    vat_net: Mapped[Decimal] = mapped_column(Money, nullable=False)
    profit: Mapped[Decimal] = mapped_column(Money, nullable=False)
    margin_pct: Mapped[Decimal] = mapped_column(Pct, nullable=False)
    commission_source: Mapped[CommissionSource | None] = mapped_column(
        pg_enum(CommissionSource, "commission_source"), nullable=True
    )
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # `is_final=False` → UI'da "tahmini" rozeti (tasarım brief'i, kalıp 2).
    is_final: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (UniqueConstraint("order_line_id", name="uq_line_profit_order_line"),)


class ProfitRevision(Base):
    """Kâr revizyon logu — append-only, geçmiş silinmez (CLAUDE.md §1, spec §6.2)."""

    __tablename__ = "profit_revisions"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    brand_id: Mapped[uuid.UUID] = brand_fk()
    order_line_id: Mapped[uuid.UUID] = uuid_fk("order_lines.id")
    field: Mapped[str] = mapped_column(String(60), nullable=False)
    old_value: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    new_value: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    reason: Mapped[str] = mapped_column(String(300), nullable=False)
    revised_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ReconciliationDiff(Base, TimestampMixin):
    """Hakediş farkı (spec §7). Faz 2'de doldurulur."""

    __tablename__ = "reconciliation_diffs"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    brand_id: Mapped[uuid.UUID] = brand_fk()
    store_id: Mapped[uuid.UUID] = uuid_fk("stores.id")
    period: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    settlement_record_id: Mapped[uuid.UUID | None] = uuid_fk_opt("settlement_records.id")
    expected: Mapped[Decimal] = mapped_column(Money, nullable=False)
    actual: Mapped[Decimal] = mapped_column(Money, nullable=False)
    diff: Mapped[Decimal] = mapped_column(Money, nullable=False)
    status: Mapped[DiffStatus] = mapped_column(
        pg_enum(DiffStatus, "diff_status"), nullable=False, default=DiffStatus.OPEN
    )
    note: Mapped[str | None] = mapped_column(String(1000), nullable=True)


class Alert(Base, TimestampMixin):
    """Uyarı. Severity üç seviye: bilgi / dikkat / kritik (tasarım brief'i, kalıp 7)."""

    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    brand_id: Mapped[uuid.UUID] = brand_fk()
    type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    severity: Mapped[AlertSeverity] = mapped_column(
        pg_enum(AlertSeverity, "alert_severity"), nullable=False
    )
    entity_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)
    message: Mapped[str] = mapped_column(String(1000), nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
