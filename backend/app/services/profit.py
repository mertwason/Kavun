"""Kâr hesabının DB katmanı: girdileri topla → motoru çağır → sonucu yaz (spec §6).

Motor saf kalır (`app/engine/profit.py`); bu modül yalnızca veri toplar ve sonucu
`line_profit`'e yazar. Değişen her alan `profit_revisions`'a append-only loglanır
(spec §6.2) — geçmiş kayıt güncellenmez, düzeltme kaydı atılır (CLAUDE.md §1).

Paylaştırmalar (spec §6.1, §6.3.6):
- kargo: paketteki satırlara **desi ağırlıklı**
- hizmet bedeli: satırlara **tutar ağırlıklı**
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.context import system_scope
from app.core.logging import get_logger
from app.engine.allocation import allocate
from app.engine.profit import (
    LineInput,
    ProfitBreakdown,
    ReturnInput,
    compute_line_profit,
    profit_from_net_amounts,
)
from app.engine.vat import quantize_money
from app.models.catalog import Product, SkuCost, SkuLogistics
from app.models.enums import CostState
from app.models.identity import Store
from app.models.results import LineProfit, ProfitRevision
from app.models.transactions import Order, OrderLine, Return, Shipment
from app.services.commission import resolve_commission

log = get_logger("services.profit")

ZERO = Decimal("0")

# `line_profit` üzerinde revizyon takibi yapılan alanlar (spec §6.2).
TRACKED_FIELDS = (
    "revenue_gross",
    "revenue_net_vat",
    "cost_cogs",
    "cost_commission",
    "cost_cargo",
    "cost_service_fee",
    "cost_return",
    "cost_penalty",
    "revenue_campaign_support",
    "vat_net",
    "profit",
)


@dataclass
class RecomputeSummary:
    """Hesap turunun özeti."""

    orders: int = 0
    lines: int = 0
    created: int = 0
    updated: int = 0
    revisions: int = 0
    warnings: dict[str, int] = field(default_factory=dict)

    def warn(self, code: str) -> None:
        """Uyarı sayacı (ör. maliyet_yok)."""
        self.warnings[code] = self.warnings.get(code, 0) + 1

    def as_dict(self) -> dict[str, Any]:
        """Log/JSON dostu özet."""
        return {
            "orders": self.orders,
            "lines": self.lines,
            "created": self.created,
            "updated": self.updated,
            "revisions": self.revisions,
            "warnings": self.warnings,
        }


def effective_unit_cost(session: Session, product: Product, on_date: datetime) -> Decimal | None:
    """Sipariş tarihinde geçerli birim maliyet: `effective_from <= tarih` en güncel kayıt."""
    cost = session.scalar(
        select(SkuCost)
        .where(SkuCost.product_id == product.id, SkuCost.effective_from <= on_date.date())
        .order_by(SkuCost.effective_from.desc(), SkuCost.created_at.desc())
        .limit(1)
    )
    return cost.unit_cost if cost else None


def _line_desi(session: Session, line: OrderLine, on_date: datetime) -> Decimal:
    """Satırın desi ağırlığı (adet × birim desi); bilinmiyorsa 0."""
    if line.product_id is None:
        return ZERO
    logistics = session.scalar(
        select(SkuLogistics)
        .where(
            SkuLogistics.product_id == line.product_id,
            SkuLogistics.effective_from <= on_date.date(),
        )
        .order_by(SkuLogistics.effective_from.desc())
        .limit(1)
    )
    return (logistics.desi * line.qty) if logistics else ZERO


def _returns_for(session: Session, line: OrderLine) -> tuple[ReturnInput, ...]:
    """Satırın iadeleri."""
    rows = session.scalars(select(Return).where(Return.order_line_id == line.id)).all()
    return tuple(
        ReturnInput(
            qty=row.qty,
            refund_amount=row.refund_amount,
            return_cargo_cost=row.return_cargo_cost_actual or row.return_cargo_cost_estimated,
            restocked=row.restocked,
        )
        for row in rows
    )


def build_line_inputs(session: Session, order: Order) -> list[tuple[OrderLine, LineInput]]:
    """Siparişin satırları için motor girdilerini hazırlar (paylaştırmalar dahil)."""
    lines = list(
        session.scalars(
            select(OrderLine)
            .where(OrderLine.order_id == order.id)
            .order_by(OrderLine.external_line_id)
        ).all()
    )
    if not lines:
        return []

    store = session.get(Store, order.store_id)
    shipment = session.scalar(select(Shipment).where(Shipment.order_id == order.id))

    cargo_total = ZERO
    if shipment is not None:
        cargo_total = (
            shipment.cargo_cost_actual
            if shipment.cost_state is CostState.ACTUAL and shipment.cargo_cost_actual is not None
            else shipment.cargo_cost_estimated
        )
    service_total = (store.service_fee_per_order or ZERO) if store else ZERO

    desi_weights = [_line_desi(session, line, order.order_date) for line in lines]
    amount_weights = [line.line_gross for line in lines]
    cargo_parts = allocate(cargo_total, desi_weights)
    service_parts = allocate(service_total, amount_weights)

    prepared: list[tuple[OrderLine, LineInput]] = []
    for index, line in enumerate(lines):
        product = session.get(Product, line.product_id) if line.product_id else None
        unit_cost = (
            effective_unit_cost(session, product, order.order_date) if product is not None else None
        )
        rate_row, source = (
            resolve_commission(
                session,
                store_id=order.store_id,
                product=product,
                on_date=order.order_date.date(),
            )
            if product is not None
            else (None, None)
        )

        prepared.append(
            (
                line,
                LineInput(
                    line_gross=line.line_gross,
                    qty=line.qty,
                    vat_percent=line.vat_rate,
                    status=line.status,
                    unit_cost_net=unit_cost,
                    commission_rate=rate_row.rate if rate_row else line.commission_rate_used,
                    commission_source=source,
                    cargo_cost=cargo_parts[index],
                    service_fee=service_parts[index],
                    returns=_returns_for(session, line),
                    is_final=bool(shipment is not None and shipment.cost_state is CostState.ACTUAL),
                ),
            )
        )
    return prepared


def _persist(
    session: Session,
    order: Order,
    line: OrderLine,
    breakdown: ProfitBreakdown,
    summary: RecomputeSummary,
) -> LineProfit:
    """Sonucu `line_profit`'e yazar; değişiklikleri `profit_revisions`'a loglar."""
    now = datetime.now(UTC)
    existing = session.scalar(select(LineProfit).where(LineProfit.order_line_id == line.id))

    values = {
        "revenue_gross": breakdown.revenue_gross,
        "revenue_net_vat": breakdown.revenue_net_vat,
        "cost_cogs": breakdown.cost_cogs,
        "cost_commission": breakdown.cost_commission,
        "cost_cargo": breakdown.cost_cargo,
        "cost_service_fee": breakdown.cost_service_fee,
        "cost_return": breakdown.cost_return,
        "cost_ad_alloc": breakdown.cost_ad_alloc,
        "cost_penalty": breakdown.cost_penalty,
        "revenue_campaign_support": breakdown.revenue_campaign_support,
        "vat_net": breakdown.vat_net,
        "profit": breakdown.profit,
        "margin_pct": breakdown.margin_pct,
        "commission_source": breakdown.commission_source,
        "is_final": breakdown.is_final,
        "computed_at": now,
    }

    if existing is None:
        record = LineProfit(
            tenant_id=order.tenant_id,
            brand_id=order.brand_id,
            order_line_id=line.id,
            **values,
        )
        session.add(record)
        summary.created += 1
        return record

    for field_name in TRACKED_FIELDS:
        old_value = getattr(existing, field_name)
        new_value = values[field_name]
        if old_value != new_value:
            session.add(
                ProfitRevision(
                    tenant_id=order.tenant_id,
                    brand_id=order.brand_id,
                    order_line_id=line.id,
                    field=field_name,
                    old_value=old_value,
                    new_value=new_value,
                    reason="recompute",
                    revised_at=now,
                )
            )
            summary.revisions += 1

    for key, value in values.items():
        setattr(existing, key, value)
    summary.updated += 1
    return existing


def recompute_order(session: Session, order: Order, summary: RecomputeSummary) -> None:
    """Bir siparişin tüm satırlarının kârını hesaplar ve yazar."""
    for line, line_input in build_line_inputs(session, order):
        breakdown = compute_line_profit(line_input)

        # Motorun kendi kendini denetlemesi: brüt ve net yol aynı kârı vermeli.
        cross_check = profit_from_net_amounts(line_input, breakdown)
        if quantize_money(abs(cross_check - breakdown.profit)) > Decimal("0.0100"):
            log.error(
                "profit.cross_check_failed",
                order_line_id=str(line.id),
                gross_path=str(breakdown.profit),
                net_path=str(cross_check),
            )
            summary.warn("cross_check_failed")

        for code in breakdown.warnings:
            summary.warn(code)
        _persist(session, order, line, breakdown, summary)
        summary.lines += 1
    summary.orders += 1


def recompute_orders(
    session: Session,
    *,
    store_id: uuid.UUID | None = None,
    order_ids: list[uuid.UUID] | None = None,
    limit: int = 5000,
) -> RecomputeSummary:
    """Verilen kapsamdaki siparişlerin kârını yeniden hesaplar."""
    summary = RecomputeSummary()
    with system_scope():
        statement = select(Order).order_by(Order.order_date).limit(limit)
        if store_id is not None:
            statement = statement.where(Order.store_id == store_id)
        if order_ids is not None:
            statement = statement.where(Order.id.in_(order_ids))

        for order in session.scalars(statement).all():
            recompute_order(session, order, summary)
        session.commit()

    log.info("profit.recomputed", **summary.as_dict())
    return summary


def recompute_pending(session: Session, *, limit: int = 5000) -> RecomputeSummary:
    """Kâr kaydı olmayan satırların siparişlerini hesaplar (sync/normalize sonrası zincir)."""
    with system_scope():
        pending_order_ids = list(
            session.scalars(
                select(OrderLine.order_id)
                .outerjoin(LineProfit, LineProfit.order_line_id == OrderLine.id)
                .where(LineProfit.id.is_(None))
                .distinct()
                .limit(limit)
            ).all()
        )
    if not pending_order_ids:
        return RecomputeSummary()
    return recompute_orders(session, order_ids=pending_order_ids, limit=limit)
