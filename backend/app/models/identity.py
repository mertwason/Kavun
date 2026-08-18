"""Kimlik ve yapı tabloları (spec §5.1, §3A)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, LargeBinary, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import (
    Money,
    Pct,
    TimestampMixin,
    VatRate,
    brand_fk,
    pg_enum,
    tenant_fk,
    uuid_fk,
    uuid_pk,
)
from app.models.enums import ChannelCode, UserRole


class Tenant(Base, TimestampMixin):
    """Kiracı. Şimdilik tek tenant: `mokka` (+ demo verisi için `demo`)."""

    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = uuid_pk()
    slug: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)


class Brand(Base, TimestampMixin):
    """Marka workspace'i — Kahveji, Alessi (spec §3A.1)."""

    __tablename__ = "brands"
    __table_args__ = (UniqueConstraint("tenant_id", "slug", name="uq_brands_tenant_slug"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    slug: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # Marka bazlı varsayılan marj tabanı; ürün seviyesinde ezilebilir (spec §12C.10).
    min_margin_floor_pct: Mapped[Decimal | None] = mapped_column(Pct, nullable=True)
    default_vat_rate: Mapped[Decimal | None] = mapped_column(VatRate, nullable=True)


class Channel(Base):
    """Satış kanalı — kanal listesi sabittir (spec §5.1)."""

    __tablename__ = "channels"

    id: Mapped[uuid.UUID] = uuid_pk()
    code: Mapped[ChannelCode] = mapped_column(
        pg_enum(ChannelCode, "channel_code"), nullable=False, unique=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)


class Store(Base, TimestampMixin):
    """Marka + kanal kesişimi: bir mağaza hesabı (spec §5.1)."""

    __tablename__ = "stores"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "channel_id", "external_seller_id", name="uq_stores_tenant_channel_seller"
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    brand_id: Mapped[uuid.UUID] = brand_fk()
    channel_id: Mapped[uuid.UUID] = uuid_fk("channels.id", ondelete="RESTRICT")
    external_seller_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Sipariş başına platform hizmet bedeli (spec §6.1); tutar bazlı satırlara paylaştırılır.
    service_fee_per_order: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class StoreCredential(Base, TimestampMixin):
    """API credential'ları — Fernet ile şifreli (spec §3.6). Loglara asla yazılmaz."""

    __tablename__ = "store_credentials"

    id: Mapped[uuid.UUID] = uuid_pk()
    store_id: Mapped[uuid.UUID] = uuid_fk("stores.id")
    encrypted_payload: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        """Şifreli içerik repr'e ASLA sızmaz."""
        return f"<StoreCredential store_id={self.store_id}>"


class User(Base, TimestampMixin):
    """Kullanıcı. Kimlik doğrulama ops.mokka SSO ile yapılır (spec §8)."""

    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Markalar arası konsolide raporları görebilme yetkisi (spec §3A.3).
    is_holding_viewer: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class UserBrandRole(Base, TimestampMixin):
    """Kullanıcı yalnızca yetkili olduğu workspace'i görür (spec §3A.3)."""

    __tablename__ = "user_brand_roles"
    __table_args__ = (
        UniqueConstraint("user_id", "brand_id", name="uq_user_brand_roles_user_brand"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = uuid_fk("users.id")
    brand_id: Mapped[uuid.UUID] = brand_fk()
    role: Mapped[UserRole] = mapped_column(pg_enum(UserRole, "user_role"), nullable=False)


class BrandFeature(Base, TimestampMixin):
    """Marka bazlı modül bayrağı — kapalı modülün endpoint'i 404 döner (spec §3A.4)."""

    __tablename__ = "brand_features"
    __table_args__ = (
        UniqueConstraint("brand_id", "feature_code", name="uq_brand_features_brand_feature"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    brand_id: Mapped[uuid.UUID] = brand_fk()
    feature_code: Mapped[str] = mapped_column(String(50), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class AuditLog(Base, TimestampMixin):
    """Holding bypass'ı gibi ayrıcalıklı erişimler her seferinde buraya yazılır (spec §3A.2)."""

    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    user_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)
    detail: Mapped[str | None] = mapped_column(String(1000), nullable=True)
