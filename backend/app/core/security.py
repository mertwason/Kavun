"""JWT üretimi ve doğrulaması (spec §8).

Kavun kendi kullanıcı parolasını tutmaz: kimlik ops.mokka SSO'sundan gelir
(`POST /auth/sso-exchange`). Token, tenant + aktif marka + rol bilgisini taşır;
brand-scope guard'ı bu bilgiyle çalışır.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid
from dataclasses import dataclass
from typing import Any

from app.core.config import get_settings
from app.models.enums import UserRole


class TokenError(ValueError):
    """Token geçersiz, süresi dolmuş ya da imzası tutmuyor."""


@dataclass(frozen=True)
class TokenClaims:
    """Token içeriği — `active_brand` workspace bağlamını taşır (spec §3A.1)."""

    tenant_id: uuid.UUID
    user_id: uuid.UUID
    email: str
    brand_roles: dict[str, str]
    active_brand: str | None = None
    is_holding_viewer: bool = False
    expires_at: int = 0

    def role_for(self, brand_slug: str) -> UserRole | None:
        """Kullanıcının o markadaki rolü; yetkisi yoksa None."""
        raw = self.brand_roles.get(brand_slug)
        return UserRole(raw) if raw else None


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _sign(message: bytes, secret: str) -> str:
    return _b64url_encode(hmac.new(secret.encode("utf-8"), message, hashlib.sha256).digest())


def create_access_token(claims: TokenClaims, *, expires_in: int | None = None) -> str:
    """HS256 imzalı JWT üretir."""
    settings = get_settings()
    lifetime = expires_in if expires_in is not None else settings.jwt_expire_minutes * 60
    payload = {
        "sub": str(claims.user_id),
        "tenant_id": str(claims.tenant_id),
        "email": claims.email,
        "brand_roles": claims.brand_roles,
        "active_brand": claims.active_brand,
        "holding": claims.is_holding_viewer,
        "exp": int(time.time()) + lifetime,
    }
    header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode("utf-8"))
    body = _b64url_encode(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    message = f"{header}.{body}".encode("ascii")
    return f"{header}.{body}.{_sign(message, settings.jwt_secret)}"


def decode_access_token(token: str) -> TokenClaims:
    """Token'ı doğrular ve claim'leri döndürür. Geçersizse `TokenError`."""
    settings = get_settings()
    try:
        header, body, signature = token.split(".")
    except ValueError as exc:
        raise TokenError("Token biçimi geçersiz") from exc

    expected = _sign(f"{header}.{body}".encode("ascii"), settings.jwt_secret)
    if not hmac.compare_digest(expected, signature):
        raise TokenError("Token imzası doğrulanamadı")

    try:
        payload: dict[str, Any] = json.loads(_b64url_decode(body))
    except (ValueError, UnicodeDecodeError) as exc:
        raise TokenError("Token içeriği okunamadı") from exc

    if int(payload.get("exp", 0)) < int(time.time()):
        raise TokenError("Token süresi dolmuş")

    try:
        return TokenClaims(
            tenant_id=uuid.UUID(payload["tenant_id"]),
            user_id=uuid.UUID(payload["sub"]),
            email=payload["email"],
            brand_roles=dict(payload.get("brand_roles") or {}),
            active_brand=payload.get("active_brand"),
            is_holding_viewer=bool(payload.get("holding", False)),
            expires_at=int(payload["exp"]),
        )
    except (KeyError, ValueError) as exc:
        raise TokenError("Token alanları eksik") from exc


def verify_sso_token(token: str, *, secret: str) -> dict[str, Any]:
    """ops.mokka SSO token'ını doğrular (aynı HS256 şeması, ayrı secret).

    Kavun kendi kullanıcı dizinini tutmaz; SSO token'ındaki e-posta ile
    `users` tablosundaki kayıt eşleştirilir.
    """
    try:
        header, body, signature = token.split(".")
    except ValueError as exc:
        raise TokenError("SSO token biçimi geçersiz") from exc

    expected = _sign(f"{header}.{body}".encode("ascii"), secret)
    if not hmac.compare_digest(expected, signature):
        raise TokenError("SSO token imzası doğrulanamadı")

    payload: dict[str, Any] = json.loads(_b64url_decode(body))
    if int(payload.get("exp", 0)) < int(time.time()):
        raise TokenError("SSO token süresi dolmuş")
    if not payload.get("email"):
        raise TokenError("SSO token e-posta içermiyor")
    return payload
