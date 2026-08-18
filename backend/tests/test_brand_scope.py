"""KVN-03: brand-scope guard'ı — fail-closed marka izolasyonu (spec §3A.2, §3A.6).

Bu dosyadaki negatif testler silinemez (CLAUDE.md §2).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.context import brand_scope, holding_scope, system_scope
from app.core.scoping import BrandScopeViolation, brand_scoped_tables, has_brand_filter
from app.models.catalog import Product
from app.models.enums import OrderStatus
from app.models.identity import Brand, Tenant
from app.models.results import Alert
from app.models.transactions import Order


@pytest.fixture
def two_brands(db_session: Session) -> tuple[Tenant, Brand, Brand]:
    """Aynı tenant altında iki marka + her birinde ürün, sipariş ve uyarı."""
    with system_scope():
        tenant = Tenant(slug=f"t-{uuid.uuid4().hex[:8]}", name="Test")
        db_session.add(tenant)
        db_session.flush()

        brands = []
        for slug in ("alessi", "kahveji"):
            brand = Brand(tenant_id=tenant.id, slug=slug, name=slug.title())
            db_session.add(brand)
            db_session.flush()
            db_session.add(
                Product(
                    tenant_id=tenant.id,
                    brand_id=brand.id,
                    sku=f"{slug.upper()}-1",
                    name=f"{slug} ürünü",
                    vat_rate=Decimal("20.00"),
                )
            )
            db_session.add(
                Alert(
                    tenant_id=tenant.id,
                    brand_id=brand.id,
                    type="test",
                    severity="info",
                    message=f"{slug} uyarısı",
                )
            )
            brands.append(brand)
        db_session.flush()
    return tenant, brands[0], brands[1]


# --- fail-closed: bağlamsız sorgu ------------------------------------------


@pytest.mark.parametrize("model", [Product, Order, Alert])
def test_query_without_brand_context_raises(db_session: Session, model: type) -> None:
    """Marka bağlamı olmadan marka-kapsamlı tabloya sorgu atılamaz (en az 3 tablo)."""
    with pytest.raises(BrandScopeViolation):
        db_session.scalars(select(model)).all()


def test_violation_message_names_the_table(db_session: Session) -> None:
    """Hata mesajı hangi tablonun korunduğunu söyler (geliştirici teşhisi için)."""
    with pytest.raises(BrandScopeViolation) as exc_info:
        db_session.scalars(select(Product)).all()
    assert "products" in str(exc_info.value)


def test_unscoped_tables_are_not_blocked(db_session: Session) -> None:
    """`brand_id` taşımayan tablolar (tenants, channels) guard'a takılmaz."""
    assert db_session.scalar(select(func.count()).select_from(Tenant)) is not None


def test_update_without_brand_context_raises(
    db_session: Session, two_brands: tuple[Tenant, Brand, Brand]
) -> None:
    """Yazma sorguları da korunur — sessiz toplu güncelleme olmaz."""
    from sqlalchemy import update

    with pytest.raises(BrandScopeViolation):
        db_session.execute(update(Product).values(name="hepsi değişti"))


# --- otomatik filtre: bağlam varken ----------------------------------------


def test_brand_scope_filters_automatically(
    db_session: Session, two_brands: tuple[Tenant, Brand, Brand]
) -> None:
    """Filtre yazılmasa bile yalnızca aktif markanın verisi döner."""
    tenant, alessi, kahveji = two_brands

    with brand_scope(tenant.id, alessi.id, brand_slug="alessi"):
        products = db_session.scalars(select(Product)).all()
    assert [product.sku for product in products] == ["ALESSI-1"]

    with brand_scope(tenant.id, kahveji.id, brand_slug="kahveji"):
        products = db_session.scalars(select(Product)).all()
    assert [product.sku for product in products] == ["KAHVEJI-1"]


def test_cross_brand_filter_returns_nothing(
    db_session: Session, two_brands: tuple[Tenant, Brand, Brand]
) -> None:
    """Alessi bağlamında Kahveji'nin id'siyle sorgu atılsa bile veri sızmaz."""
    tenant, alessi, kahveji = two_brands

    with brand_scope(tenant.id, alessi.id):
        leaked = db_session.scalars(select(Product).where(Product.brand_id == kahveji.id)).all()
    assert leaked == []


def test_count_queries_are_scoped(
    db_session: Session, two_brands: tuple[Tenant, Brand, Brand]
) -> None:
    """Toplama sorguları da markaya kısıtlanır — KPI'lar karşı markayı saymaz."""
    tenant, alessi, _ = two_brands
    with brand_scope(tenant.id, alessi.id):
        total = db_session.scalar(select(func.count()).select_from(Alert))
    assert total == 1


