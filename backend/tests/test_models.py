"""KVN-02: model davranışları — para hassasiyeti, izolasyon ve idempotency kısıtları."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.context import system_scope
from app.models.catalog import Product, SkuCost
from app.models.enums import (
    ChannelCode,
    CostSource,
    InventoryMovement,
    OrderStatus,
    UserRole,
)
from app.models.identity import Brand, Channel, Store, StoreCredential, Tenant, User, UserBrandRole
from app.models.inventory import InventoryLedger
from app.models.transactions import Order


@pytest.fixture(autouse=True)
def system_context() -> Iterator[None]:
    """Model testleri sistem bağlamında koşar (brand-scope guard'ı, KVN-03)."""
    with system_scope():
        yield


@pytest.fixture
def tenant(db_session: Session) -> Tenant:
    """İzole test tenant'ı."""
    tenant = Tenant(slug=f"t-{uuid.uuid4().hex[:8]}", name="Test")
    db_session.add(tenant)
    db_session.flush()
    return tenant


@pytest.fixture
def brand(db_session: Session, tenant: Tenant) -> Brand:
    """İzole test markası."""
    brand = Brand(tenant_id=tenant.id, slug="test", name="Test Marka")
    db_session.add(brand)
    db_session.flush()
    return brand


@pytest.fixture
def store(db_session: Session, tenant: Tenant, brand: Brand) -> Store:
    """İzole test mağazası."""
    channel = db_session.query(Channel).filter(Channel.code == ChannelCode.TRENDYOL).one_or_none()
    if channel is None:
        channel = Channel(code=ChannelCode.TRENDYOL, name="Trendyol")
        db_session.add(channel)
        db_session.flush()
    store = Store(
        tenant_id=tenant.id,
        brand_id=brand.id,
        channel_id=channel.id,
        external_seller_id=f"S-{uuid.uuid4().hex[:6]}",
        name="Test Mağaza",
    )
    db_session.add(store)
    db_session.flush()
    return store


def _product(db_session: Session, tenant: Tenant, brand: Brand) -> Product:
    product = Product(
        tenant_id=tenant.id,
        brand_id=brand.id,
        sku=f"SKU-{uuid.uuid4().hex[:6]}",
        name="Test Ürün",
        vat_rate=Decimal("20.00"),
    )
    db_session.add(product)
    db_session.flush()
    return product


def test_money_keeps_four_decimal_places(db_session: Session, tenant: Tenant, brand: Brand) -> None:
    """Tutarlar kuruş altı hassasiyetini kaybetmez (CLAUDE.md §1)."""
    product = _product(db_session, tenant, brand)
    db_session.add(
        SkuCost(
            product_id=product.id,
            unit_cost=Decimal("1234.5678"),
            source=CostSource.MANUAL,
            effective_from=date(2026, 1, 1),
        )
    )
    db_session.flush()
    db_session.expire_all()

    stored = db_session.query(SkuCost).filter(SkuCost.product_id == product.id).one()
    assert stored.unit_cost == Decimal("1234.5678")
    assert isinstance(stored.unit_cost, Decimal)


def test_average_cost_keeps_six_decimal_places(
    db_session: Session, tenant: Tenant, brand: Brand
) -> None:
    """WAC altı haneyle saklanır — 114,9254 örneği (spec §12C.1)."""
    product = _product(db_session, tenant, brand)
    db_session.add(
        InventoryLedger(
            tenant_id=tenant.id,
            brand_id=brand.id,
            product_id=product.id,
            movement=InventoryMovement.PURCHASE_IN,
            qty_delta=Decimal("100"),
            unit_cost_at_movement=Decimal("120.000000"),
            avg_cost_after=Decimal("114.925373"),
            on_hand_after=Decimal("134"),
            moved_at=datetime.now(UTC),
        )
    )
    db_session.flush()
    db_session.expire_all()

    stored = (
        db_session.query(InventoryLedger).filter(InventoryLedger.product_id == product.id).one()
    )
    assert stored.avg_cost_after == Decimal("114.925373")


def test_duplicate_external_order_is_rejected(
    db_session: Session, tenant: Tenant, brand: Brand, store: Store
) -> None:
    """Aynı sipariş iki kez çekilirse duplicate oluşmaz (spec §3.7 idempotency)."""

    def make_order() -> Order:
        return Order(
            tenant_id=tenant.id,
            brand_id=brand.id,
            store_id=store.id,
            external_order_id="TY-1",
            order_date=datetime.now(UTC),
            status=OrderStatus.CREATED,
            gross_total=Decimal("100.0000"),
        )

    db_session.add(make_order())
    db_session.flush()

    db_session.add(make_order())
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_transaction_tables_require_brand_id(
    db_session: Session, tenant: Tenant, store: Store
) -> None:
    """İşlem verisi taşıyan tabloda `brand_id` zorunludur (spec §3A.2)."""
    db_session.add(
        Order(
            tenant_id=tenant.id,
            brand_id=None,
            store_id=store.id,
            external_order_id="TY-NOBRAND",
            order_date=datetime.now(UTC),
            status=OrderStatus.CREATED,
            gross_total=Decimal("10.0000"),
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_product_sku_is_unique_per_brand(db_session: Session, tenant: Tenant) -> None:
    """Aynı SKU iki markada yaşayabilir, aynı markada iki kez yaşayamaz."""
    kahveji = Brand(tenant_id=tenant.id, slug="kahveji", name="Kahveji")
    alessi = Brand(tenant_id=tenant.id, slug="alessi", name="Alessi")
    db_session.add_all([kahveji, alessi])
    db_session.flush()

    for brand in (kahveji, alessi):
        db_session.add(
            Product(
                tenant_id=tenant.id,
                brand_id=brand.id,
                sku="ORTAK-SKU",
                name="Ortak",
                vat_rate=Decimal("20.00"),
            )
        )
    db_session.flush()  # iki markada aynı SKU sorun değil

    db_session.add(
        Product(
            tenant_id=tenant.id,
            brand_id=kahveji.id,
            sku="ORTAK-SKU",
            name="Kopya",
            vat_rate=Decimal("20.00"),
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_store_credential_repr_hides_payload(
    db_session: Session, tenant: Tenant, brand: Brand, store: Store
) -> None:
    """Credential içeriği repr'e sızmaz (CLAUDE.md §2)."""
    credential = StoreCredential(store_id=store.id, encrypted_payload=b"gizli-token")
    db_session.add(credential)
    db_session.flush()

    assert "gizli-token" not in repr(credential)
    assert str(store.id) in repr(credential)


def test_user_brand_role_is_unique_per_pair(
    db_session: Session, tenant: Tenant, brand: Brand
) -> None:
    """Bir kullanıcının bir markada tek rolü olur (spec §3A.3)."""
    user = User(tenant_id=tenant.id, email="a@b.com", full_name="A B")
    db_session.add(user)
    db_session.flush()

    db_session.add(UserBrandRole(user_id=user.id, brand_id=brand.id, role=UserRole.VIEWER))
    db_session.flush()

    db_session.add(UserBrandRole(user_id=user.id, brand_id=brand.id, role=UserRole.ADMIN))
    with pytest.raises(IntegrityError):
        db_session.flush()
