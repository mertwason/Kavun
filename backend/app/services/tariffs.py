"""Komisyon snapshot, değişiklik tespiti ve etki analizi (spec §12B.3, §12B.4).

Komisyon statik parametre değil, versiyonlu tarife verisidir. Bu modül:
1. günlük snapshot alır,
2. dünkü geçerli oranla bugünküyü karşılaştırıp `commission_changes` + alert üretir,
3. değişimin **parasal etkisini** hesaplar (son 30 günün satış hızıyla),
4. "komisyon %1,5 artarsa katalogda ne olur" sorusunu tek çağrıda cevaplar.

## Etki formülü (motorla birebir tutarlı)

Komisyon kâra `−P·k` olarak girer, KDV'si `+P·k·α` olarak indirilir (α = s/(1+s)).
Dolayısıyla oran `k₀ → k₁` değiştiğinde bir satırın kâr farkı:

    Δkâr = −P · (k₁ − k₀) · (1 − α)

Bu kapalı ifade motorun kendisiyle test edilerek doğrulanır (aynı satır iki oranla
hesaplanıp fark karşılaştırılır) — ikinci bir "yaklaşık" formül yaşamaz.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import textfmt
from app.core.logging import get_logger
from app.engine.pricing import PriceInputs, price_for_margin
from app.engine.profit import DEFAULT_SERVICE_VAT_PERCENT, LineInput, compute_line_profit
from app.engine.vat import quantize_money
from app.models.catalog import CommissionChange, CommissionRate, Product, SkuCost
from app.models.enums import AlertSeverity, CommissionScope, CommissionSource, OrderStatus
from app.models.identity import Store
from app.models.results import Alert, LineProfit
from app.models.transactions import Order, OrderLine

log = get_logger("services.tariffs")

ZERO = Decimal("0")
ONE = Decimal("1")
HUNDRED = Decimal("100")

IMPACT_WINDOW_DAYS = 30
"""Spec §12B.3: etki hesabı son 30 günün satış hızıyla yapılır."""

ALERT_TYPE = "komisyon_degisikligi"


def _service_vat_factor() -> Decimal:
    """`1 − α`: komisyonun KDV'si indirilebildiği için kâra net etkisi bu oranda."""
    rate = DEFAULT_SERVICE_VAT_PERCENT / HUNDRED
    return ONE - rate / (ONE + rate)


@dataclass
class ImpactRow:
    """Bir SKU için oran değişiminin etkisi."""

    product_id: uuid.UUID
    sku: str
    name: str
    category: str | None
    qty_sold: int
    revenue_gross: Decimal
    old_rate: Decimal
    new_rate: Decimal
    profit_impact: Decimal
    """Dönemdeki toplam kâr farkı (negatif = kâr azalıyor)."""

    current_profit: Decimal
    projected_profit: Decimal
    turns_negative: bool


@dataclass
class ImpactSummary:
    """Etki analizi özeti — alert mesajının ve UI kartının kaynağı (spec §12B.3)."""

    window_days: int
    monthly_profit_impact: Decimal = ZERO
    affected_sku_count: int = 0
    negative_margin_sku_count: int = 0
    rows: list[ImpactRow] = field(default_factory=list)

    @property
    def negative_skus(self) -> list[str]:
        """Negatife düşen SKU'lar (alert mesajında listelenir)."""
        return [row.sku for row in self.rows if row.turns_negative]


def _window(on_date: date) -> tuple[datetime, datetime]:
    end = datetime.combine(on_date + timedelta(days=1), time.min)
    start = datetime.combine(on_date - timedelta(days=IMPACT_WINDOW_DAYS - 1), time.min)
    return start, end


def _sales_by_product(
    session: Session, *, store_id: uuid.UUID, on_date: date
) -> dict[uuid.UUID, tuple[int, Decimal, Decimal]]:
    """Son 30 günde ürün bazında `(adet, brüt ciro, kâr)` — motorun yazdığı sonuçlardan."""
    start, end = _window(on_date)
    rows = session.execute(
        select(
            OrderLine.product_id,
            func.coalesce(func.sum(OrderLine.qty), 0),
            func.coalesce(func.sum(LineProfit.revenue_gross), 0),
            func.coalesce(func.sum(LineProfit.profit), 0),
        )
        .select_from(LineProfit)
        .join(OrderLine, OrderLine.id == LineProfit.order_line_id)
        .join(Order, Order.id == OrderLine.order_id)
        .where(
            Order.store_id == store_id,
            Order.order_date >= start,
            Order.order_date < end,
            Order.status.notin_((OrderStatus.CANCELLED,)),
            OrderLine.product_id.is_not(None),
        )
        .group_by(OrderLine.product_id)
    ).all()
    return {
        row[0]: (int(row[1]), Decimal(row[2]), Decimal(row[3]))
        for row in rows
        if row[0] is not None
    }


