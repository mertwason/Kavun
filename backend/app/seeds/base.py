"""Çekirdek seed: tenant, kanallar, markalar, mağazalar, feature bayrakları (spec §12.5).

Idempotent: doğal anahtarlarla arar, yoksa oluşturur. İki kez çalıştırmak veriyi bozmaz.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import ChannelCode, UserRole
from app.models.identity import (
    Brand,
    BrandFeature,
    Channel,
    Store,
    Tenant,
    User,
    UserBrandRole,
)

TENANT_SLUG = "mokka"
TENANT_NAME = "Mokka Teknoloji"

CHANNELS: tuple[tuple[ChannelCode, str], ...] = (
    (ChannelCode.TRENDYOL, "Trendyol"),
    (ChannelCode.HEPSIBURADA, "Hepsiburada"),
    (ChannelCode.N11, "N11"),
    (ChannelCode.SHOPIFY, "Shopify"),
    (ChannelCode.MANUAL, "Manuel / D2B"),
)

# Marka bazlı modül bayrakları (spec §3A.4).
ALESSI_FEATURES = ("import_files", "fx_tracking", "b2b_channel", "msrp_discipline")
KAHVEJI_FEATURES: tuple[str, ...] = ()
ALL_FEATURES = ("import_files", "fx_tracking", "b2b_channel", "msrp_discipline")


@dataclass
class SeedResult:
    """Seed sonrası özet — CLI yazdırır, testler asserte eder."""

    tenant_id: str = ""
    brands: dict[str, str] = field(default_factory=dict)
    stores: dict[str, str] = field(default_factory=dict)
    created: dict[str, int] = field(default_factory=dict)

    def bump(self, key: str, amount: int = 1) -> None:
        """Sayaç artırır."""
        self.created[key] = self.created.get(key, 0) + amount


def get_or_create_tenant(session: Session, slug: str, name: str) -> Tenant:
    """Tenant'ı slug ile bulur, yoksa oluşturur."""
    tenant = session.scalar(select(Tenant).where(Tenant.slug == slug))
    if tenant is None:
        tenant = Tenant(slug=slug, name=name)
        session.add(tenant)
        session.flush()
    return tenant


def ensure_channels(session: Session, result: SeedResult) -> dict[ChannelCode, Channel]:
    """Kanal listesini garanti eder (tenant'tan bağımsız, global tablo)."""
    channels: dict[ChannelCode, Channel] = {}
    for code, name in CHANNELS:
        channel = session.scalar(select(Channel).where(Channel.code == code))
        if channel is None:
            channel = Channel(code=code, name=name)
            session.add(channel)
            session.flush()
            result.bump("channels")
        channels[code] = channel
    return channels


def ensure_brand(
    session: Session,
    tenant: Tenant,
    slug: str,
    name: str,
    result: SeedResult,
    *,
    min_margin_floor_pct: Decimal | None = None,
    default_vat_rate: Decimal | None = None,
    features: tuple[str, ...] = (),
) -> Brand:
    """Markayı ve marka bazlı feature bayraklarını garanti eder."""
    brand = session.scalar(select(Brand).where(Brand.tenant_id == tenant.id, Brand.slug == slug))
    if brand is None:
        brand = Brand(
            tenant_id=tenant.id,
            slug=slug,
            name=name,
            min_margin_floor_pct=min_margin_floor_pct,
            default_vat_rate=default_vat_rate,
        )
        session.add(brand)
        session.flush()
        result.bump("brands")

    # Bayraklar her marka için TAM liste halinde yazılır: açık olanlar True,
    # diğerleri açıkça False — "kayıt yok" ile "kapalı" karışmasın.
    for feature_code in ALL_FEATURES:
        enabled = feature_code in features
        existing = session.scalar(
            select(BrandFeature).where(
                BrandFeature.brand_id == brand.id,
                BrandFeature.feature_code == feature_code,
            )
        )
        if existing is None:
            session.add(BrandFeature(brand_id=brand.id, feature_code=feature_code, enabled=enabled))
            result.bump("brand_features")
        elif existing.enabled != enabled:
            existing.enabled = enabled
    session.flush()
    return brand


