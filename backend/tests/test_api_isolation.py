"""KVN-03: API seviyesinde marka izolasyonu — spec §3A.6 kabul kriterleri."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api import deps
from app.core.context import system_scope
from app.main import create_app
from app.models.enums import UserRole
from app.models.identity import AuditLog, Brand, User, UserBrandRole
from app.seeds.base import seed_base
from app.seeds.demo import seed_demo


@pytest.fixture
def api(db_session: Session) -> Iterator[TestClient]:
    """Demo veriyle dolu, test oturumuna bağlı API istemcisi."""
    seed_base(db_session)
    seed_demo(db_session)

    async def session_override() -> Any:
        yield db_session

    app = create_app()
    app.dependency_overrides[deps.get_session] = session_override
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def _login(api: TestClient, email: str, brand: str | None = None) -> dict[str, str]:
    response = api.post("/auth/dev-login", json={"email": email, "brand": brand})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def single_brand_user(db_session: Session) -> str:
    """Yalnızca Kahveji'ye yetkili, holding yetkisi olmayan kullanıcı."""
    with system_scope():
        kahveji = db_session.scalars(select(Brand).where(Brand.slug == "kahveji")).first()
        assert kahveji is not None
        user = User(
            tenant_id=kahveji.tenant_id,
            email="tekmarka@mokkalabs.com",
            full_name="Tek Marka",
            is_holding_viewer=False,
        )
        db_session.add(user)
        db_session.flush()
        db_session.add(UserBrandRole(user_id=user.id, brand_id=kahveji.id, role=UserRole.VIEWER))
        db_session.flush()
    return user.email


# --- kimlik ----------------------------------------------------------------


def test_request_without_token_is_rejected(api: TestClient) -> None:
    """Token'sız istek 401 döner."""
    assert api.get("/kahveji/products").status_code == 401


def test_invalid_token_is_rejected(api: TestClient) -> None:
    """İmzası tutmayan token kabul edilmez."""
    response = api.get("/kahveji/products", headers={"Authorization": "Bearer sahte.token.imza"})
    assert response.status_code == 401


def test_me_lists_authorized_brands(api: TestClient) -> None:
    """`/auth/me` yalnızca yetkili markaları ve aktif workspace'i döner."""
    headers = _login(api, "demo@mokkalabs.com", "alessi")
    payload = api.get("/auth/me", headers=headers).json()

    assert payload["active_brand"] == "alessi"
    assert {brand["slug"] for brand in payload["brands"]} == {"alessi", "kahveji"}
    assert payload["features"]["import_files"] is True


def test_single_brand_user_sees_only_their_brand(api: TestClient, single_brand_user: str) -> None:
    """Tek markaya yetkili kullanıcı için diğer marka UI'da hiç var olmaz (spec §3A.3)."""
    headers = _login(api, single_brand_user)
    payload = api.get("/auth/me", headers=headers).json()

    assert [brand["slug"] for brand in payload["brands"]] == ["kahveji"]
    assert payload["is_holding_viewer"] is False


# --- workspace izolasyonu (spec §3A.6) --------------------------------------


def test_cross_brand_request_returns_404(api: TestClient, single_brand_user: str) -> None:
    """Kahveji token'ı ile Alessi kaynağına istek → 404 (403 değil)."""
    headers = _login(api, single_brand_user)

    assert api.get("/kahveji/products", headers=headers).status_code == 200
    assert api.get("/alessi/products", headers=headers).status_code == 404


def test_response_never_leaks_other_brand_records(api: TestClient) -> None:
    """Yanıtta karşı markaya ait hiçbir SKU/id bulunmaz (şema testi)."""
    headers = _login(api, "demo@mokkalabs.com", "kahveji")
    body = api.get("/kahveji/products", headers=headers, params={"limit": 200})
    assert body.status_code == 200

    skus = [product["sku"] for product in body.json()]
    assert skus, "demo veride Kahveji ürünü olmalı"
    assert all(sku.startswith("KHV-") for sku in skus)
    assert "ALS-" not in json.dumps(body.json())


def test_alerts_are_brand_scoped(api: TestClient) -> None:
    """Uyarı listesi de markaya kısıtlıdır."""
    alessi = api.get("/alessi/alerts", headers=_login(api, "demo@mokkalabs.com", "alessi")).json()
    kahveji = api.get(
        "/kahveji/alerts", headers=_login(api, "demo@mokkalabs.com", "kahveji")
    ).json()

    assert {alert["type"] for alert in alessi} & {"msrp_violation", "fx_exposure"}
    assert {alert["type"] for alert in kahveji} & {"negative_margin"}
    assert not {alert["id"] for alert in alessi} & {alert["id"] for alert in kahveji}


def test_switch_brand_changes_workspace(api: TestClient) -> None:
    """Workspace switcher: token değişir, veri karşı markaya geçer."""
    headers = _login(api, "demo@mokkalabs.com", "kahveji")
    response = api.post("/auth/switch-brand", json={"brand": "alessi"}, headers=headers)
    assert response.status_code == 200

    new_headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    skus = [product["sku"] for product in api.get("/alessi/products", headers=new_headers).json()]
    assert skus and all(sku.startswith("ALS-") for sku in skus)


def test_switch_to_unauthorized_brand_is_forbidden(api: TestClient, single_brand_user: str) -> None:
    """Yetkisiz workspace'e geçiş 403 döner."""
    headers = _login(api, single_brand_user)
    response = api.post("/auth/switch-brand", json={"brand": "alessi"}, headers=headers)
    assert response.status_code == 403


