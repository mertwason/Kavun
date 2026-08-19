"""Ayarlar uçları — kargo tarifesi (spec §10.7).

Mağaza ve credential yönetimi `stores.py`'de; burada Ayarlar ekranının ikinci yarısı olan
**kargo tarife tablosu** var. Hizmet bedeli mağaza alanıdır (`PATCH /{brand}/stores/{id}`).
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import Workspace, get_workspace, require_role
from app.models.enums import UserRole
from app.schemas.cargo_tariff import ReestimateOut, TariffCreate, TariffOut, TariffPreview
from app.services import cargo_tariffs as service

router = APIRouter(prefix="/{brand_slug}/settings", tags=["settings"])


@router.get("/cargo-tariffs", response_model=list[TariffOut], summary="Kargo tarife bantları")
def list_tariffs(
    include_closed: bool = False, workspace: Workspace = Depends(get_workspace)
) -> list[TariffOut]:
    """Aktif markanın bantları. `include_closed` kapatılmış bantları da getirir."""
    rows = service.tariffs(workspace.session, include_closed=include_closed)
    return [TariffOut.model_validate(row) for row in rows]


@router.post(
    "/cargo-tariffs",
    response_model=TariffOut,
    status_code=status.HTTP_201_CREATED,
    summary="Desi bandı ekle",
)
def create_tariff(
    payload: TariffCreate,
    workspace: Workspace = Depends(require_role(UserRole.ADMIN, UserRole.EDITOR)),
) -> TariffOut:
    """Yeni bant. Geçersiz aralık 422 döner — çakışan bant sessizce kabul edilmez."""
    try:
        row = service.add_band(
            workspace.session,
            tenant_id=workspace.claims.tenant_id,
            brand_id=workspace.brand_id,
            desi_min=payload.desi_min,
            desi_max=payload.desi_max,
            price=payload.price,
            carrier=payload.carrier,
            valid_from=payload.valid_from,
            note=payload.note,
        )
    except service.InvalidBandError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    workspace.session.commit()
    return TariffOut.model_validate(row)


@router.post(
    "/cargo-tariffs/{tariff_id}/close",
    response_model=TariffOut,
    summary="Bandı kapat (silme değil)",
)
def close_tariff(
    tariff_id: uuid.UUID,
    workspace: Workspace = Depends(require_role(UserRole.ADMIN, UserRole.EDITOR)),
) -> TariffOut:
    """Bandı yürürlükten kaldırır; geçmiş tahminlerin dayanağı kayıtta kalır."""
    try:
        row = service.close_band(workspace.session, tariff_id)
    except service.TariffNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bulunamadı") from exc
    workspace.session.commit()
    return TariffOut.model_validate(row)


@router.get(
    "/cargo-tariffs/preview", response_model=TariffPreview, summary="Tarifeyi bir desi ile dene"
)
def preview_tariff(
    desi: Decimal,
    carrier: str | None = None,
    workspace: Workspace = Depends(get_workspace),
) -> TariffPreview:
    """Verilen desi bugünkü tarifede kaça çıkar; hangi kaynaktan geldiğini de söyler."""
    result = service.preview(workspace.session, desi=desi, carrier=carrier)
    return TariffPreview(desi=desi, carrier=carrier, amount=result.amount, source=result.source)


@router.post(
    "/cargo-tariffs/reestimate",
    response_model=ReestimateOut,
    summary="Tahmini gönderileri güncel tarifeyle yenile",
)
def reestimate(
    dry_run: bool = True,
    workspace: Workspace = Depends(require_role(UserRole.ADMIN, UserRole.EDITOR)),
) -> ReestimateOut:
    """Yalnızca `estimated` gönderiler; kesinleşmiş maliyet ASLA ezilmez (spec §6.2)."""
    summary = service.reestimate(workspace.session, dry_run=dry_run)
    if not dry_run:
        workspace.session.commit()
    return ReestimateOut(
        dry_run=summary.dry_run,
        shipments=summary.shipments,
        changed=summary.changed,
        skipped_actual=summary.skipped_actual,
        delta=summary.delta,
    )
