"""Dashboard, SKU marj listesi ve sipariş detayı için okuma sorguları (spec §10).

Bu katman hesap YAPMAZ — kâr motorunun `line_profit`'e yazdığı sonuçları toplar.
Aynı sayının iki farklı yerde hesaplanması (motorda bir, SQL'de bir) mutabakatı
imkânsız kılardı; tek doğruluk kaynağı motordur (CLAUDE.md §1).

Marka filtresi yazılmaz: brand-scope guard (KVN-03) her sorguya otomatik ekler.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.engine.vat import quantize_money
from app.models.catalog import Product
from app.models.enums import CommissionSource, OrderStatus
from app.models.identity import Store
from app.models.results import LineProfit
from app.models.transactions import Order, OrderLine, Return

ZERO = Decimal("0")

# Kâr hesabına girmeyen statüler — ciroyu ve marjı bozmasınlar (spec §6.3.5).
EXCLUDED_STATUSES = (OrderStatus.CANCELLED,)


@dataclass(frozen=True)
class Step:
    """Şelale adımı: `key` frontend'de tr.json'dan etikete çevrilir."""

    key: str
    amount: Decimal


@dataclass(frozen=True)
class Period:
    """Kapalı-açık tarih aralığı: `start <= order_date < end`."""

    start: date
    end: date

    @property
    def start_at(self) -> datetime:
        """Aralığın başlangıcı (gün başı)."""
        return datetime.combine(self.start, time.min)

    @property
    def end_at(self) -> datetime:
        """Aralığın bitişi (hariç)."""
        return datetime.combine(self.end, time.min)


def default_period(today: date, *, days: int = 30) -> Period:
    """Varsayılan dönem: bugün dahil son `days` gün."""
    return Period(start=today - timedelta(days=days - 1), end=today + timedelta(days=1))


@dataclass
class Kpis:
    """Dashboard üst şeridi (spec §10.1)."""

    revenue_gross: Decimal = ZERO
    revenue_net_vat: Decimal = ZERO
    profit: Decimal = ZERO
    margin_pct: Decimal = ZERO
    return_rate_pct: Decimal = ZERO
    order_count: int = 0
    line_count: int = 0
    # "Tahmini vs kesinleşmiş" ayrımı (tasarım brief'i, kalıp 2).
    final_profit: Decimal = ZERO
    estimated_profit: Decimal = ZERO
    final_line_count: int = 0


@dataclass
class DailyPoint:
    """Günlük kâr grafiğinin bir noktası."""

    day: date
    revenue_gross: Decimal
    profit: Decimal


@dataclass
class StoreBreakdown:
    """Mağaza (kanal) kırılımı."""

    store_id: uuid.UUID
    store_name: str
    revenue_gross: Decimal
    profit: Decimal
    margin_pct: Decimal


@dataclass
class Dashboard:
    """Dashboard yanıtı."""

    period: Period
    kpis: Kpis
    daily: list[DailyPoint] = field(default_factory=list)
    stores: list[StoreBreakdown] = field(default_factory=list)


@dataclass
class SkuMargin:
    """SKU marj listesi satırı (spec §10.2)."""

    product_id: uuid.UUID
    sku: str
    name: str
    category: str | None
    qty_sold: int
    revenue_gross: Decimal
    cost_cogs: Decimal
    profit: Decimal
    margin_pct: Decimal
    is_final: bool


@dataclass
class OrderLineDetail:
    """Sipariş detayındaki bir satır + şelale adımları (spec §10.3)."""

    order_line_id: uuid.UUID
    sku: str | None
    name: str | None
    qty: int
    line_gross: Decimal
    vat_rate: Decimal
    profit: Decimal
    margin_pct: Decimal
    is_final: bool
    commission_source: CommissionSource | None
    waterfall: list[Step]


@dataclass
class OrderDetail:
    """Sipariş detayı yanıtı."""

    order_id: uuid.UUID
    external_order_id: str
    order_date: datetime
    status: OrderStatus
    store_name: str
    gross_total: Decimal
    profit: Decimal
    margin_pct: Decimal
    is_final: bool
    lines: list[OrderLineDetail]
    waterfall: list[Step]


@dataclass
class OrderRow:
    """Sipariş listesi satırı — detay ekranına giriş kapısı."""

    order_id: uuid.UUID
    external_order_id: str
    order_date: datetime
    status: OrderStatus
    store_name: str
    gross_total: Decimal
    profit: Decimal
    margin_pct: Decimal
    is_final: bool


def _margin(profit: Decimal, revenue: Decimal) -> Decimal:
    """Marj yüzdesi; gelir yoksa 0 (bölme hatası yerine dürüst sıfır)."""
    if not revenue:
        return ZERO
    return quantize_money(profit / revenue * Decimal(100))


def _scoped[SelectT: Select[Any]](statement: SelectT, period: Period) -> SelectT:
    """Ortak kısıt: dönem + iptal dışı siparişler."""
    return statement.where(
        Order.order_date >= period.start_at,
        Order.order_date < period.end_at,
        Order.status.notin_(EXCLUDED_STATUSES),
    )


def _kpis(session: Session, period: Period) -> Kpis:
    row = session.execute(
        _scoped(
            select(
                func.coalesce(func.sum(LineProfit.revenue_gross), 0),
                func.coalesce(func.sum(LineProfit.revenue_net_vat), 0),
                func.coalesce(func.sum(LineProfit.profit), 0),
                func.count(LineProfit.id),
                func.count(func.distinct(Order.id)),
                func.coalesce(func.sum(LineProfit.profit).filter(LineProfit.is_final.is_(True)), 0),
                func.coalesce(
                    func.sum(LineProfit.profit).filter(LineProfit.is_final.is_(False)), 0
                ),
                func.count(LineProfit.id).filter(LineProfit.is_final.is_(True)),
            )
            .select_from(LineProfit)
            .join(OrderLine, OrderLine.id == LineProfit.order_line_id)
            .join(Order, Order.id == OrderLine.order_id),
            period,
        )
    ).one()

    refunded = (
        session.scalar(
            _scoped(
                select(func.coalesce(func.sum(Return.refund_amount), 0))
                .select_from(Return)
                .join(OrderLine, OrderLine.id == Return.order_line_id)
                .join(Order, Order.id == OrderLine.order_id),
                period,
            )
        )
        or ZERO
    )

    revenue_gross = Decimal(row[0])
    profit = Decimal(row[2])
    # İade oranı: geri dönen tutarın toplam talebe (kalan ciro + iade) oranı.
    demand = revenue_gross + Decimal(refunded)
    return Kpis(
        revenue_gross=quantize_money(revenue_gross),
        revenue_net_vat=quantize_money(Decimal(row[1])),
        profit=quantize_money(profit),
        margin_pct=_margin(profit, revenue_gross),
        return_rate_pct=_margin(Decimal(refunded), demand),
        line_count=int(row[3]),
        order_count=int(row[4]),
        final_profit=quantize_money(Decimal(row[5])),
        estimated_profit=quantize_money(Decimal(row[6])),
        final_line_count=int(row[7]),
    )


def _daily(session: Session, period: Period) -> list[DailyPoint]:
    day = func.date(Order.order_date).label("day")
    rows = session.execute(
        _scoped(
            select(
                day,
                func.coalesce(func.sum(LineProfit.revenue_gross), 0),
                func.coalesce(func.sum(LineProfit.profit), 0),
            )
            .select_from(LineProfit)
            .join(OrderLine, OrderLine.id == LineProfit.order_line_id)
            .join(Order, Order.id == OrderLine.order_id),
            period,
        )
        .group_by(day)
        .order_by(day)
    ).all()
    return [
        DailyPoint(
            day=row[0],
            revenue_gross=quantize_money(Decimal(row[1])),
            profit=quantize_money(Decimal(row[2])),
        )
        for row in rows
    ]


def _stores(session: Session, period: Period) -> list[StoreBreakdown]:
    rows = session.execute(
        _scoped(
            select(
                Store.id,
                Store.name,
                func.coalesce(func.sum(LineProfit.revenue_gross), 0),
                func.coalesce(func.sum(LineProfit.profit), 0),
            )
            .select_from(LineProfit)
            .join(OrderLine, OrderLine.id == LineProfit.order_line_id)
            .join(Order, Order.id == OrderLine.order_id)
            .join(Store, Store.id == Order.store_id),
            period,
        )
        .group_by(Store.id, Store.name)
        .order_by(Store.name)
    ).all()
    return [
        StoreBreakdown(
            store_id=row[0],
            store_name=row[1],
            revenue_gross=quantize_money(Decimal(row[2])),
            profit=quantize_money(Decimal(row[3])),
            margin_pct=_margin(Decimal(row[3]), Decimal(row[2])),
        )
        for row in rows
    ]


def dashboard(session: Session, period: Period) -> Dashboard:
    """Dönem KPI'ları, günlük seri ve mağaza kırılımı (spec §10.1)."""
    return Dashboard(
        period=period,
        kpis=_kpis(session, period),
        daily=_daily(session, period),
        stores=_stores(session, period),
    )


