"""Uyarı uçları — `/{brand_slug}/alerts` (spec §8, §10.6).

Uyarı üretimi buraya ait değil: negatif stok, tarife değişimi, MSRP ihlali, eşleşmeyen
kargo satırı, hakediş farkı ve bayat senkron kendi akışlarında yazılır. Bu router yalnızca
**okuma ve acknowledge** sunar.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import Workspace, get_workspace, require_role
from app.models.enums import AlertSeverity, UserRole
from app.schemas.alert import AlertCountsOut, AlertOut
from app.services import alerts as service

router = APIRouter(prefix="/{brand_slug}/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertOut], summary="Uyarılar")
def list_alerts(
    severity: AlertSeverity | None = None,
    type: str | None = None,
    acknowledged: bool | None = None,
    limit: int = 200,
    workspace: Workspace = Depends(get_workspace),
) -> list[AlertOut]:
    """Aktif markanın uyarıları. `acknowledged` boşsa hepsi döner."""
    rows = service.alerts(
        workspace.session,
        severity=severity,
        alert_type=type,
        acknowledged=acknowledged,
        limit=limit,
    )
    return [AlertOut.model_validate(row) for row in rows]


@router.get("/summary", response_model=AlertCountsOut, summary="Uyarı özeti")
def alert_summary(workspace: Workspace = Depends(get_workspace)) -> AlertCountsOut:
    """Seviye bazlı açık/kapalı sayımlar + markada geçen türler."""
    counts = service.counts(workspace.session)
    return AlertCountsOut(
        open=counts.open,
        acknowledged=counts.acknowledged,
        critical_open=counts.critical_open,
        warning_open=counts.warning_open,
        info_open=counts.info_open,
        total=counts.total,
        types=service.types(workspace.session),
    )


@router.post("/{alert_id}/acknowledge", response_model=AlertOut, summary="Uyarıyı gördüm")
def acknowledge_alert(
    alert_id: uuid.UUID,
    workspace: Workspace = Depends(require_role(UserRole.ADMIN, UserRole.EDITOR)),
) -> AlertOut:
    """Uyarıyı "görüldü" işaretler. İdempotenttir; ilk damga korunur."""
    try:
        alert = service.acknowledge(workspace.session, alert_id)
    except service.AlertNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bulunamadı") from exc
    workspace.session.commit()
    return AlertOut.model_validate(alert)
