"""Komisyon tarifesi uçları — güncel oranlar, değişiklik geçmişi, etki analizi (spec §12B).

Tarife Excel yüklemesi (§12B.2) KVN-14'te bu router'a eklenecek.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import Workspace, get_workspace, require_role
from app.models.catalog import CommissionChange, CommissionRate
from app.models.enums import CommissionScope, UserRole
from app.models.identity import Channel, Store
from app.schemas.tariffs import (
    CommissionChangeOut,
    CommissionRateOut,
    TariffImpactIn,
    TariffImpactOut,
    TariffImpactRowOut,
)
from app.services import tariffs

router = APIRouter(prefix="/{brand_slug}/tariffs", tags=["tariffs"])


def _store(workspace: Workspace) -> Store:
    """Markanın Trendyol mağazası (yoksa ilki)."""
    rows = workspace.session.scalars(select(Store).order_by(Store.name)).all()
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mağaza tanımlı değil")
    channels = {row.id: row.code for row in workspace.session.scalars(select(Channel)).all()}
    for store in rows:
        code = channels.get(store.channel_id)
        if code is not None and code.value == "trendyol":
            return store
    return rows[0]


@router.get("", response_model=list[CommissionRateOut], summary="Geçerli komisyon tarifeleri")
def list_rates(
    workspace: Workspace = Depends(get_workspace),
    on_date: date | None = None,
) -> list[CommissionRateOut]:
    """Verilen tarihte (varsayılan bugün) geçerli kategori tarifeleri."""
    store = _store(workspace)
    target = on_date or date.today()
    rows = workspace.session.scalars(
        select(CommissionRate)
        .where(
            CommissionRate.store_id == store.id,
            CommissionRate.valid_from <= target,
            (CommissionRate.valid_to.is_(None)) | (CommissionRate.valid_to > target),
        )
        .order_by(CommissionRate.category_code, CommissionRate.valid_from.desc())
    ).all()
    return [
        CommissionRateOut(
            id=row.id,
            scope=row.scope,
            category_code=row.category_code,
            product_id=row.product_id,
            rate=row.rate,
            source=row.source,
            valid_from=row.valid_from,
            valid_to=row.valid_to,
            is_campaign_period=row.is_campaign_period,
        )
        for row in rows
        if row.scope is CommissionScope.CATEGORY or row.product_id is not None
    ]


@router.get(
    "/changes",
    response_model=list[CommissionChangeOut],
    summary="Komisyon değişiklik geçmişi + etki tutarları",
)
def list_changes(
    workspace: Workspace = Depends(get_workspace),
    limit: int = Query(default=50, le=200),
) -> list[CommissionChangeOut]:
    """Snapshot diff'inden doğan değişiklikler (spec §12B.3)."""
    store = _store(workspace)
    rows = workspace.session.scalars(
        select(CommissionChange)
        .where(CommissionChange.store_id == store.id)
        .order_by(CommissionChange.detected_at.desc())
        .limit(limit)
    ).all()
    return [CommissionChangeOut.model_validate(row) for row in rows]


@router.post(
    "/detect-changes",
    summary="Bugünün tarifesini dünküyle karşılaştır (günlük job'ın elle tetiklenmesi)",
)
def detect_changes(
    workspace: Workspace = Depends(require_role(UserRole.ADMIN, UserRole.EDITOR)),
) -> dict[str, object]:
    """Değişiklik varsa `commission_changes` + alert üretir (spec §12B.3)."""
    store = _store(workspace)
    summary = tariffs.detect_changes(workspace.session, store=store, on_date=date.today())
    workspace.session.commit()
    return {
        "detected": summary.detected,
        "alerts": summary.alerts,
        "monthly_profit_impact": (
            str(summary.impact.monthly_profit_impact) if summary.impact else "0"
        ),
    }


@router.post(
    "/impact",
    response_model=TariffImpactOut,
    summary="Toplu tarife senaryosu — 'komisyon %X artarsa ne olur'",
)
def tariff_impact(
    payload: TariffImpactIn,
    workspace: Workspace = Depends(get_workspace),
) -> TariffImpactOut:
    """§12B.4: etkilenen SKU'lar, yeni marjlar ve hedef marjı koruyan fiyatlar."""
    try:
        result = tariffs.tariff_impact(
            workspace.session,
            store=_store(workspace),
            on_date=date.today(),
            category=payload.category,
            new_rate=payload.new_rate,
            rate_delta=payload.rate_delta,
            target_margin_pct=payload.target_margin_pct,
            cargo_estimate=payload.kargo_tahmini,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    return TariffImpactOut(
        scope=result.scope,
        target_margin_pct=result.target_margin_pct,
        monthly_profit_impact=result.monthly_profit_impact,
        rows=[TariffImpactRowOut.model_validate(row) for row in result.rows],
    )