def sku_margins(
    session: Session,
    period: Period,
    *,
    category: str | None = None,
    only_negative: bool = False,
    limit: int = 200,
) -> list[SkuMargin]:
    """SKU bazlı marj listesi — negatif marjlar ekranda kırmızı (spec §10.2)."""
    statement = (
        _scoped(
            select(
                Product.id,
                Product.sku,
                Product.name,
                Product.category,
                func.coalesce(func.sum(OrderLine.qty), 0),
                func.coalesce(func.sum(LineProfit.revenue_gross), 0),
                func.coalesce(func.sum(LineProfit.cost_cogs), 0),
                func.coalesce(func.sum(LineProfit.profit), 0),
                func.bool_and(LineProfit.is_final),
            )
            .select_from(LineProfit)
            .join(OrderLine, OrderLine.id == LineProfit.order_line_id)
            .join(Order, Order.id == OrderLine.order_id)
            .join(Product, Product.id == OrderLine.product_id),
            period,
        )
        .group_by(Product.id, Product.sku, Product.name, Product.category)
        .order_by(func.sum(LineProfit.profit))
        .limit(limit)
    )
    if category:
        statement = statement.where(Product.category == category)

    rows = session.execute(statement).all()
    result = [
        SkuMargin(
            product_id=row[0],
            sku=row[1],
            name=row[2],
            category=row[3],
            qty_sold=int(row[4]),
            revenue_gross=quantize_money(Decimal(row[5])),
            cost_cogs=quantize_money(Decimal(row[6])),
            profit=quantize_money(Decimal(row[7])),
            margin_pct=_margin(Decimal(row[7]), Decimal(row[5])),
            is_final=bool(row[8]),
        )
        for row in rows
    ]
    if only_negative:
        result = [item for item in result if item.profit < ZERO]
    return result


