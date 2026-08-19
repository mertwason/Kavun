"""Stok ve maliyet uçları — durum, hareket defteri, açılış stoku (spec §12C.4, §12C.5)."""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import Workspace, get_workspace, require_role
from app.models.catalog import Product
from app.models.enums import UserRole
from app.schemas.inventory import (
    AdjustmentIn,
    LedgerEntryOut,
    OpeningStockIn,
    RebuildOut,
    StockRowOut,
)
from app.services import inventory

router = APIRouter(prefix="/{brand_slug}/inventory", tags=["inventory"])


def _product(workspace: Workspace, product_id: uuid.UUID) -> Product:
    product = workspace.session.scalar(select(Product).where(Product.id == product_id))
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ürün bulunamadı")
    return product


@router.get("", response_model=list[StockRowOut], summary="Eldeki stok ve ortalama maliyet")
def list_stock(workspace: Workspace = Depends(get_workspace)) -> list[StockRowOut]:
    """Stok & maliyet ekranı (tasarım brief'i ekran 8)."""
    return [StockRowOut.model_validate(row) for row in inventory.stock_rows(workspace.session)]


@router.get("/ledger", response_model=list[LedgerEntryOut], summary="Stok hareket defteri")
def list_ledger(
    workspace: Workspace = Depends(get_workspace),
    product_id: uuid.UUID | None = None,
    limit: int = Query(default=200, le=1000),
) -> list[LedgerEntryOut]:
    """Append-only hareket zaman çizelgesi."""
    rows = inventory.ledger_rows(workspace.session, product_id=product_id, limit=limit)
    return [LedgerEntryOut.model_validate(row) for row in rows]


@router.post(
    "/opening",
    response_model=LedgerEntryOut,
    status_code=status.HTTP_201_CREATED,
    summary="Açılış (devir) stoku gir",
)
def create_opening_stock(
    payload: OpeningStockIn,
    workspace: Workspace = Depends(require_role(UserRole.ADMIN, UserRole.EDITOR)),
) -> LedgerEntryOut:
    """§12C.4: sistem kullanılmaya başlarken eldeki stok buradan girilir (tek seferlik)."""
    product = _product(workspace, payload.product_id)
    try:
        entry = inventory.opening_stock(
            workspace.session,
            product=product,
            qty=payload.qty,
            unit_cost=payload.unit_cost,
            on_date=payload.on_date or date.today(),
            user=workspace.claims.email,
        )
    except inventory.InventoryError as exc:
        workspace.session.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    workspace.session.commit()
    return LedgerEntryOut.model_validate(entry)


@router.post(
    "/adjust",
    response_model=LedgerEntryOut,
    status_code=status.HTTP_201_CREATED,
    summary="Stok düzeltme kaydı (gerekçe zorunlu)",
)
def create_adjustment(
    payload: AdjustmentIn,
    workspace: Workspace = Depends(require_role(UserRole.ADMIN, UserRole.EDITOR)),
) -> LedgerEntryOut:
    """Geçmiş silinmez; düzeltme ayrı kayıtla yapılır (CLAUDE.md §1)."""
    product = _product(workspace, payload.product_id)
    try:
        entry = inventory.adjust(
            workspace.session,
            product=product,
            qty_delta=payload.qty_delta,
            reason=payload.reason,
            unit_cost=payload.unit_cost,
        )
    except inventory.InventoryError as exc:
        workspace.session.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    workspace.session.commit()
    return LedgerEntryOut.model_validate(entry)


@router.post("/rebuild", response_model=RebuildOut, summary="Durumu defterden yeniden kur")
def rebuild(
    dry_run: bool = Query(default=True, description="true iken yalnızca fark raporlanır"),
    workspace: Workspace = Depends(require_role(UserRole.ADMIN)),
) -> RebuildOut:
    """§12C.11: `sku_cost_state` ledger'dan yeniden üretilebilir olmalı."""
    summary = inventory.rebuild_state(workspace.session, dry_run=dry_run)
    if not dry_run:
        workspace.session.commit()
    return RebuildOut(
        products=summary.products,
        movements=summary.movements,
        mismatches=summary.mismatches,
        dry_run=dry_run,
    )