def ensure_store(
    session: Session,
    tenant: Tenant,
    brand: Brand,
    channel: Channel,
    name: str,
    result: SeedResult,
    *,
    external_seller_id: str | None = None,
    service_fee_per_order: Decimal | None = None,
) -> Store:
    """Mağazayı garanti eder."""
    store = session.scalar(
        select(Store).where(
            Store.tenant_id == tenant.id,
            Store.channel_id == channel.id,
            Store.external_seller_id == external_seller_id,
        )
    )
    if store is None:
        store = Store(
            tenant_id=tenant.id,
            brand_id=brand.id,
            channel_id=channel.id,
            external_seller_id=external_seller_id,
            name=name,
            service_fee_per_order=service_fee_per_order,
        )
        session.add(store)
        session.flush()
        result.bump("stores")
    return store


def ensure_user(
    session: Session,
    tenant: Tenant,
    email: str,
    full_name: str,
    brands: list[Brand],
    result: SeedResult,
    *,
    role: UserRole = UserRole.ADMIN,
    is_holding_viewer: bool = False,
) -> User:
    """Kullanıcıyı ve marka rollerini garanti eder (spec §3A.3)."""
    user = session.scalar(select(User).where(User.tenant_id == tenant.id, User.email == email))
    if user is None:
        user = User(
            tenant_id=tenant.id,
            email=email,
            full_name=full_name,
            is_holding_viewer=is_holding_viewer,
        )
        session.add(user)
        session.flush()
        result.bump("users")

    for brand in brands:
        existing = session.scalar(
            select(UserBrandRole).where(
                UserBrandRole.user_id == user.id, UserBrandRole.brand_id == brand.id
            )
        )
        if existing is None:
            session.add(UserBrandRole(user_id=user.id, brand_id=brand.id, role=role))
            result.bump("user_brand_roles")
    session.flush()
    return user


def seed_base(session: Session) -> SeedResult:
    """Gerçek çalışma için minimum veri: mokka tenant, 2 marka, kanallar, mağazalar."""
    result = SeedResult()
    tenant = get_or_create_tenant(session, TENANT_SLUG, TENANT_NAME)
    result.tenant_id = str(tenant.id)

    channels = ensure_channels(session, result)

    kahveji = ensure_brand(
        session,
        tenant,
        "kahveji",
        "Kahveji",
        result,
        min_margin_floor_pct=Decimal("12.00"),
        default_vat_rate=Decimal("1.00"),
        features=KAHVEJI_FEATURES,
    )
    alessi = ensure_brand(
        session,
        tenant,
        "alessi",
        "Alessi",
        result,
        min_margin_floor_pct=Decimal("18.00"),
        default_vat_rate=Decimal("20.00"),
        features=ALESSI_FEATURES,
    )
    result.brands = {"kahveji": str(kahveji.id), "alessi": str(alessi.id)}

    kahveji_ty = ensure_store(
        session,
        tenant,
        kahveji,
        channels[ChannelCode.TRENDYOL],
        "Kahveji — Trendyol",
        result,
        external_seller_id="KHV-SELLER",
        service_fee_per_order=Decimal("8.99"),
    )
    alessi_ty = ensure_store(
        session,
        tenant,
        alessi,
        channels[ChannelCode.TRENDYOL],
        "Alessi — Trendyol",
        result,
        external_seller_id="ALS-SELLER",
        service_fee_per_order=Decimal("8.99"),
    )
    alessi_d2b = ensure_store(
        session,
        tenant,
        alessi,
        channels[ChannelCode.MANUAL],
        "Alessi D2B",
        result,
        external_seller_id="ALS-D2B",
    )
    result.stores = {
        "kahveji_trendyol": str(kahveji_ty.id),
        "alessi_trendyol": str(alessi_ty.id),
        "alessi_d2b": str(alessi_d2b.id),
    }

    ensure_user(
        session,
        tenant,
        "mert@mokkalabs.com",
        "Mert",
        [kahveji, alessi],
        result,
        role=UserRole.ADMIN,
        is_holding_viewer=True,
    )
    return result
