"""Kimlik uçları (spec §8, §3A.1)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_claims, get_session, is_feature_enabled
from app.core.config import get_settings
from app.core.context import system_scope
from app.core.security import (
    TokenClaims,
    TokenError,
    create_access_token,
    verify_sso_token,
)
from app.models.enums import UserRole
from app.models.identity import Brand, Tenant, User, UserBrandRole
from app.schemas.workspace import (
    BrandAccess,
    DevLoginRequest,
    MeResponse,
    SsoExchangeRequest,
    SwitchBrandRequest,
    TokenResponse,
)
from app.seeds.base import ALL_FEATURES

router = APIRouter(prefix="/auth", tags=["auth"])

INVALID_CREDENTIALS = "Kimlik doğrulanamadı"


def _load_user_by_email(session: Session, email: str) -> tuple[User, dict[str, str]] | None:
    """Kullanıcıyı ve marka rollerini (slug → rol) yükler."""
    with system_scope():
        user = session.scalar(select(User).where(User.email == email, User.is_active.is_(True)))
        if user is None:
            return None
        rows = session.execute(
            select(Brand.slug, UserBrandRole.role)
            .join(UserBrandRole, UserBrandRole.brand_id == Brand.id)
            .where(UserBrandRole.user_id == user.id)
        ).all()
    return user, {slug: role.value for slug, role in rows}


def _issue_token(
    user: User, brand_roles: dict[str, str], requested_brand: str | None
) -> TokenResponse:
    """Aktif workspace'i seçip token üretir."""
    if requested_brand is not None and requested_brand not in brand_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Bu workspace için yetkiniz yok"
        )
    active_brand = requested_brand or (sorted(brand_roles)[0] if brand_roles else None)
    claims = TokenClaims(
        tenant_id=user.tenant_id,
        user_id=user.id,
        email=user.email,
        brand_roles=brand_roles,
        active_brand=active_brand,
        is_holding_viewer=user.is_holding_viewer,
    )
    return TokenResponse(access_token=create_access_token(claims), active_brand=active_brand)


@router.post("/sso-exchange", response_model=TokenResponse, summary="ops.mokka SSO → Kavun token")
def sso_exchange(
    payload: SsoExchangeRequest, session: Session = Depends(get_session)
) -> TokenResponse:
    """ops.mokka'nın imzaladığı token'ı Kavun token'ına çevirir (spec §8)."""
    secret = get_settings().ops_sso_secret
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SSO yapılandırılmamış (OPS_SSO_SECRET)",
        )
    try:
        sso_claims = verify_sso_token(payload.sso_token, secret=secret)
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=INVALID_CREDENTIALS
        ) from exc

    found = _load_user_by_email(session, str(sso_claims["email"]))
    if found is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=INVALID_CREDENTIALS)
    user, brand_roles = found
    return _issue_token(user, brand_roles, payload.brand)


@router.post("/dev-login", response_model=TokenResponse, summary="Geliştirme girişi (local/ci)")
def dev_login(payload: DevLoginRequest, session: Session = Depends(get_session)) -> TokenResponse:
    """Parolasız geliştirme girişi.

    Yalnızca `local` ve `ci` ortamlarında vardır; diğer ortamlarda 404 döner —
    ucun varlığı bile sızdırılmaz.
    """
    if get_settings().environment not in ("local", "ci"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bulunamadı")

    found = _load_user_by_email(session, payload.email)
    if found is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=INVALID_CREDENTIALS)
    user, brand_roles = found
    return _issue_token(user, brand_roles, payload.brand)


@router.post("/switch-brand", response_model=TokenResponse, summary="Workspace değiştir")
def switch_brand(
    payload: SwitchBrandRequest,
    claims: TokenClaims = Depends(get_claims),
    session: Session = Depends(get_session),
) -> TokenResponse:
    """Aktif workspace'i değiştirir; yetkisiz markaya geçiş 403 döner (spec §3A.1)."""
    with system_scope(claims.tenant_id):
        user = session.get(User, claims.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=INVALID_CREDENTIALS)
    return _issue_token(user, claims.brand_roles, payload.brand)


@router.get("/me", response_model=MeResponse, summary="Oturum bilgisi")
def me(
    claims: TokenClaims = Depends(get_claims), session: Session = Depends(get_session)
) -> MeResponse:
    """Kullanıcı, yetkili markalar ve aktif workspace'in modül bayrakları."""
    with system_scope(claims.tenant_id):
        user = session.get(User, claims.user_id)
        tenant = session.get(Tenant, claims.tenant_id)
        if user is None or tenant is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail=INVALID_CREDENTIALS
            )
        brands = session.scalars(
            select(Brand).where(
                Brand.tenant_id == claims.tenant_id, Brand.slug.in_(claims.brand_roles or [""])
            )
        ).all()
        active_brand_id: uuid.UUID | None = next(
            (brand.id for brand in brands if brand.slug == claims.active_brand), None
        )
        features = (
            {
                feature: is_feature_enabled(session, active_brand_id, feature)
                for feature in ALL_FEATURES
            }
            if active_brand_id
            else {}
        )

    return MeResponse(
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        tenant=tenant.slug,
        active_brand=claims.active_brand,
        brands=[
            BrandAccess(
                slug=brand.slug,
                name=brand.name,
                role=UserRole(claims.brand_roles[brand.slug]),
            )
            for brand in sorted(brands, key=lambda item: item.slug)
        ],
        is_holding_viewer=user.is_holding_viewer,
        features=features,
    )