def profit_delta(revenue_gross: Decimal, old_rate: Decimal, new_rate: Decimal) -> Decimal:
    """Oran değişiminin kâra etkisi: `−P·(k₁−k₀)·(1−α)` (bkz. modül docstring'i)."""
    return quantize_money(-revenue_gross * (new_rate - old_rate) * _service_vat_factor())


def estimate_impact(
    session: Session,
    *,
    store: Store,
    on_date: date,
    changes: list[tuple[Product, Decimal, Decimal]],
) -> ImpactSummary:
    """Değişen oranların son 30 günlük satış hızıyla parasal etkisi (spec §12B.3)."""
    sales = _sales_by_product(session, store_id=store.id, on_date=on_date)
    summary = ImpactSummary(window_days=IMPACT_WINDOW_DAYS)

    for product, old_rate, new_rate in changes:
        qty, revenue, profit = sales.get(product.id, (0, ZERO, ZERO))
        delta = profit_delta(revenue, old_rate, new_rate)
        projected = quantize_money(profit + delta)
        row = ImpactRow(
            product_id=product.id,
            sku=product.sku,
            name=product.name,
            category=product.category,
            qty_sold=qty,
            revenue_gross=quantize_money(revenue),
            old_rate=old_rate,
            new_rate=new_rate,
            profit_impact=delta,
            current_profit=quantize_money(profit),
            projected_profit=projected,
            turns_negative=profit >= ZERO > projected,
        )
        summary.rows.append(row)
        summary.monthly_profit_impact += delta
        if qty:
            summary.affected_sku_count += 1
        if projected < ZERO:
            summary.negative_margin_sku_count += 1

    summary.monthly_profit_impact = quantize_money(summary.monthly_profit_impact)
    return summary


def _products_for(session: Session, rate: CommissionRate) -> list[Product]:
    """Tarifenin kapsadığı ürünler."""
    if rate.scope is CommissionScope.PRODUCT and rate.product_id:
        product = session.scalar(select(Product).where(Product.id == rate.product_id))
        return [product] if product else []
    if rate.category_code:
        return list(
            session.scalars(select(Product).where(Product.category == rate.category_code)).all()
        )
    return []


def _effective_rate(
    session: Session, *, store_id: uuid.UUID, category: str, on_date: date
) -> CommissionRate | None:
    """Verilen tarihte kategori için geçerli tarife (en güncel `valid_from`)."""
    candidates = list(
        session.scalars(
            select(CommissionRate).where(
                CommissionRate.store_id == store_id,
                CommissionRate.scope == CommissionScope.CATEGORY,
                CommissionRate.category_code == category,
                CommissionRate.valid_from <= on_date,
                (CommissionRate.valid_to.is_(None)) | (CommissionRate.valid_to > on_date),
            )
        ).all()
    )
    if not candidates:
        return None
    return max(candidates, key=lambda item: (item.valid_from, item.created_at))


@dataclass
class DiffSummary:
    """Snapshot karşılaştırmasının sonucu."""

    detected: int = 0
    alerts: int = 0
    impact: ImpactSummary | None = None


def alert_message(
    category: str, old_rate: Decimal, new_rate: Decimal, impact: ImpactSummary
) -> str:
    """Spec §12B.3'teki alert metni — rakamlar hesaplanmış hâliyle."""
    negative = impact.negative_skus
    message = (
        f"{category} kategorisinde komisyon "
        f"{textfmt.percent(old_rate * HUNDRED)} → {textfmt.percent(new_rate * HUNDRED)}. "
        f"Mevcut satış hızıyla aylık kâr etkisi: "
        f"{textfmt.money(impact.monthly_profit_impact)}."
    )
    if negative:
        message += f" Negatif marja düşen SKU: {len(negative)} ({', '.join(negative[:5])})"
    return message


