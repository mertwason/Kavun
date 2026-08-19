"""Holding görünümü — markalar arası, salt okunur (spec §3A.3)."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from app.api.deps import HoldingContext, get_holding_context
from app.models.catalog import Product
from app.models.identity import Brand
from app.models.results import Alert
from app.models.transactions import Order
from app.schemas.workspace import (
    BrandTotals,
    ConsolidatedBrandOut,
    ConsolidatedOut,
    HoldingSummary,
)
from app.services import holding

router = APIRouter(prefix="/holding", tags=["holding"])


@router.get("/summary", response_model=HoldingSummary, summary="Marka karşılaştırmalı özet")
def summary(context: HoldingContext = Depends(get_holding_context)) -> HoldingSummary:
    """Markaların yan yana sayımları. Brand-scope guard'ı yalnızca burada bypass edilir."""
    session = context.session
    tenant_id = context.tenant.id

    brands = session.scalars(
        select(Brand).where(Brand.tenant_id == tenant_id).order_by(Brand.slug)
    ).all()

    def count(
        model: type[Product] | type[Order] | type[Alert], brand_id: object, **filters: object
    ) -> int:
        statement = select(func.count()).select_from(model).where(model.brand_id == brand_id)
        if filters.get("open_only"):
            statement = statement.where(Alert.acknowledged_at.is_(None))
        return session.scalar(statement) or 0

    return HoldingSummary(
        tenant=context.tenant.slug,
        brands=[
            BrandTotals(
                brand=brand.slug,
                name=brand.name,
                product_count=count(Product, brand.id),
                order_count=count(Order, brand.id),
                open_alert_count=count(Alert, brand.id, open_only=True),
            )
            for brand in brands
        ],
    )


@router.get(
    "/consolidated",
    response_model=ConsolidatedOut,
    summary="Konsolide P&L, stok değeri, fire ve kur maruziyeti",
)
def consolidated(
    since: date | None = None,
    until: date | None = None,
    context: HoldingContext = Depends(get_holding_context),
) -> ConsolidatedOut:
    """Markalar arası konsolide rapor (spec §3A.3). Salt okunur; işlem yapılamaz."""
    report = holding.consolidated(context.session, context.tenant, since=since, until=until)
    return ConsolidatedOut(
        tenant=report.tenant,
        since=report.since,
        until=report.until,
        brands=[ConsolidatedBrandOut.model_validate(line) for line in report.brands],
        total_revenue=report.total_revenue,
        total_profit=report.total_profit,
        total_stock_value=report.total_stock_value,
        total_damage_cost=report.total_damage_cost,
        total_fx_diff=report.total_fx_diff,
    )
