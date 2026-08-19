"""Hakediş mutabakatı uçları (spec §7)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import Workspace, get_workspace, require_role
from app.models.enums import ChannelCode, DiffStatus, UserRole
from app.models.identity import Channel, Store
from app.schemas.reconciliation import DiffOut, ExplainIn, PeriodSummaryOut, RunOut
from app.services import reconciliation

router = APIRouter(prefix="/{brand_slug}/reconciliation", tags=["reconciliation"])


def _marketplace_store(workspace: Workspace) -> Store:
    """Hakediş yalnızca pazaryeri mağazasında olur (D2B'de hakediş yoktur)."""
    manual = workspace.session.scalar(select(Channel).where(Channel.code == ChannelCode.MANUAL))
    statement = select(Store).order_by(Store.name)
    if manual is not None:
        statement = statement.where(Store.channel_id != manual.id)
    store = workspace.session.scalar(statement)
    if store is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Bu markada mağaza tanımlı değil"
        )
    return store


@router.get("/periods", response_model=list[str], summary="Fark kaydı olan dönemler")
def list_periods(workspace: Workspace = Depends(get_workspace)) -> list[str]:
    """Ekranın dönem seçicisi."""
    return reconciliation.periods(workspace.session)


@router.get("/diffs", response_model=list[DiffOut], summary="Hakediş farkları")
def list_diffs(
    workspace: Workspace = Depends(get_workspace),
    period: str | None = None,
    diff_status: DiffStatus | None = None,
) -> list[DiffOut]:
    """Dönem ve duruma göre fark listesi (spec §7.4)."""
    rows = reconciliation.diff_contexts(workspace.session, period=period, status=diff_status)
    return [
        DiffOut.model_validate(row.diff).model_copy(
            update={"record_type": row.record_type, "order_ref": row.order_ref}
        )
        for row in rows
    ]


@router.get("/summary", response_model=PeriodSummaryOut, summary="Dönem özeti")
def summary(
    period: str,
    workspace: Workspace = Depends(get_workspace),
) -> PeriodSummaryOut:
    """Açık/açıklanmış/çözülmüş fark sayıları ve toplam fark."""
    return PeriodSummaryOut.model_validate(
        reconciliation.period_summary(workspace.session, period=period)
    )


@router.post("/run", response_model=RunOut, summary="Mutabakatı çalıştır")
def run(
    period: str,
    dry_run: bool = Query(default=True, description="true iken hiçbir kayıt yazılmaz"),
    workspace: Workspace = Depends(require_role(UserRole.ADMIN, UserRole.EDITOR)),
) -> RunOut:
    """Dönemin hakediş kalemlerini bizim hesabımızla karşılaştırır (spec §7)."""
    store = _marketplace_store(workspace)
    result = reconciliation.run(workspace.session, store=store, period=period, dry_run=dry_run)
    if not dry_run:
        workspace.session.commit()
    return RunOut(
        period=result.period,
        records=result.records,
        matched=result.matched,
        unmatched=result.unmatched,
        within_tolerance=result.within_tolerance,
        diffs=result.diffs,
        skipped=result.skipped,
        total_diff=result.total_diff,
        match_rate_pct=result.match_rate_pct,
        unmatched_refs=result.unmatched_refs[:50],
        dry_run=dry_run,
    )


@router.post("/diffs/{diff_id}/explain", response_model=DiffOut, summary="Farkı açıkla/çöz")
def explain(
    diff_id: uuid.UUID,
    payload: ExplainIn,
    workspace: Workspace = Depends(require_role(UserRole.ADMIN, UserRole.EDITOR)),
) -> DiffOut:
    """Açıklamasız kapatma yoktur: not zorunludur (spec §7.4)."""
    try:
        record = reconciliation.explain(
            workspace.session, diff_id=diff_id, note=payload.note, status=payload.status
        )
    except reconciliation.ReconciliationError as exc:
        workspace.session.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    workspace.session.commit()
    return DiffOut.model_validate(record)