def detect_changes(session: Session, *, store: Store, on_date: date) -> DiffSummary:
    """Dünkü geçerli oranla bugünküyü karşılaştırır; değişim varsa kayıt + alert üretir.

    Spec §12B.3: "dünkü geçerli oran ≠ bugünkü → `commission_changes` kaydı + alert".
    """
    summary = DiffSummary()
    yesterday = on_date - timedelta(days=1)
    categories = {
        row
        for row in session.scalars(
            select(CommissionRate.category_code).where(
                CommissionRate.store_id == store.id,
                CommissionRate.scope == CommissionScope.CATEGORY,
                CommissionRate.category_code.is_not(None),
            )
        ).all()
        if row
    }

    changed: list[tuple[Product, Decimal, Decimal]] = []
    pairs: list[tuple[str, Decimal, Decimal]] = []
    for category in sorted(categories):
        today_rate = _effective_rate(session, store_id=store.id, category=category, on_date=on_date)
        previous = _effective_rate(session, store_id=store.id, category=category, on_date=yesterday)
        if today_rate is None or previous is None or today_rate.rate == previous.rate:
            continue
        pairs.append((category, previous.rate, today_rate.rate))
        changed.extend(
            (product, previous.rate, today_rate.rate)
            for product in _products_for(session, today_rate)
        )

    if not pairs:
        return summary

    impact = estimate_impact(session, store=store, on_date=on_date, changes=changed)
    summary.impact = impact
    now = datetime.now(UTC)

    for category, old_rate, new_rate in pairs:
        category_rows = [row for row in impact.rows if row.category == category]
        category_impact = ImpactSummary(
            window_days=impact.window_days,
            monthly_profit_impact=quantize_money(
                sum((row.profit_impact for row in category_rows), ZERO)
            ),
            affected_sku_count=sum(1 for row in category_rows if row.qty_sold),
            negative_margin_sku_count=sum(
                1 for row in category_rows if row.projected_profit < ZERO
            ),
            rows=category_rows,
        )
        alert = Alert(
            tenant_id=store.tenant_id,
            brand_id=store.brand_id,
            type=ALERT_TYPE,
            severity=(
                AlertSeverity.CRITICAL if category_impact.negative_skus else AlertSeverity.WARNING
            ),
            entity_ref=f"category:{category}",
            message=alert_message(category, old_rate, new_rate, category_impact),
            created_at=now,
        )
        session.add(alert)
        session.flush()
        session.add(
            CommissionChange(
                store_id=store.id,
                category_code=category,
                old_rate=old_rate,
                new_rate=new_rate,
                detected_at=now,
                monthly_profit_impact=category_impact.monthly_profit_impact,
                alert_id=alert.id,
            )
        )
        summary.detected += 1
        summary.alerts += 1

    session.flush()
    log.info(
        "tariffs.changes_detected",
        store_id=str(store.id),
        detected=summary.detected,
        monthly_profit_impact=str(impact.monthly_profit_impact),
    )
    return summary


# --- toplu tarife senaryosu (spec §12B.4) ------------------------------------


@dataclass
class TariffImpactRow:
    """`tariff-impact` çıktısının bir satırı."""

    product_id: uuid.UUID
    sku: str
    name: str
    category: str | None
    old_rate: Decimal
    new_rate: Decimal
    current_price: Decimal | None
    current_margin_pct: Decimal
    projected_margin_pct: Decimal
    required_price: Decimal | None
    """Hedef marjı korumak için gereken yeni fiyat (kapalı formülle çözülür)."""

    qty_sold: int
    revenue_gross: Decimal
    profit_impact: Decimal


@dataclass
class TariffImpactResult:
    """Toplu tarife senaryosunun sonucu."""

    scope: str
    target_margin_pct: Decimal | None
    monthly_profit_impact: Decimal
    rows: list[TariffImpactRow] = field(default_factory=list)


def _current_price(session: Session, product_id: uuid.UUID, store_id: uuid.UUID) -> Decimal | None:
    from app.models.catalog import SkuPrice

    row = session.scalar(
        select(SkuPrice)
        .where(SkuPrice.product_id == product_id, SkuPrice.store_id == store_id)
        .order_by(SkuPrice.effective_from.desc(), SkuPrice.created_at.desc())
        .limit(1)
    )
    return row.price if row else None


def _unit_cost(session: Session, product_id: uuid.UUID, on_date: date) -> Decimal | None:
    row = session.scalar(
        select(SkuCost)
        .where(SkuCost.product_id == product_id, SkuCost.effective_from <= on_date)
        .order_by(SkuCost.effective_from.desc(), SkuCost.created_at.desc())
        .limit(1)
    )
    return row.unit_cost if row else None


def _margin_at(
    *,
    price: Decimal,
    cost: Decimal,
    vat_percent: Decimal,
    rate: Decimal,
    cargo: Decimal,
    service_fee: Decimal,
) -> Decimal:
    """Verilen komisyon oranıyla marj — motorun kendisinden."""
    return compute_line_profit(
        LineInput(
            line_gross=price,
            qty=1,
            vat_percent=vat_percent,
            unit_cost_net=cost,
            commission_rate=rate,
            cargo_cost=cargo,
            service_fee=service_fee,
        )
    ).margin_pct


