"""Fiyat listesi Excel round-trip uçları (spec §12A.1, §12A.2).

Akış: `GET /price-list/export` → dosyayı düzenle → `POST /price-list/import?dry_run=true`
(diff önizleme) → onay → `dry_run=false`. Export edilen dosya import şablonudur.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status

from app.api.deps import Workspace, get_workspace, require_role
from app.models.enums import UserRole
from app.models.workspace import ImportBatch
from app.schemas.pricelist import ImportSummaryOut, PriceRowOut
from app.services import pricelist

router = APIRouter(prefix="/{brand_slug}/price-list", tags=["price-list"])

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def _attachment(filename: str) -> dict[str, str]:
    return {"Content-Disposition": f'attachment; filename="{filename}"'}


@router.get("", response_model=list[PriceRowOut], summary="Fiyat listesi (ekran tablosu)")
def list_price_rows(workspace: Workspace = Depends(get_workspace)) -> list[pricelist.PriceRow]:
    """Ekrandaki tablo ile export edilen dosya AYNI kaynaktan beslenir (spec §12A)."""
    return pricelist.price_rows(workspace.session, today=date.today())


@router.get("/export", summary="Fiyat listesini xlsx olarak indir")
def export_price_list(workspace: Workspace = Depends(get_workspace)) -> Response:
    """Export edilen dosya aynı zamanda import şablonudur (spec §12A)."""
    today = date.today()
    payload = pricelist.export_price_list(
        workspace.session, brand_name=workspace.brand.name, today=today
    )
    filename = f"kavun-fiyat-listesi-{workspace.brand.slug}-{today.isoformat()}.xlsx"
    return Response(content=payload, media_type=XLSX_MEDIA_TYPE, headers=_attachment(filename))


@router.post(
    "/import",
    response_model=ImportSummaryOut,
    summary="Fiyat listesi yükle (dry_run ile diff önizleme)",
)
async def import_price_list(
    file: UploadFile = File(..., description="Kavun şablonuyla üretilmiş xlsx"),
    dry_run: bool = Query(default=True, description="true iken hiçbir şey yazılmaz"),
    workspace: Workspace = Depends(require_role(UserRole.ADMIN, UserRole.EDITOR)),
) -> pricelist.ImportSummary:
    """`dry_run=true` → yalnızca diff; `false` → uygulanır ve batch loglanır."""
    payload = await file.read()
    if len(payload) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Dosya çok büyük (en fazla 10 MB)",
        )

    try:
        summary = pricelist.import_price_list(
            workspace.session,
            payload,
            today=date.today(),
            user=workspace.claims.email,
            dry_run=dry_run,
        )
    except pricelist.TemplateError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    workspace.session.add(
        ImportBatch(
            tenant_id=workspace.brand.tenant_id,
            brand_id=workspace.brand_id,
            kind="price_list",
            filename=file.filename or "fiyat-listesi.xlsx",
            user=workspace.claims.email,
            dry_run=dry_run,
            yeni=summary.yeni,
            guncelleme=summary.guncelleme,
            hata=summary.hata,
        )
    )
    workspace.session.commit()
    return summary


@router.post(
    "/import/errors",
    summary="Hatalı satırların işaretlendiği dosyayı indir",
)
async def download_error_report(
    file: UploadFile = File(...),
    workspace: Workspace = Depends(require_role(UserRole.ADMIN, UserRole.EDITOR)),
) -> Response:
    """Orijinal dosya + "Hatalar" sayfası (satır no + açıklama) — spec §12A.2.3."""
    payload = await file.read()
    try:
        summary = pricelist.import_price_list(
            workspace.session, payload, today=date.today(), dry_run=True
        )
    except pricelist.TemplateError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    report = pricelist.error_workbook(payload, summary)
    return Response(
        content=report,
        media_type=XLSX_MEDIA_TYPE,
        headers=_attachment(f"hatalar-{file.filename or 'fiyat-listesi.xlsx'}"),
    )