def order_rows(
    session: Session,
    period: Period,
    *,
    only_negative: bool = False,
    limit: int = 200,
) -> list[OrderRow]:
    """Dönemdeki siparişler + kârları (detay ekranına giriş)."""
    rows = session.execute(
        _scoped(
            select(
                Order.id,
                Order.external_order_id,
                Order.order_date,
                Order.status,
                Store.name,
                Order.gross_total,
                func.coalesce(func.sum(LineProfit.profit), 0),
                func.coalesce(func.sum(LineProfit.revenue_gross), 0),
                func.coalesce(func.bool_and(LineProfit.is_final), False),
            )
            .select_from(Order)
            .join(Store, Store.id == Order.store_id)
            .join(OrderLine, OrderLine.order_id == Order.id)
            .outerjoin(LineProfit, LineProfit.order_line_id == OrderLine.id),
            period,
        )
        .group_by(
            Order.id,
            Order.external_order_id,
            Order.order_date,
            Order.status,
            Store.name,
            Order.gross_total,
        )
        .order_by(Order.order_date.desc())
        .limit(limit)
    ).all()

    result = [
        OrderRow(
            order_id=row[0],
            external_order_id=row[1],
            order_date=row[2],
            status=row[3],
            store_name=row[4],
            gross_total=quantize_money(Decimal(row[5])),
            profit=quantize_money(Decimal(row[6])),
            margin_pct=_margin(Decimal(row[6]), Decimal(row[7])),
            is_final=bool(row[8]),
        )
        for row in rows
    ]
    if only_negative:
        result = [item for item in result if item.profit < ZERO]
    return result


