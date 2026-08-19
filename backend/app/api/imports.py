"""İthalat dosyası ve kur farkı uçları (spec §12C.7-8).

Tüm uçlar `import_files` bayrağına bağlıdır: bayrak kapalıysa **404** döner (403 değil —
modülün varlığı sızdırılmaz, spec §3A.4).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.api.deps import Workspace, require_feature, require_role
from app.models.catalog import Supplier
from app.models.enums import UserRole
from app.models.inventory import ImportFile, PurchaseInvoice
from app.schemas.imports import (
    ConfirmResultOut,
    CostItemIn,
    CostItemOut,
    FxExposureOut,
    ImportFileDetailOut,
    ImportFileIn,
    ImportFileSummaryOut,
    LandedLineOut,
    PaymentIn,
    PaymentOut,
)
from app.services import imports

router = APIRouter(prefix="/{brand_slug}/imports", tags=["imports"])

FEATURE = "import_files"


def _file(workspace: Workspace, file_id: uuid.UUID) -> ImportFile:
    record = workspace.session.scalar(select(ImportFile).where(ImportFile.id == file_id))
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="İthalat dosyası yok")
    return record


def _fail(exc: imports.ImportFileError, workspace: Workspace) -> HTTPException:
    workspace.session.rollback()
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))


@router.get("", response_model=list[ImportFileSummaryOut], summary="İthalat dosyaları")
def list_files(
    workspace: Workspace = Depends(require_feature(FEATURE)),
) -> list[ImportFileSummaryOut]:
    """Marka kapsamlı dosya listesi."""
    return [ImportFileSummaryOut.model_validate(row) for row in imports.files(workspace.session)]


@router.get("/fx-exposure", response_model=list[FxExposureOut], summary="Açık döviz pozisyonu")
def fx_exposure(
    workspace: Workspace = Depends(require_feature(FEATURE)),
) -> list[FxExposureOut]:
    """§12C.8 raporu: açık pozisyon, maliyet kuru, gerçekleşmiş kur farkı."""
    return [FxExposureOut.model_validate(row) for row in imports.fx_exposure(workspace.session)]


@router.post(
    "",
    response_model=ImportFileSummaryOut,
    status_code=status.HTTP_201_CREATED,
    summary="Yeni ithalat dosyası",
)
def create_file(
    payload: ImportFileIn,
    workspace: Workspace = Depends(require_role(UserRole.ADMIN, UserRole.EDITOR)),
) -> ImportFileSummaryOut:
    """Dosya açar. Bayrak kontrolü rol kontrolünden sonra ayrıca uygulanır."""
    _guard_feature(workspace)
    record = ImportFile(
        tenant_id=workspace.brand.tenant_id,
        brand_id=workspace.brand_id,
        supplier_id=payload.supplier_id,
        file_no=payload.file_no,
        beyanname_no=payload.beyanname_no,
        beyanname_date=payload.beyanname_date,
        currency=payload.currency.upper(),
        fx_rate_beyanname=payload.fx_rate_beyanname,
        import_vat_paid=payload.import_vat_paid,
    )
    workspace.session.add(record)
    workspace.session.commit()
    return ImportFileSummaryOut.model_validate(record)


@router.get("/{file_id}", response_model=ImportFileDetailOut, summary="Dosya detayı")
def get_file(
    file_id: uuid.UUID,
    workspace: Workspace = Depends(require_feature(FEATURE)),
) -> ImportFileDetailOut:
    """Masraf kalemleri + satır bazlı dağıtım önizlemesi + ödemeler."""
    record = _file(workspace, file_id)
    session = workspace.session
    lines = imports.landed_costs(session, import_file=record)
    supplier = session.scalar(select(Supplier).where(Supplier.id == record.supplier_id))
    invoice_ids = [row.id for row in imports.file_invoices(session, import_file_id=record.id)]
    return ImportFileDetailOut(
        file=ImportFileSummaryOut.model_validate(record),
        supplier_name=supplier.name if supplier else "—",
        cost_items=[
            CostItemOut.model_validate(item)
            for item in imports.cost_items(session, import_file_id=record.id)
        ],
        cost_total_try=imports.import_cost_total(session, import_file_id=record.id),
        goods_total_try=sum((line.goods_total_try for line in lines), start=imports.ZERO),
        lines=[LandedLineOut.model_validate(line) for line in lines],
        payments=[
            PaymentOut.model_validate(row)
            for row in imports.payments(session, import_file_id=record.id)
        ],
        invoice_ids=invoice_ids,
    )


@router.post(
    "/{file_id}/cost-items",
    response_model=CostItemOut,
    status_code=status.HTTP_201_CREATED,
    summary="Masraf kalemi ekle",
)
def add_cost_item(
    file_id: uuid.UUID,
    payload: CostItemIn,
    workspace: Workspace = Depends(require_role(UserRole.ADMIN, UserRole.EDITOR)),
) -> CostItemOut:
    """İthalat KDV'si buraya girilmez; dosyanın `import_vat_paid` alanında durur."""
    _guard_feature(workspace)
    record = _file(workspace, file_id)
    try:
        item = imports.add_cost_item(
            workspace.session,
            import_file=record,
            item_type=payload.item_type,
            amount_original=payload.amount_original,
            currency=payload.currency,
            fx_rate=payload.fx_rate,
            vendor=payload.vendor,
            doc_ref=payload.doc_ref,
        )
    except imports.ImportFileError as exc:
        raise _fail(exc, workspace) from exc
    workspace.session.commit()
    return CostItemOut.model_validate(item)