# --- feature bayrakları (spec §3A.4) ----------------------------------------


def test_disabled_feature_returns_404(api: TestClient) -> None:
    """Kahveji'de `import_files` kapalı → uç 404 (403 değil, modül sızdırılmaz)."""
    headers = _login(api, "demo@mokkalabs.com", "kahveji")
    assert api.get("/kahveji/import-files", headers=headers).status_code == 404


def test_enabled_feature_is_reachable(api: TestClient) -> None:
    """Alessi'de aynı modül açık → 200 ve dosya listesi döner."""
    headers = _login(api, "demo@mokkalabs.com", "alessi")
    response = api.get("/alessi/import-files", headers=headers)
    assert response.status_code == 200
    assert response.json()[0]["file_no"] == "ITH-2026-014"


# --- holding görünümü (spec §3A.3) ------------------------------------------


def test_holding_view_requires_permission(
    api: TestClient, db_session: Session, single_brand_user: str
) -> None:
    """Tek marka yetkili kullanıcının `/holding` isteği → 403 + audit kaydı."""
    headers = _login(api, single_brand_user)
    assert api.get("/holding/summary", headers=headers).status_code == 403

    with system_scope():
        denied = db_session.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(AuditLog.action == "holding_view_denied")
        )
    assert denied and denied >= 1


def test_holding_view_returns_all_brands_and_is_audited(
    api: TestClient, db_session: Session
) -> None:
    """Holding yetkisi olan kullanıcı markaları yan yana görür; erişim audit'e yazılır."""
    headers = _login(api, "demo@mokkalabs.com", "alessi")
    response = api.get("/holding/summary", headers=headers)
    assert response.status_code == 200

    payload = response.json()
    assert {row["brand"] for row in payload["brands"]} == {"alessi", "kahveji"}
    assert all(row["product_count"] > 0 for row in payload["brands"])

    with system_scope():
        granted = db_session.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(AuditLog.action == "holding_view_granted")
        )
    assert granted and granted >= 1


# --- dev-login yalnızca local/ci --------------------------------------------


def test_dev_login_hidden_outside_local(api: TestClient, monkeypatch: Any) -> None:
    """Üretim ortamında geliştirme girişi yoktur (404)."""
    from app.core.config import Settings, get_settings

    settings = get_settings()
    production = Settings(**{**settings.model_dump(), "environment": "production"})
    monkeypatch.setattr("app.api.auth.get_settings", lambda: production)

    response = api.post("/auth/dev-login", json={"email": "demo@mokkalabs.com"})
    assert response.status_code == 404


# --- ops.mokka SSO (spec §8) ------------------------------------------------


def _make_sso_token(email: str, secret: str, *, expires_in: int = 60) -> str:
    """ops.mokka'nın imzalayacağı türden bir SSO token'ı üretir."""
    import json
    import time

    from app.core.security import _b64url_encode, _sign

    header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    body = _b64url_encode(
        json.dumps({"email": email, "exp": int(time.time()) + expires_in}).encode()
    )
    return f"{header}.{body}.{_sign(f'{header}.{body}'.encode(), secret)}"


def _with_sso_secret(monkeypatch: Any, secret: str | None) -> None:
    from app.core.config import Settings, get_settings

    patched = Settings(**{**get_settings().model_dump(), "ops_sso_secret": secret})
    monkeypatch.setattr("app.api.auth.get_settings", lambda: patched)


def test_sso_exchange_issues_token(api: TestClient, monkeypatch: Any) -> None:
    """ops.mokka token'ı Kavun token'ına çevrilir ve workspace verisi açılır."""
    _with_sso_secret(monkeypatch, "ops-secret")

    response = api.post(
        "/auth/sso-exchange",
        json={"sso_token": _make_sso_token("demo@mokkalabs.com", "ops-secret"), "brand": "alessi"},
    )
    assert response.status_code == 200
    assert response.json()["active_brand"] == "alessi"

    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    assert api.get("/alessi/products", headers=headers).status_code == 200


def test_sso_exchange_rejects_foreign_signature(api: TestClient, monkeypatch: Any) -> None:
    """Başka bir secret'la imzalanmış SSO token'ı kabul edilmez."""
    _with_sso_secret(monkeypatch, "ops-secret")

    response = api.post(
        "/auth/sso-exchange",
        json={"sso_token": _make_sso_token("demo@mokkalabs.com", "sahte-secret")},
    )
    assert response.status_code == 401


def test_sso_exchange_rejects_unknown_user(api: TestClient, monkeypatch: Any) -> None:
    """Kavun'da karşılığı olmayan e-posta ile giriş yapılamaz."""
    _with_sso_secret(monkeypatch, "ops-secret")

    response = api.post(
        "/auth/sso-exchange",
        json={"sso_token": _make_sso_token("yabanci@example.com", "ops-secret")},
    )
    assert response.status_code == 401


def test_sso_exchange_unconfigured_returns_503(api: TestClient, monkeypatch: Any) -> None:
    """SSO secret'ı tanımlı değilse uç sessizce kimlik doğrulamaz, 503 döner."""
    _with_sso_secret(monkeypatch, None)

    response = api.post("/auth/sso-exchange", json={"sso_token": "x.y.z"})
    assert response.status_code == 503
