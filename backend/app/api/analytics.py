"""Dashboard, SKU marj listesi ve sipariş detayı uçları (spec §10).

Hepsi marka workspace'i içinde çalışır: `get_workspace` bağımlılığı brand-scope
guard'ını kurar, başka markanın verisi sorgudan otomatik düşer.
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import Workspace, get_workspace
from app.schemas.analytics import (
    DashboardOut,
    OrderDetailOut,
    OrderRowOut,
    SkuMarginOut,
)
from app.services import analytics

router = APIRouter(prefix="/{brand_slug}", tags=["analytics"])

MAX_PERIOD_DAYS = 400


def _period(start: date | None, end: date | None) -> analytics.Period:
    """Sorgu parametrelerinden dönem; verilmezse son 30 gün."""
    if start is None or end is None:
        return analytics.default_period(date.today())
    if end <= start:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Bitiş tarihi başlangıçtan sonra olmalı",
        )
    if (end - start).days > MAX_PERIOD_DAYS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Dönem en fazla {MAX_PERIOD_DAYS} gün olabilir",
        )
    return analytics.Period(start=start, end=end)


@router.get("/dashboard", response_model=DashboardOut, summary="Dönem KPI'ları ve grafikler")
def get_dashboard(
    workspace: Workspace = Depends(get_workspace),
    start: date | None = Query(default=None, alias="from"),
    end: date | None = Query(default=None, alias="to"),
) -> analytics.Dashboard:
    """Ciro, net kâr, marj%, iade% + günlük seri + mağaza kırılımı (spec §10.1)."""
    return analytics.dashboard(workspace.session, _period(start, end))


@router.get("/sku-margins", response_model=list[SkuMarginOut], summary="SKU marj listesi")
def get_sku_margins(
    workspace: Workspace = Depends(get_workspace),
    start: date | None = Query(default=None, alias="from"),
    end: date | None = Query(default=None, alias="to"),
    category: str | None = None,
    only_negative: bool = False,
    limit: int = Query(default=200, le=1000),
) -> list[analytics.SkuMargin]:
    """En düşük kârdan başlayarak SKU marjları (spec §10.2)."""
    return analytics.sku_margins(
        workspace.session,
        _period(start, end),
        category=category,
        only_negative=only_negative,
        limit=limit,
    )


@router.get("/orders", response_model=list[OrderRowOut], summary="Sipariş listesi + kâr")
def get_orders(
    workspace: Workspace = Depends(get_workspace),
    start: date | None = Query(default=None, alias="from"),
    end: date | None = Query(default=None, alias="to"),
    only_negative: bool = False,
    limit: int = Query(default=200, le=1000),
) -> list[analytics.OrderRow]:
    """Dönemdeki siparişler; detay ekranının giriş kapısı."""
    return analytics.order_rows(
        workspace.session,
        _period(start, end),
        only_negative=only_negative,
        limit=limit,
    )


@router.get(
    "/orders/{order_id}",
    response_model=OrderDetailOut,
    summary="Sipariş detayı — satır bazlı şelale dökümü",
)
def get_order_detail(
    order_id: uuid.UUID,
    workspace: Workspace = Depends(get_workspace),
) -> analytics.OrderDetail:
    """Başka markanın siparişi de 404 döner — varlığı sızdırılmaz (spec §3A.6)."""
    detail = analytics.order_detail(workspace.session, order_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bulunamadı")
    return detail
