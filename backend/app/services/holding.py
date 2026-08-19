"""Holding görünümü: markalar arası konsolide rapor (spec §3A.3).

Salt okunur ve **markalar üstüdür**: birleşik P&L, toplam stok değeri, kur maruziyeti,
fire gideri. Marka içinde çalışan hiçbir ekran bu sayıları göremez; holding görünümü
brand-scope guard'ını bilinçli olarak bypass eden tek yerdir (erişim audit'e yazılır,
`app/api/deps.py`).

Hesap yapılmaz, toplanır: her sayı marka içindeki motorun ürettiği kayıtlardan gelir
(`line_profit`, `sku_cost_state`, `inventory_ledger`, `supplier_payments`). Böylece
holding görünümü ile marka görünümü asla çelişmez.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.catalog import Product
from app.models.enums import InventoryMovement
from app.models.identity import Brand, Tenant
from app.models.inventory import ImportFile, InventoryLedger, SkuCostState, SupplierPayment
from app.models.results import Alert, LineProfit
from app.models.transactions import Order, OrderLine
from app.services.imports import file_goods_amount

ZERO = Decimal("0")
DEFAULT_WINDOW_DAYS = 30


@dataclass(frozen=True)
class BrandLine:
    """Bir markanın konsolide satırı."""

    brand: str
    name: str
    product_count: int
    order_count: int
    open_alert_count: int

    revenue: Decimal
    profit: Decimal
    margin_pct: Decimal
    stock_value: Decimal
    damage_cost: Decimal
    """Fire gideri — dönem içindeki `damage` hareketlerinin maliyeti (spec §12C.10)."""

    fx_diff: Decimal
    """Gerçekleşen kur farkı (P&L yönlü: negatif = gider) — spec §12C.8."""

    open_fx_amount: Decimal
    """Açık döviz pozisyonu (orijinal para biriminde toplam)."""


@dataclass(frozen=True)
class Consolidated:
    """Holding özeti: markalar + toplam satırı."""

    tenant: str
    since: date
    until: date
    brands: list[BrandLine]

    @property
    def total_revenue(self) -> Decimal:
        """Markaların ciro toplamı."""
        return sum((line.revenue for line in self.brands), ZERO)

    @property
    def total_profit(self) -> Decimal:
        """Markaların net kâr toplamı."""
        return sum((line.profit for line in self.brands), ZERO)

    @property
    def total_stock_value(self) -> Decimal:
        """Toplam stok değeri."""
        return sum((line.stock_value for line in self.brands), ZERO)

    @property
    def total_damage_cost(self) -> Decimal:
        """Toplam fire gideri."""
        return sum((line.damage_cost for line in self.brands), ZERO)

    @property
    def total_fx_diff(self) -> Decimal:
        """Toplam gerçekleşen kur farkı."""
        return sum((line.fx_diff for line in self.brands), ZERO)


def _window(since: date | None, until: date | None) -> tuple[datetime, datetime]:
    end = until or date.today()
    start = since or (end - timedelta(days=DEFAULT_WINDOW_DAYS))
    return (
        datetime.combine(start, datetime.min.time()),
        datetime.combine(end + timedelta(days=1), datetime.min.time()),
    )


def _profit_totals(
    session: Session, brand_id: uuid.UUID, start: datetime, end: datetime
) -> tuple[Decimal, Decimal]:
    """Dönem cirosu ve net kârı — motorun yazdığı `line_profit` satırlarından."""
    row = session.execute(
        select(
            func.coalesce(func.sum(LineProfit.revenue_gross), 0),
            func.coalesce(func.sum(LineProfit.profit), 0),
        )
        .join(OrderLine, OrderLine.id == LineProfit.order_line_id)
        .join(Order, Order.id == OrderLine.order_id)
        .where(
            LineProfit.brand_id == brand_id,
            Order.order_date >= start,
            Order.order_date < end,
        )
    ).one()
    return Decimal(row[0]), Decimal(row[1])


def _stock_value(session: Session, brand_id: uuid.UUID) -> Decimal:
    """Eldeki stokun değeri: adet × ortalama maliyet."""
    rows = session.execute(
        select(SkuCostState.on_hand_qty, SkuCostState.avg_cost)
        .join(Product, Product.id == SkuCostState.product_id)
        .where(Product.brand_id == brand_id)
    ).all()
    total = sum((qty * cost for qty, cost in rows if qty > 0), ZERO)
    return Decimal(total).quantize(Decimal("0.0001"))


def _damage_cost(session: Session, brand_id: uuid.UUID, start: datetime, end: datetime) -> Decimal:
    """Fire gideri: hasar hareketlerinin o günkü ortalama maliyetle tutarı."""
    rows = session.execute(
        select(InventoryLedger.qty_delta, InventoryLedger.unit_cost_at_movement).where(
            InventoryLedger.brand_id == brand_id,
            InventoryLedger.movement == InventoryMovement.DAMAGE,
            InventoryLedger.moved_at >= start,
            InventoryLedger.moved_at < end,
        )
    ).all()
    total = sum((abs(qty) * (cost or ZERO) for qty, cost in rows), ZERO)
    return Decimal(total).quantize(Decimal("0.0001"))


def _fx(session: Session, brand_id: uuid.UUID) -> tuple[Decimal, Decimal]:
    """Gerçekleşen kur farkı ve açık döviz pozisyonu (spec §12C.8)."""
    payments = session.scalars(
        select(SupplierPayment).where(SupplierPayment.brand_id == brand_id)
    ).all()
    realized = sum((payment.fx_diff_try or ZERO for payment in payments), ZERO)

    files = session.scalars(select(ImportFile).where(ImportFile.brand_id == brand_id)).all()
    invoiced = ZERO
    for item in files:
        if item.currency.upper() == "TRY" or item.fx_rate_beyanname is None:
            continue
        # Dosyanın dövizli tutarı: mal faturası satırlarının orijinal para birimi toplamı.
        invoiced += file_goods_amount(session, import_file=item)
    paid = sum(
        (payment.amount_original for payment in payments if payment.currency.upper() != "TRY"),
        ZERO,
    )
    return Decimal(realized).quantize(Decimal("0.01")), Decimal(invoiced - paid).quantize(
        Decimal("0.01")
    )


def consolidated(
    session: Session,
    tenant: Tenant,
    *,
    since: date | None = None,
    until: date | None = None,
) -> Consolidated:
    """Markalar arası konsolide özet (spec §3A.3).

    Çağıran holding bağlamını (guard bypass) açmış olmalıdır; bu fonksiyon kendi başına
    bypass yapmaz.
    """
    start, end = _window(since, until)
    brands = session.scalars(
        select(Brand).where(Brand.tenant_id == tenant.id).order_by(Brand.slug)
    ).all()

    lines: list[BrandLine] = []
    for brand in brands:
        revenue, profit = _profit_totals(session, brand.id, start, end)
        realized_fx, open_fx = _fx(session, brand.id)
        lines.append(
            BrandLine(
                brand=brand.slug,
                name=brand.name,
                product_count=session.scalar(
                    select(func.count()).select_from(Product).where(Product.brand_id == brand.id)
                )
                or 0,
                order_count=session.scalar(
                    select(func.count())
                    .select_from(Order)
                    .where(
                        Order.brand_id == brand.id,
                        Order.order_date >= start,
                        Order.order_date < end,
                    )
                )
                or 0,
                open_alert_count=session.scalar(
                    select(func.count())
                    .select_from(Alert)
                    .where(Alert.brand_id == brand.id, Alert.acknowledged_at.is_(None))
                )
                or 0,
                revenue=revenue,
                profit=profit,
                margin_pct=(
                    (profit / revenue * Decimal("100")).quantize(Decimal("0.01"))
                    if revenue
                    else ZERO
                ),
                stock_value=_stock_value(session, brand.id),
                damage_cost=_damage_cost(session, brand.id, start, end),
                fx_diff=realized_fx,
                open_fx_amount=open_fx,
            )
        )

    return Consolidated(
        tenant=tenant.slug,
        since=start.date(),
        until=(end - timedelta(days=1)).date(),
        brands=lines,
    )
