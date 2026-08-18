"""KVN-03: token üretimi ve doğrulaması (spec §8)."""

from __future__ import annotations

import uuid

import pytest

from app.core.security import (
    TokenClaims,
    TokenError,
    create_access_token,
    decode_access_token,
    verify_sso_token,
)
from app.models.enums import UserRole


def _claims(**overrides: object) -> TokenClaims:
    base = {
        "tenant_id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "email": "mert@mokkalabs.com",
        "brand_roles": {"alessi": "admin", "kahveji": "viewer"},
        "active_brand": "alessi",
        "is_holding_viewer": True,
    }
    return TokenClaims(**{**base, **overrides})  # type: ignore[arg-type]


def test_token_roundtrip_preserves_workspace_claims() -> None:
    """Token tenant, kullanıcı, roller ve aktif workspace'i taşır (spec §3A.1)."""
    original = _claims()
    decoded = decode_access_token(create_access_token(original))

    assert decoded.tenant_id == original.tenant_id
    assert decoded.user_id == original.user_id
    assert decoded.active_brand == "alessi"
    assert decoded.is_holding_viewer is True
    assert decoded.role_for("kahveji") == UserRole.VIEWER
    assert decoded.role_for("bilinmeyen") is None


def test_tampered_payload_is_rejected() -> None:
    """İçeriği değiştirilmiş token imza kontrolüne takılır."""
    token = create_access_token(_claims())
    header, body, signature = token.split(".")
    tampered = f"{header}.{body[:-4]}AAAA.{signature}"

    with pytest.raises(TokenError):
        decode_access_token(tampered)


def test_expired_token_is_rejected() -> None:
    """Süresi dolmuş token kabul edilmez."""
    token = create_access_token(_claims(), expires_in=-10)
    with pytest.raises(TokenError):
        decode_access_token(token)


def test_malformed_token_is_rejected() -> None:
    """Biçimi bozuk token anlaşılır hata verir."""
    with pytest.raises(TokenError):
        decode_access_token("bu-bir-token-degil")


def test_sso_token_requires_matching_secret() -> None:
    """SSO token'ı ops.mokka'nın secret'ıyla doğrulanır."""
    import json
    import time

    from app.core.security import _b64url_encode, _sign

    payload = {"email": "mert@mokkalabs.com", "exp": int(time.time()) + 60}
    header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    body = _b64url_encode(json.dumps(payload).encode())
    message = f"{header}.{body}".encode()
    token = f"{header}.{body}.{_sign(message, 'ops-secret')}"

    assert verify_sso_token(token, secret="ops-secret")["email"] == "mert@mokkalabs.com"
    with pytest.raises(TokenError):
        verify_sso_token(token, secret="baska-secret")