# --- bilinçli bypass'lar ---------------------------------------------------


def test_holding_scope_sees_all_brands(
    db_session: Session, two_brands: tuple[Tenant, Brand, Brand]
) -> None:
    """Holding görünümü markalar arası okur (spec §3A.3)."""
    tenant, _, _ = two_brands
    with holding_scope(tenant.id):
        skus = sorted(product.sku for product in db_session.scalars(select(Product)).all())
    assert skus == ["ALESSI-1", "KAHVEJI-1"]


def test_system_scope_sees_all_brands(
    db_session: Session, two_brands: tuple[Tenant, Brand, Brand]
) -> None:
    """Seed/replay gibi sistem işleri filtresiz çalışabilir."""
    tenant, _, _ = two_brands
    with system_scope(tenant.id):
        assert db_session.scalar(select(func.count()).select_from(Product)) == 2


def test_nested_system_scope_restores_previous_context(
    db_session: Session, two_brands: tuple[Tenant, Brand, Brand]
) -> None:
    """Sistem bloğundan çıkınca marka bağlamı geri gelir — bypass sızmaz."""
    tenant, alessi, _ = two_brands
    with brand_scope(tenant.id, alessi.id):
        with system_scope():
            assert db_session.scalar(select(func.count()).select_from(Product)) == 2
        assert db_session.scalar(select(func.count()).select_from(Product)) == 1


# --- yardımcılar -----------------------------------------------------------


def test_brand_scoped_tables_detects_joined_tables() -> None:
    """Join'lenen marka-kapsamlı tablolar da tespit edilir."""
    statement = select(Product).join(Order, Order.brand_id == Product.brand_id)
    assert brand_scoped_tables(statement) == {"products", "orders"}


def test_has_brand_filter_detects_explicit_condition() -> None:
    """Core sorgularında açık `brand_id` koşulu tanınır."""
    brand_id = uuid.uuid4()
    assert has_brand_filter(select(Product).where(Product.brand_id == brand_id))
    assert not has_brand_filter(select(Product).where(Product.sku == "X"))


def test_core_query_is_scoped_too(
    db_session: Session, two_brands: tuple[Tenant, Brand, Brand]
) -> None:
    """ORM varlığı olmayan (Core) sorgular da üst seviye FROM üzerinden kısıtlanır."""
    tenant, alessi, _ = two_brands
    table = Product.__table__

    with brand_scope(tenant.id, alessi.id):
        rows = db_session.execute(select(table.c.sku)).all()
    assert [row.sku for row in rows] == ["ALESSI-1"]


def test_subquery_only_reference_requires_explicit_filter(
    db_session: Session, two_brands: tuple[Tenant, Brand, Brand]
) -> None:
    """Alt sorguda kalan tablo otomatik filtre alamaz; kendi koşulunu taşımalı."""
    tenant, alessi, _ = two_brands
    unfiltered = select(Product.id).subquery()

    with brand_scope(tenant.id, alessi.id):
        with pytest.raises(BrandScopeViolation):
            db_session.scalar(select(func.count()).select_from(unfiltered))

        filtered = select(Product.id).where(Product.brand_id == alessi.id).subquery()
        assert db_session.scalar(select(func.count()).select_from(filtered)) == 1


def test_orders_are_scoped_for_reporting(
    db_session: Session, two_brands: tuple[Tenant, Brand, Brand]
) -> None:
    """Sipariş tablosu da kapsanır — rapor sorguları karşı markayı toplamaz."""
    tenant, alessi, kahveji = two_brands
    with system_scope():
        from app.models.enums import ChannelCode
        from app.models.identity import Channel, Store

        channel = db_session.scalar(select(Channel).where(Channel.code == ChannelCode.TRENDYOL))
        if channel is None:
            channel = Channel(code=ChannelCode.TRENDYOL, name="Trendyol")
            db_session.add(channel)
            db_session.flush()
        for brand in (alessi, kahveji):
            store = Store(
                tenant_id=tenant.id,
                brand_id=brand.id,
                channel_id=channel.id,
                external_seller_id=f"S-{brand.slug}-{uuid.uuid4().hex[:4]}",
                name=f"{brand.slug} mağaza",
            )
            db_session.add(store)
            db_session.flush()
            db_session.add(
                Order(
                    tenant_id=tenant.id,
                    brand_id=brand.id,
                    store_id=store.id,
                    external_order_id=f"{brand.slug}-1",
                    order_date=datetime.now(UTC),
                    status=OrderStatus.DELIVERED,
                    gross_total=Decimal("100.0000"),
                )
            )
        db_session.flush()

    with brand_scope(tenant.id, alessi.id):
        orders = db_session.scalars(select(Order)).all()
    assert [order.external_order_id for order in orders] == ["alessi-1"]
