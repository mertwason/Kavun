"""Marka workspace uçları — `/{brand_slug}/...` (spec §3A.1).

Bu router'daki her uç marka bağlamı içinde çalışır: `get_workspace` bağımlılığı
brand-scope guard'ını kurar, sorgular otomatik olarak aktif markaya kısıtlanır.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.api.deps import Workspace, get_workspace, require_feature
from app.models.catalog import Product
from app.models.inventory import ImportFile
from app.schemas.workspace import ImportFileSummary, ProductSummary

router = APIRouter(prefix="/{brand_slug}", tags=["workspace"])


@router.get("/products", response_model=list[ProductSummary], summary="Marka ürün listesi")
def list_products(workspace: Workspace = Depends(get_workspace), limit: int = 100) -> list[Product]:
    """Aktif workspace'in ürünleri. Filtre yazılmasa bile guard markayı uygular."""
    return list(workspace.session.scalars(select(Product).order_by(Product.sku).limit(limit)).all())


@router.get(
    "/import-files",
    response_model=list[ImportFileSummary],
    summary="İthalat dosyaları (yalnızca bayrağı açık markalarda)",
)
def list_import_files(
    workspace: Workspace = Depends(require_feature("import_files")),
) -> list[ImportFile]:
    """`import_files` bayrağı kapalı markada bu uç 404 döner (spec §3A.4)."""
    return list(workspace.session.scalars(select(ImportFile).order_by(ImportFile.file_no)).all())