@router.post(
    "/{file_id}/invoices/{invoice_id}",
    response_model=ImportFileDetailOut,
    summary="Mal faturasını dosyaya bağla",
)
def attach_invoice(
    file_id: uuid.UUID,
    invoice_id: uuid.UUID,
    workspace: Workspace = Depends(require_role(UserRole.ADMIN, UserRole.EDITOR)),
) -> ImportFileDetailOut:
    """Bağlanan faturanın landed cost'u artık dosyadan gelir (§12C.7)."""
    _guard_feature(workspace)
    record = _file(workspace, file_id)
    invoice = workspace.session.scalar(
        select(PurchaseInvoice).where(PurchaseInvoice.id == invoice_id)
    )
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fatura bulunamadı")
    try:
        imports.attach_invoice(workspace.session, import_file=record, invoice=invoice)
    except imports.ImportFileError as exc:
        raise _fail(exc, workspace) from exc
    workspace.session.commit()
    return get_file(file_id, workspace)


@router.post(
    "/{file_id}/confirm", response_model=ConfirmResultOut, summary="Dosyayı onayla (stoka işle)"
)
def confirm_file(
    file_id: uuid.UUID,
    workspace: Workspace = Depends(require_role(UserRole.ADMIN, UserRole.EDITOR)),
) -> ConfirmResultOut:
    """Ledger + WAC + `sku_costs` zinciri bağlı her fatura için çalışır."""
    _guard_feature(workspace)
    record = _file(workspace, file_id)
    try:
        totals = imports.confirm_file(
            workspace.session, import_file=record, user=workspace.claims.email
        )
    except imports.ImportFileError as exc:
        raise _fail(exc, workspace) from exc
    except Exception:
        workspace.session.rollback()
        raise
    workspace.session.commit()
    return ConfirmResultOut(**totals)


@router.post(
    "/{file_id}/payments",
    response_model=PaymentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Ödeme kaydet (kur farkı hesaplanır)",
)
def record_payment(
    file_id: uuid.UUID,
    payload: PaymentIn,
    workspace: Workspace = Depends(require_role(UserRole.ADMIN, UserRole.EDITOR)),
) -> PaymentOut:
    """Kur farkı ürün maliyetine dokunmaz; ayrı satırda raporlanır (§12C.8)."""
    _guard_feature(workspace)
    record = _file(workspace, file_id)
    try:
        payment = imports.record_payment(
            workspace.session,
            import_file=record,
            pay_date=payload.pay_date,
            amount_original=payload.amount_original,
            fx_rate_payment=payload.fx_rate_payment,
            currency=payload.currency,
        )
    except imports.ImportFileError as exc:
        raise _fail(exc, workspace) from exc
    workspace.session.commit()
    return PaymentOut.model_validate(payment)


def _guard_feature(workspace: Workspace) -> None:
    """Rol bağımlılığı kullanan uçlarda bayrak kontrolü (kapalı modül → 404)."""
    from app.api.deps import FEATURE_DISABLED_DETAIL, is_feature_enabled

    if not is_feature_enabled(workspace.session, workspace.brand_id, FEATURE):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=FEATURE_DISABLED_DETAIL)