def tariff_impact(
    session: Session,
    *,
    store: Store,
    on_date: date,
    category: str | None = None,
    new_rate: Decimal | None = None,
    rate_delta: Decimal | None = None,
    target_margin_pct: Decimal | None = None,
    cargo_estimate: Decimal | None = None,
) -> TariffImpactResult:
    """ "Komisyon %X artarsa katalogda ne olur" — tek çağrıda cevap (spec §12B.4).

    `new_rate` mutlak oranı, `rate_delta` mevcut orana eklenecek farkı belirtir.
    `target_margin_pct` verilirse her SKU için o marjı KORUYAN yeni fiyat da çözülür.
    """
    if new_rate is None and rate_delta is None:
        raise ValueError("new_rate ya da rate_delta verilmeli")

    statement = select(Product).order_by(Product.sku)
    if category:
        statement = statement.where(Product.category == category)
    products = list(session.scalars(statement).all())

    sales = _sales_by_product(session, store_id=store.id, on_date=on_date)
    service_fee = store.service_fee_per_order or ZERO
    cargo = cargo_estimate or ZERO
    result = TariffImpactResult(
        scope=category or "all",
        target_margin_pct=target_margin_pct,
        monthly_profit_impact=ZERO,
    )

    for product in products:
        current = (
            _effective_rate(session, store_id=store.id, category=product.category, on_date=on_date)
            if product.category
            else None
        )
        old_rate = current.rate if current else ZERO
        updated = new_rate if new_rate is not None else old_rate + (rate_delta or ZERO)
        if updated < ZERO:
            updated = ZERO

        qty, revenue, _ = sales.get(product.id, (0, ZERO, ZERO))
        delta = profit_delta(revenue, old_rate, updated)
        price = _current_price(session, product.id, store.id)
        cost = _unit_cost(session, product.id, on_date)

        current_margin = ZERO
        projected_margin = ZERO
        required_price: Decimal | None = None
        if price is not None and cost is not None:
            current_margin = _margin_at(
                price=price,
                cost=cost,
                vat_percent=product.vat_rate,
                rate=old_rate,
                cargo=cargo,
                service_fee=service_fee,
            )
            projected_margin = _margin_at(
                price=price,
                cost=cost,
                vat_percent=product.vat_rate,
                rate=updated,
                cargo=cargo,
                service_fee=service_fee,
            )
            goal = target_margin_pct if target_margin_pct is not None else current_margin
            required_price = price_for_margin(
                goal,
                PriceInputs(
                    unit_cost_net=cost,
                    vat_percent=product.vat_rate,
                    commission_rate=updated,
                    cargo_cost=cargo,
                    service_fee=service_fee,
                ),
            )

        result.rows.append(
            TariffImpactRow(
                product_id=product.id,
                sku=product.sku,
                name=product.name,
                category=product.category,
                old_rate=old_rate,
                new_rate=updated,
                current_price=price,
                current_margin_pct=current_margin,
                projected_margin_pct=projected_margin,
                required_price=required_price,
                qty_sold=qty,
                revenue_gross=quantize_money(revenue),
                profit_impact=delta,
            )
        )
        result.monthly_profit_impact += delta

    result.monthly_profit_impact = quantize_money(result.monthly_profit_impact)
    return result


def settlement_conflict(
    session: Session,
    *,
    store: Store,
    product: Product,
    settlement_rate: Decimal,
    on_date: date,
) -> CommissionRate | None:
    """Hakedişteki gerçek oran tarifeden farklıysa `settlement_actual` kaydı yazar.

    Spec §12B.3: çelişki sessiz geçilmez. Mutabakat farkı kaydı Faz 2'de
    (`reconciliation_diffs`) bu fonksiyonun döndürdüğü kayda bağlanacak.
    """
    current = (
        _effective_rate(session, store_id=store.id, category=product.category, on_date=on_date)
        if product.category
        else None
    )
    if current is not None and current.rate == settlement_rate:
        return None

    record = CommissionRate(
        store_id=store.id,
        scope=CommissionScope.PRODUCT,
        product_id=product.id,
        rate=settlement_rate,
        source=CommissionSource.SETTLEMENT_ACTUAL,
        valid_from=on_date,
    )
    session.add(record)
    session.flush()
    log.warning(
        "tariffs.settlement_conflict",
        product_id=str(product.id),
        tariff_rate=str(current.rate if current else None),
        settlement_rate=str(settlement_rate),
    )
    return record
