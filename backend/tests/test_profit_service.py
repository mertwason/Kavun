"""KVN-07: kâr hesabının DB katmanı — girdi toplama, yazma, revizyon logu (spec §6.2)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.context import system_scope
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
from app.models.results import LineProfit, ProfitRevision
from app.models.transactions import Order, OrderLine, Return, Shipment
from app.seeds.base import seed_base
from app.services import profit as profit_service
from app.services.commission import resolve_commission

D = Decimal
ORDER_DATE = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def system_context() -> Iterator[None]:
    """Kâr hesabı bir sistem işidir (KVN-03 guard'ı)."""
    with system_scope():
        yield


@pytest.fixture
def store(db_session: Session) -> Store:
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


def _product(
    db_session: Session,
    store: Store,
    sku: str,
    *,
    vat: Decimal = D("20.00"),
    cost: Decimal = D("50.0000"),
    desi: Decimal = D("1.00"),
    category: str = "Kahve/Harman",
) -> Product:
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


def _commission(
    db_session: Session,
    store: Store,
    *,
    rate: Decimal = D("0.2000"),
    category: str = "Kahve/Harman",
    source: CommissionSource = CommissionSource.MANUAL_TARIFF_UPLOAD,
    valid_from: datetime | None = None,
) -> CommissionRate:
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


def _order(
    db_session: Session,
    store: Store,
    lines: list[tuple[Product, int, Decimal]],
    *,
    cargo: Decimal | None = D("24.0000"),
    status: OrderStatus = OrderStatus.DELIVERED,
) -> Order:
    order = Order(
        tenant_id=store.tenant_id,
        brand_id=store.brand_id,
        store_id=store.id,
        external_order_id=f"TY-{datetime.now(UTC).timestamp()}",
        order_date=ORDER_DATE,
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


# --- komisyon çözümleme (spec §12B.1) ---------------------------------------


def test_commission_hierarchy_prefers_product_over_category(
    db_session: Session, store: Store
) -> None:
    """Ürün bazlı oran kategori tarifesini ezer."""
    product = _product(db_session, store, "SKU-1")
    _commission(db_session, store, rate=D("0.2000"))
    db_session.add(
        CommissionRate(
            store_id=store.id,
            scope=CommissionScope.PRODUCT,
            product_id=product.id,
            rate=D("0.1500"),
            source=CommissionSource.API_PRODUCT,
            valid_from=ORDER_DATE.date() - timedelta(days=10),
        )
    )
    db_session.flush()

    rate, source = resolve_commission(
        db_session, store_id=store.id, product=product, on_date=ORDER_DATE.date()
    )
    assert rate is not None and rate.rate == D("0.1500")
    assert source is CommissionSource.API_PRODUCT


def test_settlement_actual_wins_over_everything(db_session: Session, store: Store) -> None:
    """Hakedişten gelen oran ground truth'tur (spec §12B.1)."""
    product = _product(db_session, store, "SKU-2")
    db_session.add(
        CommissionRate(
            store_id=store.id,
            scope=CommissionScope.PRODUCT,
            product_id=product.id,
            rate=D("0.1500"),
            source=CommissionSource.API_PRODUCT,
            valid_from=ORDER_DATE.date() - timedelta(days=10),
        )
    )
    db_session.add(
        CommissionRate(
            store_id=store.id,
            scope=CommissionScope.PRODUCT,
            product_id=product.id,
            rate=D("0.1725"),
            source=CommissionSource.SETTLEMENT_ACTUAL,
            valid_from=ORDER_DATE.date() - timedelta(days=5),
        )
    )
    db_session.flush()

    rate, source = resolve_commission(
        db_session, store_id=store.id, product=product, on_date=ORDER_DATE.date()
    )
    assert rate is not None and rate.rate == D("0.1725")
    assert source is CommissionSource.SETTLEMENT_ACTUAL


def test_no_commission_rate_returns_none(db_session: Session, store: Store) -> None:
    """Oran yoksa uydurulmaz (KVN-05: Trendyol'da komisyon API'si yok)."""
    product = _product(db_session, store, "SKU-3")
    assert resolve_commission(
        db_session, store_id=store.id, product=product, on_date=ORDER_DATE.date()
    ) == (None, None)


def test_future_tariff_is_not_used_for_past_orders(db_session: Session, store: Store) -> None:
    """İleri tarihli tarife geçmiş siparişe uygulanmaz (tarih penceresi)."""
    product = _product(db_session, store, "SKU-4")
    _commission(db_session, store, rate=D("0.2000"))
    _commission(db_session, store, rate=D("0.2300"), valid_from=ORDER_DATE + timedelta(days=30))

    rate, _ = resolve_commission(
        db_session, store_id=store.id, product=product, on_date=ORDER_DATE.date()
    )
    assert rate is not None and rate.rate == D("0.2000")


# --- kâr hesabı (DB katmanı) ------------------------------------------------


def test_recompute_writes_line_profit(db_session: Session, store: Store) -> None:
    """Hesap sonucu `line_profit`'e yazılır ve tarihli maliyet kullanılır."""
    product = _product(db_session, store, "SKU-10")
    _commission(db_session, store)
    order = _order(db_session, store, [(product, 1, D("120.0000"))])

    summary = profit_service.recompute_orders(db_session, order_ids=[order.id])

    assert summary.created == 1
    record = db_session.scalar(select(LineProfit))
    assert record is not None
    assert record.revenue_net_vat == D("100.0000")
    assert record.cost_cogs == D("60.0000")
    assert record.cost_commission == D("24.0000")
    assert record.cost_service_fee == D("12.0000")
    assert record.commission_source is CommissionSource.MANUAL_TARIFF_UPLOAD
    assert record.brand_id == store.brand_id


def test_cargo_is_allocated_by_desi(db_session: Session, store: Store) -> None:
    """Aynı pakette çoklu satır → kargo desi ağırlıklı dağılır (spec §6.3.6)."""
    heavy = _product(db_session, store, "SKU-HEAVY", desi=D("3.00"))
    light = _product(db_session, store, "SKU-LIGHT", desi=D("1.00"))
    _commission(db_session, store)
    order = _order(
        db_session,
        store,
        [(heavy, 1, D("120.0000")), (light, 1, D("120.0000"))],
        cargo=D("100.0000"),
    )

    profit_service.recompute_orders(db_session, order_ids=[order.id])

    records = {
        line.external_line_id: record
        for line, record in db_session.execute(
            select(OrderLine, LineProfit).join(LineProfit, LineProfit.order_line_id == OrderLine.id)
        ).all()
    }
    assert records["L0"].cost_cargo == D("75.0000")
    assert records["L1"].cost_cargo == D("25.0000")
    # Kuruş kaybolmaz.
    assert records["L0"].cost_cargo + records["L1"].cost_cargo == D("100.0000")


def test_service_fee_is_allocated_by_amount(db_session: Session, store: Store) -> None:
    """Hizmet bedeli satırlara tutar ağırlıklı paylaştırılır (spec §6.1)."""
    big = _product(db_session, store, "SKU-BIG")
    small = _product(db_session, store, "SKU-SMALL")
    _commission(db_session, store)
    order = _order(db_session, store, [(big, 1, D("300.0000")), (small, 1, D("100.0000"))])

    profit_service.recompute_orders(db_session, order_ids=[order.id])

    parts = sorted(
        record.cost_service_fee for record in db_session.scalars(select(LineProfit)).all()
    )
    assert parts == [D("3.0000"), D("9.0000")]
    assert sum(parts, D("0")) == D("12.0000")


def test_actual_cargo_cost_is_preferred(db_session: Session, store: Store) -> None:
    """Kesinleşmiş kargo maliyeti tahmini ezer (spec §3.4)."""
    product = _product(db_session, store, "SKU-11")
    _commission(db_session, store)
    order = _order(db_session, store, [(product, 1, D("120.0000"))], cargo=D("24.0000"))
    shipment = db_session.scalar(select(Shipment).where(Shipment.order_id == order.id))
    assert shipment is not None
    shipment.cargo_cost_actual = D("31.5000")
    shipment.cost_state = CostState.ACTUAL
    db_session.flush()

    profit_service.recompute_orders(db_session, order_ids=[order.id])

    record = db_session.scalar(select(LineProfit))
    assert record is not None
    assert record.cost_cargo == D("31.5000")
    # Kesinleşmiş maliyetle hesaplanan kâr "tahmini" değil (UI rozeti bundan beslenir).
    assert record.is_final is True


def test_return_reduces_revenue(db_session: Session, store: Store) -> None:
    """İade edilen adet gelirden düşer; iade tutarı ayrıca gider yazılmaz."""
    product = _product(db_session, store, "SKU-12")
    _commission(db_session, store)
    order = _order(db_session, store, [(product, 2, D("240.0000"))])
    line = db_session.scalar(select(OrderLine).where(OrderLine.order_id == order.id))
    assert line is not None
    db_session.add(
        Return(
            tenant_id=store.tenant_id,
            brand_id=store.brand_id,
            order_line_id=line.id,
            return_date=ORDER_DATE + timedelta(days=3),
            qty=1,
            refund_amount=D("120.0000"),
            return_cargo_cost_estimated=D("24.0000"),
            restocked=True,
        )
    )
    db_session.flush()

    profit_service.recompute_orders(db_session, order_ids=[order.id])

    record = db_session.scalar(select(LineProfit))
    assert record is not None
    assert record.revenue_net_vat == D("100.0000")  # 2 adetin 1'i kaldı
    assert record.cost_return == D("24.0000")  # yalnızca dönüş kargosu


def test_recompute_logs_revisions(db_session: Session, store: Store) -> None:
    """Değişen değerler `profit_revisions`'a append-only loglanır (spec §6.2)."""
    product = _product(db_session, store, "SKU-13")
    _commission(db_session, store)
    order = _order(db_session, store, [(product, 1, D("120.0000"))])
    profit_service.recompute_orders(db_session, order_ids=[order.id])

    # Maliyet güncellendi (geçmişe etkili yeni sku_costs kaydı).
    db_session.add(
        SkuCost(
            product_id=product.id,
            unit_cost=D("70.0000"),
            source=CostSource.INVOICE_WAC,
            effective_from=ORDER_DATE.date() - timedelta(days=1),
        )
    )
    db_session.flush()

    summary = profit_service.recompute_orders(db_session, order_ids=[order.id])

    assert summary.updated == 1
    assert summary.revisions >= 1
    revisions = db_session.scalars(select(ProfitRevision)).all()
    fields = {revision.field for revision in revisions}
    assert {"cost_cogs", "profit"} <= fields
    cogs_revision = next(r for r in revisions if r.field == "cost_cogs")
    assert cogs_revision.old_value == D("60.0000")
    assert cogs_revision.new_value == D("84.0000")  # 70 net + 14 KDV


def test_recompute_is_idempotent(db_session: Session, store: Store) -> None:
    """Aynı girdiyle ikinci hesap yeni revizyon üretmez."""
    product = _product(db_session, store, "SKU-14")
    _commission(db_session, store)
    order = _order(db_session, store, [(product, 1, D("120.0000"))])

    profit_service.recompute_orders(db_session, order_ids=[order.id])
    second = profit_service.recompute_orders(db_session, order_ids=[order.id])

    assert second.revisions == 0
    assert db_session.scalar(select(func.count()).select_from(LineProfit)) == 1


def test_recompute_pending_only_touches_missing_lines(db_session: Session, store: Store) -> None:
    """Zincir yalnızca kâr kaydı olmayan satırları hesaplar."""
    product = _product(db_session, store, "SKU-15")
    _commission(db_session, store)
    _order(db_session, store, [(product, 1, D("120.0000"))])

    first = profit_service.recompute_pending(db_session)
    second = profit_service.recompute_pending(db_session)

    assert first.created == 1
    assert second.created == 0 and second.lines == 0


def test_line_without_product_is_computed_with_warning(db_session: Session, store: Store) -> None:
    """Ürünle eşleşmemiş satır düşürülmez; maliyetsiz hesaplanır ve uyarı sayılır."""
    product = _product(db_session, store, "SKU-16")
    _commission(db_session, store)
    order = _order(db_session, store, [(product, 1, D("120.0000"))])
    line = db_session.scalar(select(OrderLine).where(OrderLine.order_id == order.id))
    assert line is not None
    line.product_id = None
    db_session.flush()

    summary = profit_service.recompute_orders(db_session, order_ids=[order.id])

    assert summary.warnings.get("maliyet_yok") == 1
    record = db_session.scalar(select(LineProfit))
    assert record is not None and record.cost_cogs == D("0.0000")


def test_cancelled_order_produces_zero_profit(db_session: Session, store: Store) -> None:
    """İptal edilen sipariş sıfır kâr/maliyet üretir (spec §6.3.5)."""
    product = _product(db_session, store, "SKU-17")
    _commission(db_session, store)
    order = _order(
        db_session, store, [(product, 1, D("120.0000"))], status=OrderStatus.CANCELLED, cargo=None
    )

    profit_service.recompute_orders(db_session, order_ids=[order.id])

    record = db_session.scalar(select(LineProfit))
    assert record is not None
    assert record.profit == D("0.0000")
    assert record.cost_cargo == D("0.0000")