def _waterfall_of(record: LineProfit) -> list[Step]:
    """`line_profit` satırından şelale adımları (motorun `waterfall` sırasıyla aynı)."""
    return [
        Step("satis", record.revenue_gross),
        Step("kampanya_destegi", record.revenue_campaign_support),
        Step("komisyon", -record.cost_commission),
        Step("kargo", -record.cost_cargo),
        Step("hizmet_bedeli", -record.cost_service_fee),
        Step("iade", -record.cost_return),
        Step("ceza", -record.cost_penalty),
        Step("reklam", -record.cost_ad_alloc),
        Step("kdv", -record.vat_net),
        Step("maliyet", -record.cost_cogs),
        Step("kar", record.profit),
    ]


def order_detail(session: Session, order_id: uuid.UUID) -> OrderDetail | None:
    """Sipariş detayı: satır bazlı şelale dökümü (spec §10.3, tasarım brief'i kalıp 4).

    Marka guard'ı yüzünden başka markanın siparişi burada `None` döner — API 404 verir.

    **`session.get()` KULLANILMAZ:** birincil anahtar araması identity map'ten
    dönebilir ve o yol guard'a hiç uğramaz — başka markanın siparişi sızardı.
    Marka verisi her zaman `select()` ile okunur (negatif testi vardır).
    """
    order = session.scalar(select(Order).where(Order.id == order_id))
    if order is None:
        return None
    store = session.scalar(select(Store).where(Store.id == order.store_id))

    rows = session.execute(
        select(OrderLine, LineProfit, Product)
        .outerjoin(LineProfit, LineProfit.order_line_id == OrderLine.id)
        .outerjoin(Product, Product.id == OrderLine.product_id)
        .where(OrderLine.order_id == order.id)
        .order_by(OrderLine.external_line_id)
    ).all()

    lines: list[OrderLineDetail] = []
    totals: dict[str, Decimal] = {}
    order_profit = ZERO
    order_revenue = ZERO
    is_final = bool(rows)

    for order_line, line_profit, product in rows:
        steps = _waterfall_of(line_profit) if line_profit is not None else []
        for step in steps:
            totals[step.key] = totals.get(step.key, ZERO) + step.amount
        if line_profit is not None:
            order_profit += line_profit.profit
            order_revenue += line_profit.revenue_gross
            is_final = is_final and line_profit.is_final
        else:
            is_final = False

        lines.append(
            OrderLineDetail(
                order_line_id=order_line.id,
                sku=product.sku if product else None,
                name=product.name if product else None,
                qty=order_line.qty,
                line_gross=order_line.line_gross,
                vat_rate=order_line.vat_rate,
                profit=line_profit.profit if line_profit else ZERO,
                margin_pct=line_profit.margin_pct if line_profit else ZERO,
                is_final=bool(line_profit and line_profit.is_final),
                commission_source=line_profit.commission_source if line_profit else None,
                waterfall=steps,
            )
        )

    return OrderDetail(
        order_id=order.id,
        external_order_id=order.external_order_id,
        order_date=order.order_date,
        status=order.status,
        store_name=store.name if store else "",
        gross_total=order.gross_total,
        profit=quantize_money(order_profit),
        margin_pct=_margin(order_profit, order_revenue),
        is_final=is_final,
        lines=lines,
        waterfall=[Step(key, quantize_money(value)) for key, value in totals.items()],
    )
