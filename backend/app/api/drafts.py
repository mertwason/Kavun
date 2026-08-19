"""Taslak ürün uçları (spec §12A.3).

Akış: form → `POST /drafts/analyze` (kaydetmeden anlık kâr kartı) → `POST /drafts`
(kaydet) → `POST /drafts/{id}/promote` (ürüne dönüştür).
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.api.deps import Workspace, get_workspace, require_role
from app.models.enums import UserRole
from app.models.workspace import ProductDraft
from app.schemas.drafts import AnalysisOut, DraftInput, DraftOut, PromotedOut
from app.services import drafts

router = APIRouter(prefix="/{brand_slug}/drafts", tags=["drafts"])


def _analysis_out(analysis: drafts.DraftAnalysis) -> AnalysisOut:
    breakdown = analysis.breakdown
    return AnalysisOut(
        revenue_gross=breakdown.revenue_gross,
        cost_cogs=breakdown.cost_cogs,
        cost_commission=breakdown.cost_commission,
        cost_cargo=breakdown.cost_cargo,
        cost_service_fee=breakdown.cost_service_fee,
        vat_net=breakdown.vat_net,
        profit=breakdown.profit,
        margin_pct=breakdown.margin_pct,
        commission_rate=analysis.commission_rate,
        commission_source=analysis.commission_source,
        warnings=list(breakdown.warnings),
        waterfall=[{"key": key, "amount": amount} for key, amount in breakdown.waterfall],
    )


def _draft_out(draft: ProductDraft, analysis: drafts.DraftAnalysis) -> DraftOut:
    return DraftOut(
        id=draft.id,
        name=draft.name,
        sku_onerisi=draft.sku_onerisi,
        alis_maliyeti=draft.alis_maliyeti,
        hedef_satis_fiyati=draft.hedef_satis_fiyati,
        kanal=draft.kanal,
        kategori=draft.kategori,
        vat_rate=draft.vat_rate,
        desi=draft.desi,
        status=draft.status,
        promoted_product_id=draft.promoted_product_id,
        analysis=_analysis_out(analysis),
    )


def _load(workspace: Workspace, draft_id: uuid.UUID) -> ProductDraft:
    """Taslağı marka kapsamında okur (`session.get()` guard'ı atlayabilir — KVN-09)."""
    draft = workspace.session.scalar(select(ProductDraft).where(ProductDraft.id == draft_id))
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bulunamadı")
    return draft


@router.post("/analyze", response_model=AnalysisOut, summary="Anlık kâr analizi (kaydetmeden)")
def analyze_input(
    payload: DraftInput,
    workspace: Workspace = Depends(get_workspace),
) -> AnalysisOut:
    """Form doldurulurken kâr kartını besler; hiçbir şey kaydedilmez (spec §12A.5)."""
    analysis = drafts.analyze(
        workspace.session,
        price=payload.hedef_satis_fiyati,
        unit_cost=payload.alis_maliyeti,
        vat_rate=payload.vat_rate,
        channel=payload.kanal,
        category=payload.kategori,
        cargo_cost=payload.kargo_tahmini,
        on_date=date.today(),
    )
    return _analysis_out(analysis)


@router.get("", response_model=list[DraftOut], summary="Taslak listesi")
def list_drafts(workspace: Workspace = Depends(get_workspace)) -> list[DraftOut]:
    """Markanın taslakları, güncel analizleriyle."""
    rows = workspace.session.scalars(
        select(ProductDraft).order_by(ProductDraft.created_at.desc())
    ).all()
    today = date.today()
    return [
        _draft_out(
            draft, drafts.analyze_draft(workspace.session, draft, cargo_cost=None, on_date=today)
        )
        for draft in rows
    ]


@router.post(
    "", response_model=DraftOut, status_code=status.HTTP_201_CREATED, summary="Taslak kaydet"
)
def create_draft(
    payload: DraftInput,
    workspace: Workspace = Depends(require_role(UserRole.ADMIN, UserRole.EDITOR)),
) -> DraftOut:
    """Taslağı kaydeder ve analizini döner (spec §12A.3)."""
    draft = drafts.create_draft(
        workspace.session,
        tenant_id=workspace.brand.tenant_id,
        brand_id=workspace.brand_id,
        name=payload.name,
        sku_onerisi=payload.sku_onerisi,
        alis_maliyeti=payload.alis_maliyeti,
        hedef_satis_fiyati=payload.hedef_satis_fiyati,
        kanal=payload.kanal,
        kategori=payload.kategori,
        vat_rate=payload.vat_rate,
        desi=payload.desi,
    )
    analysis = drafts.analyze_draft(
        workspace.session, draft, cargo_cost=payload.kargo_tahmini, on_date=date.today()
    )
    workspace.session.commit()
    return _draft_out(draft, analysis)


@router.post("/{draft_id}/promote", response_model=PromotedOut, summary="Taslağı ürüne dönüştür")
def promote_draft(
    draft_id: uuid.UUID,
    workspace: Workspace = Depends(require_role(UserRole.ADMIN, UserRole.EDITOR)),
) -> PromotedOut:
    """Ürün + maliyet + desi + fiyat kayıtları doğar; taslak `promoted` olur."""
    draft = _load(workspace, draft_id)
    try:
        product = drafts.promote(
            workspace.session, draft, today=date.today(), user=workspace.claims.email
        )
    except drafts.DraftError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    workspace.session.commit()
    return PromotedOut(product_id=product.id, sku=product.sku, name=product.name)


@router.post("/{draft_id}/discard", response_model=DraftOut, summary="Taslağı iptal et")
def discard_draft(
    draft_id: uuid.UUID,
    workspace: Workspace = Depends(require_role(UserRole.ADMIN, UserRole.EDITOR)),
) -> DraftOut:
    """Kayıt silinmez, `discarded` olarak işaretlenir."""
    draft = _load(workspace, draft_id)
    try:
        drafts.discard(workspace.session, draft)
    except drafts.DraftError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    analysis = drafts.analyze_draft(workspace.session, draft, cargo_cost=None, on_date=date.today())
    workspace.session.commit()
    return _draft_out(draft, analysis)
