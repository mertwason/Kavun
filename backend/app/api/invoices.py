"""Alış faturası uçları — yükle, eşleştir, onayla (spec §12C.3, §12C.5)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select

from app.api.deps import Workspace, get_workspace, require_role
from app.models.catalog import Product, Supplier
from app.models.enums import InvoiceStatus, UserRole
from app.models.inventory import PurchaseInvoice, PurchaseInvoiceLine
from app.schemas.invoices import (
    ConfirmMatchIn,
    InvoiceDetailOut,
    InvoiceLineOut,
    InvoiceSummaryOut,
    SuggestionOut,
    SupplierOut,
    UploadResultOut,
)
from app.services import invoices

router = APIRouter(prefix="/{brand_slug}/invoices", tags=["invoices"])

MAX_UPLOAD_BYTES = 20 * 1024 * 1024


def _invoice(workspace: Workspace, invoice_id: uuid.UUID) -> PurchaseInvoice:
    record = workspace.session.scalar(
        select(PurchaseInvoice).where(PurchaseInvoice.id == invoice_id)
    )
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bulunamadı")
    return record


def _line_out(workspace: Workspace, line: PurchaseInvoiceLine) -> InvoiceLineOut:
    product = (
        workspace.session.scalar(select(Product).where(Product.id == line.product_id))
        if line.product_id
        else None
    )
    return InvoiceLineOut(
        id=line.id,
        raw_text=line.raw_text,
        product_id=line.product_id,
        sku=product.sku if product else None,
        product_name=product.name if product else None,
        qty=line.qty,
        unit_price_original=line.unit_price_original,
        unit_price_try=line.unit_price_try,
        vat_rate=line.vat_rate,
        landed_unit_cost_try=line.landed_unit_cost_try,
        match_status=line.match_status,
        suggestions=[],
    )


@router.get("/suppliers", response_model=list[SupplierOut], summary="Tedarikçiler")
def list_suppliers(workspace: Workspace = Depends(get_workspace)) -> list[SupplierOut]:
    """Fatura yükleme formundaki tedarikçi listesi."""
    rows = workspace.session.scalars(select(Supplier).order_by(Supplier.name)).all()
    return [SupplierOut.model_validate(row) for row in rows]


@router.get("", response_model=list[InvoiceSummaryOut], summary="Alış faturaları")
def list_invoices(workspace: Workspace = Depends(get_workspace)) -> list[InvoiceSummaryOut]:
    """Markanın alış faturaları (en yeni üstte)."""
    rows = workspace.session.scalars(
        select(PurchaseInvoice).order_by(PurchaseInvoice.invoice_date.desc())
    ).all()
    return [InvoiceSummaryOut.model_validate(row) for row in rows]


@router.post(
    "/upload",
    response_model=UploadResultOut,
    summary="Fatura PDF'i yükle (ayrıştır — stoka YAZMAZ)",
)
async def upload_invoice(
    file: UploadFile = File(..., description="Metin tabanlı e-arşiv/e-fatura PDF'i"),
    supplier_id: uuid.UUID = Form(...),
    invoice_no: str = Form(...),
    invoice_date: date = Form(...),
    currency: str = Form(default="TRY"),
    fx_rate: Decimal | None = Form(default=None),
    landed_cost_extra: Decimal = Form(default=Decimal("0")),
    workspace: Workspace = Depends(require_role(UserRole.ADMIN, UserRole.EDITOR)),
) -> UploadResultOut:
    """§12C.3: ayrıştırma sonucu ASLA doğrudan yazılmaz; review ekranından geçer."""
    payload = await file.read()
    if len(payload) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Dosya çok büyük (en fazla 20 MB)",
        )

    supplier = workspace.session.scalar(select(Supplier).where(Supplier.id == supplier_id))
    if supplier is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tedarikçi bulunamadı")

    try:
        result = invoices.upload_invoice(
            workspace.session,
            payload,
            supplier=supplier,
            tenant_id=workspace.brand.tenant_id,
            brand_id=workspace.brand_id,
            invoice_no=invoice_no,
            invoice_date=invoice_date,
            currency=currency,
            fx_rate=fx_rate,
            landed_cost_extra=landed_cost_extra,
            pdf_path=file.filename,
        )
    except invoices.InvoiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    workspace.session.commit()
    return UploadResultOut(
        invoice_id=result.invoice.id,
        status=result.invoice.status,
        lines=len(
            workspace.session.scalars(
                select(PurchaseInvoiceLine).where(
                    PurchaseInvoiceLine.invoice_id == result.invoice.id
                )
            ).all()
        ),
        unmatched=result.unmatched,
        totals_ok=result.validation.ok,
        lines_total=result.validation.lines_total,
        invoice_total=result.validation.invoice_total,
        message=result.validation.message,
    )


@router.get("/{invoice_id}", response_model=InvoiceDetailOut, summary="Fatura detayı + öneriler")
def get_invoice(
    invoice_id: uuid.UUID,
    workspace: Workspace = Depends(get_workspace),
) -> InvoiceDetailOut:
    """Review ekranının kaynağı: satırlar + eşleşmemişler için öneriler."""
    invoice = _invoice(workspace, invoice_id)
    supplier = workspace.session.scalar(select(Supplier).where(Supplier.id == invoice.supplier_id))
    lines = workspace.session.scalars(
        select(PurchaseInvoiceLine).where(PurchaseInvoiceLine.invoice_id == invoice.id)
    ).all()

    line_outs: list[InvoiceLineOut] = []
    for line in lines:
        out = _line_out(workspace, line)
        if line.product_id is None:
            match = invoices.match_line(
                workspace.session, supplier_id=invoice.supplier_id, raw_name=line.raw_text
            )
            out.suggestions = [
                SuggestionOut(
                    product_id=product.id,
                    sku=product.sku,
                    name=product.name,
                    confidence=score,
                )
                for product, score in match.suggestions
            ]
        line_outs.append(out)

    return InvoiceDetailOut(
        id=invoice.id,
        supplier_id=invoice.supplier_id,
        supplier_name=supplier.name if supplier else "",
        invoice_no=invoice.invoice_no,
        invoice_date=invoice.invoice_date,
        currency=invoice.currency,
        fx_rate=invoice.fx_rate,
        landed_cost_extra=invoice.landed_cost_extra,
        total=invoice.total,
        status=invoice.status,
        confirmed_at=invoice.confirmed_at,
        lines=line_outs,
    )


@router.post(
    "/{invoice_id}/lines/{line_id}/match",
    response_model=InvoiceLineOut,
    summary="Satırı SKU ile eşleştir (öğrenilir)",
)
def confirm_line_match(
    invoice_id: uuid.UUID,
    line_id: uuid.UUID,
    payload: ConfirmMatchIn,
    workspace: Workspace = Depends(require_role(UserRole.ADMIN, UserRole.EDITOR)),
) -> InvoiceLineOut:
    """§12C.3.4: onaylanan eşleştirme öğrenilir — aynı ürün bir daha sorulmaz."""
    invoice = _invoice(workspace, invoice_id)
    if invoice.status is InvoiceStatus.CONFIRMED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Onaylanmış fatura değiştirilemez; düzeltme ancak ters kayıtla yapılır",
        )

    line = workspace.session.scalar(
        select(PurchaseInvoiceLine).where(
            PurchaseInvoiceLine.id == line_id, PurchaseInvoiceLine.invoice_id == invoice.id
        )
    )
    if line is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Satır bulunamadı")

    product = workspace.session.scalar(select(Product).where(Product.id == payload.product_id))
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ürün bulunamadı")

    invoices.confirm_match(
        workspace.session, supplier_id=invoice.supplier_id, line=line, product=product
    )
    workspace.session.commit()
    return _line_out(workspace, line)


@router.post("/{invoice_id}/confirm", response_model=InvoiceDetailOut, summary="Faturayı onayla")
def confirm_invoice(
    invoice_id: uuid.UUID,
    workspace: Workspace = Depends(require_role(UserRole.ADMIN, UserRole.EDITOR)),
) -> InvoiceDetailOut:
    """§12C.3.5: ledger + WAC + `sku_costs` tek transaction'da yazılır."""
    invoice = _invoice(workspace, invoice_id)
    try:
        invoices.confirm_invoice(workspace.session, invoice, user=workspace.claims.email)
    except invoices.ImmutableInvoiceError as exc:
        workspace.session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except invoices.InvoiceError as exc:
        workspace.session.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    workspace.session.commit()
    return get_invoice(invoice_id, workspace)
