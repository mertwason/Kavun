"""Stok ve maliyet uçları — durum, hareket defteri, açılış stoku (spec §12C.4, §12C.5)."""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import Workspace, get_workspace, require_role
from app.models.catalog import Product
from app.models.enums import UserRole
from app.schemas.b2b import DamageIn, DamageRowOut
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


@router.post(
    "/damage",
    response_model=LedgerEntryOut,
    status_code=status.HTTP_201_CREATED,
    summary="Fire/hasar kaydı (gerekçe zorunlu)",
)
def record_damage(
    payload: DamageIn,
    workspace: Workspace = Depends(require_role(UserRole.ADMIN, UserRole.EDITOR)),
) -> LedgerEntryOut:
    """Hasar stoktan mevcut ortalama maliyetle düşer; ortalama değişmez (spec §12C.10)."""
    product = workspace.session.scalar(select(Product).where(Product.id == payload.product_id))
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ürün bulunamadı")
    try:
        entry = inventory.damage(
            workspace.session, product=product, qty=payload.qty, reason=payload.reason
        )
    except inventory.InventoryError as exc:
        workspace.session.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    workspace.session.commit()
    return LedgerEntryOut.model_validate(entry)


@router.get("/damage", response_model=list[DamageRowOut], summary="SKU bazlı hasar oranı")
def damage_report(
    workspace: Workspace = Depends(get_workspace),
) -> list[DamageRowOut]:
    """Porselen-cam üründe kritik metrik: hasar / (hasar + satış)."""
    return [DamageRowOut.model_validate(row) for row in inventory.damage_rows(workspace.session)]


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
