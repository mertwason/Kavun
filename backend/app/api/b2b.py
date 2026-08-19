"""D2B satış importu, fire/hasar ve fiyat disiplini uçları (spec §12C.9-10).

D2B uçları `b2b_channel`, disiplin uçları `msrp_discipline` bayrağına bağlıdır; kapalı
markada 404 döner (403 değil — modülün varlığı sızdırılmaz).
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status

from app.api.deps import Workspace, require_feature, require_role
from app.models.enums import UserRole
from app.schemas.b2b import B2BImportOut, RowErrorOut, TierMarginOut, ViolationOut
from app.services import b2b, discipline

router = APIRouter(prefix="/{brand_slug}", tags=["b2b"])

B2B_FEATURE = "b2b_channel"
MSRP_FEATURE = "msrp_discipline"

TEMPLATE_MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/b2b/template", summary="D2B satış şablonu (xlsx)")
def download_template(
    workspace: Workspace = Depends(require_feature(B2B_FEATURE)),
) -> Response:
    """İndirilen dosya birebir yüklenebilir olmalıdır (KVN-10 disiplini)."""
    del workspace
    return Response(
        content=b2b.template_workbook(),
        media_type=TEMPLATE_MEDIA,
        headers={"Content-Disposition": 'attachment; filename="kavun-d2b-sablon.xlsx"'},
    )


@router.get("/b2b/tiers", response_model=list[TierMarginOut], summary="Kademe bazlı satış özeti")
def list_tiers(
    workspace: Workspace = Depends(require_feature(B2B_FEATURE)),
) -> list[TierMarginOut]:
    """Hangi müşteri kademesi ne bırakıyor (spec §12C.9)."""
    return [TierMarginOut.model_validate(row) for row in b2b.tier_margins(workspace.session)]


@router.post("/b2b/import", response_model=B2BImportOut, summary="D2B satışlarını yükle")
async def import_sales(
    file: UploadFile = File(...),
    dry_run: bool = Query(default=True, description="true iken hiçbir sipariş yazılmaz"),
    workspace: Workspace = Depends(require_role(UserRole.ADMIN, UserRole.EDITOR)),
) -> B2BImportOut:
    """Satışlar normal sipariş olarak yazılır: stok düşer, kâr motoru komisyonsuz hesaplar."""
    _guard(workspace, B2B_FEATURE)
    store = b2b.d2b_store(workspace.session)
    if store is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Bu markada D2B mağazası tanımlı değil"
        )
    payload = await file.read()
    try:
        summary = b2b.import_sales(workspace.session, payload=payload, store=store, dry_run=dry_run)
    except b2b.TemplateError as exc:
        workspace.session.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    if not dry_run:
        workspace.session.commit()
    return B2BImportOut(
        rows=summary.rows,
        orders=summary.orders,
        lines=summary.lines,
        customers=summary.customers,
        skipped=summary.skipped,
        gross_total=summary.gross_total,
        errors=[RowErrorOut.model_validate(error) for error in summary.errors],
        dry_run=dry_run,
    )


@router.get("/discipline", response_model=list[ViolationOut], summary="MSRP ve marj tabanı ihlali")
def list_violations(
    workspace: Workspace = Depends(require_feature(MSRP_FEATURE)),
    today: date | None = None,
) -> list[ViolationOut]:
    """Kural uyarır, engellemez (spec §12C.10)."""
    return [
        ViolationOut.model_validate(row)
        for row in discipline.violations(workspace.session, today=today)
    ]


def _guard(workspace: Workspace, feature: str) -> None:
    """Rol bağımlılığı kullanan uçlarda bayrak kontrolü."""
    from app.api.deps import FEATURE_DISABLED_DETAIL, is_feature_enabled

    if not is_feature_enabled(workspace.session, workspace.brand_id, feature):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=FEATURE_DISABLED_DETAIL)
