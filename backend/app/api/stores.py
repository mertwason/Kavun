"""Mağaza yönetimi uçları — `/{brand_slug}/stores` (spec §8, §5.1)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.deps import Workspace, get_workspace, require_role
from app.core import crypto
from app.models.enums import ChannelCode, UserRole
from app.models.identity import Store, StoreCredential
from app.schemas.store import (
    REQUIRED_CREDENTIAL_FIELDS,
    CredentialStatus,
    CredentialWrite,
    StoreCreate,
    StoreSummary,
    StoreUpdate,
)
from app.services import stores as store_service

router = APIRouter(prefix="/{brand_slug}/stores", tags=["stores"])

VAULT_UNAVAILABLE = (
    "Credential kasası kullanılamıyor: KAVUN_ENCRYPTION_KEY tanımlı değil "
    "(üret: python -m app.cli generate-key)"
)


def _status(credential: StoreCredential | None) -> CredentialStatus:
    """Credential durumunu içeriği açmadan özetler."""
    if credential is None:
        return CredentialStatus(configured=False)
    return CredentialStatus(
        configured=True,
        created_at=credential.created_at,
        rotated_at=credential.rotated_at,
    )


def _summary(
    store: Store, channel_code: ChannelCode, credential: StoreCredential | None
) -> StoreSummary:
    return StoreSummary(
        id=store.id,
        name=store.name,
        channel=channel_code,
        external_seller_id=store.external_seller_id,
        is_active=store.is_active,
        service_fee_per_order=store.service_fee_per_order,
        last_synced_at=store.last_synced_at,
        credentials=_status(credential),
    )


def _require_store(workspace: Workspace, store_id: uuid.UUID) -> Store:
    """Mağazayı aktif marka kapsamında bulur; başka markanınki 404 döner."""
    try:
        return store_service.get_store(workspace.session, store_id)
    except store_service.StoreNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bulunamadı") from exc


def _require_vault() -> None:
    """Kasa yoksa fail-closed: credential yazma/okuma denenmez."""
    if not crypto.is_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=VAULT_UNAVAILABLE
        )


@router.get("", response_model=list[StoreSummary], summary="Mağaza listesi + sync durumu")
def list_stores(workspace: Workspace = Depends(get_workspace)) -> list[StoreSummary]:
    """Aktif markanın mağazaları. Credential içeriği değil, yalnızca durumu döner."""
    return [
        _summary(store, channel.code, credential)
        for store, channel, credential in store_service.list_stores(workspace.session)
    ]


@router.post(
    "",
    response_model=StoreSummary,
    status_code=status.HTTP_201_CREATED,
    summary="Mağaza ekle",
)
def create_store(
    payload: StoreCreate,
    workspace: Workspace = Depends(require_role(UserRole.ADMIN, UserRole.EDITOR)),
) -> StoreSummary:
    """Aktif markaya mağaza ekler."""
    try:
        channel = store_service.get_channel(workspace.session, payload.channel)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Kanal tanımlı değil"
        ) from exc

    store = Store(
        tenant_id=workspace.claims.tenant_id,
        brand_id=workspace.brand_id,
        channel_id=channel.id,
        name=payload.name,
        external_seller_id=payload.external_seller_id,
        service_fee_per_order=payload.service_fee_per_order,
    )
    workspace.session.add(store)
    workspace.session.commit()
    return _summary(store, channel.code, None)


@router.patch("/{store_id}", response_model=StoreSummary, summary="Mağaza güncelle")
def update_store(
    store_id: uuid.UUID,
    payload: StoreUpdate,
    workspace: Workspace = Depends(require_role(UserRole.ADMIN, UserRole.EDITOR)),
) -> StoreSummary:
    """Yalnızca gönderilen alanları değiştirir."""
    store = _require_store(workspace, store_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(store, field, value)
    workspace.session.commit()

    channel_code = store_service.get_channel_code(workspace.session, store)
    return _summary(store, channel_code, store_service.credential_status(workspace.session, store))


@router.get(
    "/{store_id}/credentials",
    response_model=CredentialStatus,
    summary="Credential durumu (içerik dönmez)",
)
def credential_status(
    store_id: uuid.UUID, workspace: Workspace = Depends(get_workspace)
) -> CredentialStatus:
    """Credential var mı, ne zaman güncellendi."""
    store = _require_store(workspace, store_id)
    return _status(store_service.credential_status(workspace.session, store))


@router.post(
    "/{store_id}/credentials",
    response_model=CredentialStatus,
    summary="Credential kaydet (şifreli)",
)
def save_credentials(
    store_id: uuid.UUID,
    payload: CredentialWrite,
    workspace: Workspace = Depends(require_role(UserRole.ADMIN)),
) -> CredentialStatus:
    """Credential'ı Fernet ile şifreleyip kaydeder; içerik yanıtta dönmez (spec §3.6)."""
    _require_vault()
    store = _require_store(workspace, store_id)
    channel_code = store_service.get_channel_code(workspace.session, store)

    try:
        credential = store_service.save_credentials(
            workspace.session,
            store,
            payload.values,
            REQUIRED_CREDENTIAL_FIELDS.get(channel_code, ()),
        )
    except store_service.MissingCredentialFieldsError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    workspace.session.commit()
    return _status(credential)


@router.post(
    "/{store_id}/credentials/rotate",
    response_model=CredentialStatus,
    summary="Credential'ı güncel anahtarla yeniden şifrele",
)
def rotate_credentials(
    store_id: uuid.UUID,
    workspace: Workspace = Depends(require_role(UserRole.ADMIN)),
) -> CredentialStatus:
    """Anahtar rotasyonu: içerik değişmez, kayıt yeni anahtarla saklanır."""
    _require_vault()
    store = _require_store(workspace, store_id)
    try:
        credential = store_service.rotate_credentials(workspace.session, store)
    except store_service.CredentialNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bulunamadı") from exc
    workspace.session.commit()
    return _status(credential)


@router.delete(
    "/{store_id}/credentials",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Credential sil",
)
def delete_credentials(
    store_id: uuid.UUID,
    workspace: Workspace = Depends(require_role(UserRole.ADMIN)),
) -> Response:
    """Kayıtlı credential'ı siler."""
    store = _require_store(workspace, store_id)
    try:
        store_service.delete_credentials(workspace.session, store)
    except store_service.CredentialNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bulunamadı") from exc
    workspace.session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
