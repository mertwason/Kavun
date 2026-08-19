"""Kâr testleri için ortak DB kurulum yardımcıları (KVN-07 / KVN-08).

Test değil, test verisi üreticisi: mağaza, ürün + maliyet + desi, komisyon tarifesi,
sipariş + satır + gönderi. `test_profit_service.py` ve `test_profit_edge_cases.py`
ikisi de buradan besleniyor ki senaryolar aynı zeminde karşılaştırılabilsin.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.catalog import CommissionRate, Product, SkuCost, SkuLogistics
from app.models.enums import (
    ChannelCode,
    CommissionScope,
    CommissionSource,
    CostSource,
    CostState,
    OrderStatus,
)
from app.models.identity import Channel, Store
from app.models.transactions import Order, OrderLine, Shipment
from app.seeds.base import seed_base

D = Decimal
ORDER_DATE = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)


def make_store(db_session: Session) -> Store:
    """Hizmet bedeli tanımlı Trendyol mağazası."""
    seed_base(db_session)
    channel = db_session.scalar(select(Channel).where(Channel.code == ChannelCode.TRENDYOL))
    assert channel is not None
    store = db_session.scalar(
        select(Store).where(Store.channel_id == channel.id).order_by(Store.name)
    )
    assert store is not None
    store.service_fee_per_order = D("12.0000")
    db_session.flush()
    return store


def make_product(
    db_session: Session,
    store: Store,
    sku: str,
    *,
    vat: Decimal = D("20.00"),
    cost: Decimal = D("50.0000"),
    desi: Decimal = D("1.00"),
    category: str = "Kahve/Harman",
) -> Product:
    """Maliyeti ve desisi tanımlı ürün."""
    product = Product(
        tenant_id=store.tenant_id,
        brand_id=store.brand_id,
        sku=sku,
        name=sku,
        category=category,
        vat_rate=vat,
    )
    db_session.add(product)
    db_session.flush()
    db_session.add(
        SkuCost(
            product_id=product.id,
            unit_cost=cost,
            source=CostSource.INVOICE_WAC,
            effective_from=ORDER_DATE.date() - timedelta(days=30),
        )
    )
    db_session.add(
        SkuLogistics(
            product_id=product.id,
            desi=desi,
            effective_from=ORDER_DATE.date() - timedelta(days=30),
        )
    )
    db_session.flush()
    return product


def make_commission(
    db_session: Session,
    store: Store,
    *,
    rate: Decimal = D("0.2000"),
    category: str = "Kahve/Harman",
    source: CommissionSource = CommissionSource.MANUAL_TARIFF_UPLOAD,
    valid_from: datetime | None = None,
) -> CommissionRate:
    """Kategori bazlı komisyon tarifesi."""
    record = CommissionRate(
        store_id=store.id,
        scope=CommissionScope.CATEGORY,
        category_code=category,
        rate=rate,
        source=source,
        valid_from=(valid_from or ORDER_DATE - timedelta(days=60)).date(),
    )
    db_session.add(record)
    db_session.flush()
    return record


def make_order(
    db_session: Session,
    store: Store,
    lines: list[tuple[Product, int, Decimal]],
    *,
    cargo: Decimal | None = D("24.0000"),
    status: OrderStatus = OrderStatus.DELIVERED,
    order_date: datetime | None = None,
) -> Order:
    """Sipariş + satırlar + (istenirse) gönderi."""
    placed_at = order_date or ORDER_DATE
    order = Order(
        tenant_id=store.tenant_id,
        brand_id=store.brand_id,
        store_id=store.id,
        external_order_id=f"TY-{datetime.now(UTC).timestamp()}",
        order_date=placed_at,
        status=status,
        gross_total=sum((gross for _, _, gross in lines), D("0")),
        currency="TRY",
    )
    db_session.add(order)
    db_session.flush()

    for index, (product, qty, gross) in enumerate(lines):
        db_session.add(
            OrderLine(
                tenant_id=store.tenant_id,
                brand_id=store.brand_id,
                order_id=order.id,
                product_id=product.id,
                external_line_id=f"L{index}",
                qty=qty,
                unit_sale_price=gross / qty,
                line_gross=gross,
                vat_rate=product.vat_rate,
                status=status,
            )
        )
    if cargo is not None:
        db_session.add(
            Shipment(
                tenant_id=store.tenant_id,
                brand_id=store.brand_id,
                order_id=order.id,
                cargo_cost_estimated=cargo,
                cost_state=CostState.ESTIMATED,
            )
        )
    db_session.flush()
    return order
