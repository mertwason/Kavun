"""Kargo faturası uçları — `estimated → actual` (spec §5.3, §6.2)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from fastapi import status as http_status
from sqlalchemy import select

from app.api.deps import Workspace, get_workspace, require_role
from app.models.enums import ChannelCode, UserRole
from app.models.identity import Channel, Store
from app.schemas.cargo import CargoImportOut, CargoInvoiceOut, CargoRowOut, CostStateOut
from app.services import cargo

router = APIRouter(prefix="/{brand_slug}/cargo-invoices", tags=["cargo"])

XLSX_MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def _marketplace_store(workspace: Workspace) -> Store:
    """Faturanın ait olduğu mağaza: markanın pazaryeri mağazası (manuel kanal değil)."""
    manual = workspace.session.scalar(select(Channel).where(Channel.code == ChannelCode.MANUAL))
    statement = select(Store).order_by(Store.name)
    if manual is not None:
        statement = statement.where(Store.channel_id != manual.id)
    store = workspace.session.scalar(statement)
    if store is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail="Bu markada mağaza tanımlı değil"
        )
    return store


@router.get("", response_model=list[CargoInvoiceOut], summary="Kargo faturaları")
def list_invoices(workspace: Workspace = Depends(get_workspace)) -> list[CargoInvoiceOut]:
    """Marka kapsamlı fatura listesi."""
    return [CargoInvoiceOut.model_validate(row) for row in cargo.invoices(workspace.session)]


@router.get("/cost-state", response_model=CostStateOut, summary="Kesinleşme durumu")
def cost_state(workspace: Workspace = Depends(get_workspace)) -> CostStateOut:
    """Kaç gönderinin kargo maliyeti kesinleşti, kaçı hâlâ tahmini."""
    return CostStateOut.model_validate(cargo.cost_state_summary(workspace.session))


@router.get("/template", summary="Kargo faturası şablonu (xlsx)")
def download_template(workspace: Workspace = Depends(get_workspace)) -> Response:
    """İndirilen dosya birebir yüklenebilir olmalıdır (KVN-10 disiplini)."""
    filename = f"{workspace.brand.slug}-kargo-faturasi-sablon.xlsx"
    return Response(
        content=cargo.template_workbook(),
        media_type=XLSX_MEDIA,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/import", response_model=CargoImportOut, summary="Kargo faturasını eşleştir")
async def import_invoice(
    file: UploadFile = File(...),
    invoice_no: str = Form(...),
    period: str = Form(...),
    dry_run: bool = Query(default=True, description="true iken hiçbir şey yazılmaz"),
    workspace: Workspace = Depends(require_role(UserRole.ADMIN, UserRole.EDITOR)),
) -> CargoImportOut:
    """Eşleşen gönderilerin maliyeti kesinleşir ve kâr yeniden hesaplanır (spec §6.2)."""
    payload = await file.read()
    if len(payload) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=http_status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Dosya çok büyük"
        )
    store = _marketplace_store(workspace)
    try:
        summary = cargo.import_invoice(
            workspace.session,
            payload=payload,
            store=store,
            invoice_no=invoice_no,
            period=period,
            dry_run=dry_run,
        )
    except cargo.TemplateError as exc:
        workspace.session.rollback()
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    if not dry_run:
        workspace.session.commit()
    return CargoImportOut(
        dry_run=summary.dry_run,
        rows=summary.rows,
        kesinlesti=summary.kesinlesti,
        zaten_kesin=summary.zaten_kesin,
        eslesmedi=summary.eslesmedi,
        hata=summary.hata,
        total_amount=summary.total_amount,
        delta=summary.delta,
        invoice_id=summary.invoice_id,
        results=[CargoRowOut.model_validate(row) for row in summary.results],
    )
