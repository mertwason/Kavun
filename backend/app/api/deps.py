"""FastAPI bağımlılıkları: kimlik, workspace bağlamı, feature bayrakları (spec §3A).

Bağımlılıklar `async def` yazılır — böylece `contextvars` ile kurulan marka bağlamı
istek görevinin (task) bağlamında yaşar ve endpoint'e taşınır.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, Path, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.context import RequestContext, holding_scope, system_scope, use_context
from app.core.db import SessionLocal
from app.core.logging import get_logger
from app.core.security import TokenClaims, TokenError, decode_access_token
from app.models.enums import UserRole
from app.models.identity import AuditLog, Brand, BrandFeature, Tenant, User

log = get_logger("api.deps")

# Kapalı modülün endpoint'i 404 döner — modülün varlığı bile sızdırılmaz (spec §3A.4).
FEATURE_DISABLED_DETAIL = "Bulunamadı"


async def get_session() -> AsyncIterator[Session]:
    """İstek başına DB oturumu."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


async def get_claims(
    request: Request,
    authorization: str | None = Header(default=None),
) -> TokenClaims:
    """`Authorization: Bearer <token>` başlığından claim'leri çözer."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kimlik doğrulaması gerekli",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        claims = decode_access_token(authorization.split(" ", 1)[1].strip())
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    request.state.claims = claims
    return claims


@dataclass
class Workspace:
    """Çözümlenmiş workspace bağlamı — endpoint'ler bunu alır."""

    brand: Brand
    role: UserRole
    claims: TokenClaims
    session: Session

    @property
    def brand_id(self) -> uuid.UUID:
        """Aktif markanın id'si."""
        return self.brand.id


def _load_brand(session: Session, tenant_id: uuid.UUID, slug: str) -> Brand | None:
    with system_scope(tenant_id):
        return session.scalar(select(Brand).where(Brand.tenant_id == tenant_id, Brand.slug == slug))


async def get_workspace(
    brand_slug: str = Path(..., description="Workspace: alessi | kahveji"),
    claims: TokenClaims = Depends(get_claims),
    session: Session = Depends(get_session),
) -> AsyncIterator[Workspace]:
    """URL'deki workspace'i çözer, yetkiyi doğrular ve marka bağlamını kurar.

    Yetkisiz marka **404** döner (403 değil): başka markanın varlığı sızdırılmaz
    (spec §3A.6).
    """
    role = claims.role_for(brand_slug)
    brand = _load_brand(session, claims.tenant_id, brand_slug)
    if brand is None or role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=FEATURE_DISABLED_DETAIL)

    context = RequestContext(
        tenant_id=claims.tenant_id,
        user_id=claims.user_id,
        brand_id=brand.id,
        brand_slug=brand.slug,
        role=role,
    )
    with use_context(context):
        yield Workspace(brand=brand, role=role, claims=claims, session=session)


def require_role(*allowed: UserRole):  # type: ignore[no-untyped-def]
    """Belirli rolleri şart koşan bağımlılık üretir."""

    async def dependency(workspace: Workspace = Depends(get_workspace)) -> Workspace:
        if workspace.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Bu işlem için yetkiniz yok"
            )
        return workspace

    return dependency


def is_feature_enabled(session: Session, brand_id: uuid.UUID, feature_code: str) -> bool:
    """Marka bazlı modül bayrağı (spec §3A.4)."""
    with system_scope():
        flag = session.scalar(
            select(BrandFeature).where(
                BrandFeature.brand_id == brand_id, BrandFeature.feature_code == feature_code
            )
        )
    return bool(flag and flag.enabled)


def require_feature(feature_code: str):  # type: ignore[no-untyped-def]
    """Kapalı modülde 404 döndüren bağımlılık üretir."""

    async def dependency(workspace: Workspace = Depends(get_workspace)) -> Workspace:
        if not is_feature_enabled(workspace.session, workspace.brand_id, feature_code):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=FEATURE_DISABLED_DETAIL
            )
        return workspace

    return dependency


@dataclass
class HoldingContext:
    """Holding görünümü bağlamı — markalar arası salt okunur erişim."""

    tenant: Tenant
    claims: TokenClaims
    session: Session


async def get_holding_context(
    claims: TokenClaims = Depends(get_claims),
    session: Session = Depends(get_session),
) -> AsyncIterator[HoldingContext]:
    """Holding yetkisini doğrular; her erişim (ve her ret) audit'e yazılır (spec §3A.3)."""
    with system_scope(claims.tenant_id):
        tenant = session.get(Tenant, claims.tenant_id)
        user = session.get(User, claims.user_id)
        allowed = bool(claims.is_holding_viewer and user is not None and user.is_holding_viewer)
        session.add(
            AuditLog(
                tenant_id=claims.tenant_id,
                user_id=claims.user_id,
                action="holding_view_granted" if allowed else "holding_view_denied",
                entity_ref="/holding",
                detail=f"brands={sorted(claims.brand_roles)}",
            )
        )
        session.commit()

    if tenant is None or not allowed:
        log.warning("holding.denied", user_id=str(claims.user_id))
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Holding görünümü için yetkiniz yok",
        )

    with holding_scope(claims.tenant_id, claims.user_id):
        yield HoldingContext(tenant=tenant, claims=claims, session=session)
