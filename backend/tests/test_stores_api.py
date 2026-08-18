"""KVN-04: mağaza yönetimi ve credential kasası API'si (spec §3.6, §5.1, §8)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import deps
from app.core import crypto
from app.core.config import Settings, get_settings
from app.core.context import system_scope
from app.main import create_app
from app.models.enums import UserRole
from app.models.identity import Brand, Store, StoreCredential, User, UserBrandRole
from app.seeds.base import seed_base
from app.seeds.demo import seed_demo
from app.services import stores as store_service

TRENDYOL_SECRET = {
    "api_key": "TY-API-KEY-GIZLI",
    "api_secret": "TY-API-SECRET-COK-GIZLI",
    "seller_id": "998877",
}


@pytest.fixture
def vault(monkeypatch: Any) -> Iterator[str]:
    """Testler için gerçek bir şifreleme anahtarı."""
    key = crypto.generate_key()
    patched = Settings(**{**get_settings().model_dump(), "kavun_encryption_key": key})
    monkeypatch.setattr("app.core.crypto.get_settings", lambda: patched)
    yield key


@pytest.fixture
def api(db_session: Session, vault: str) -> Iterator[TestClient]:
    """Demo veriyle dolu API istemcisi."""
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
def admin(api: TestClient) -> dict[str, str]:
    """Kahveji workspace'inde admin oturumu."""
    return _login(api, "demo@mokkalabs.com", "kahveji")


@pytest.fixture
def viewer(db_session: Session, api: TestClient) -> dict[str, str]:
    """Kahveji'de yalnızca viewer yetkisi olan kullanıcı."""
    with system_scope():
        kahveji = db_session.scalar(select(Brand).where(Brand.slug == "kahveji"))
        assert kahveji is not None
        user = User(tenant_id=kahveji.tenant_id, email="viewer@mokkalabs.com", full_name="Viewer")
        db_session.add(user)
        db_session.flush()
        db_session.add(UserBrandRole(user_id=user.id, brand_id=kahveji.id, role=UserRole.VIEWER))
        db_session.flush()
    return _login(api, "viewer@mokkalabs.com")


def _first_store_id(api: TestClient, headers: dict[str, str], brand: str = "kahveji") -> str:
    stores = api.get(f"/{brand}/stores", headers=headers).json()
    assert stores, "demo veride mağaza olmalı"
    return str(stores[0]["id"])


# --- mağaza yönetimi --------------------------------------------------------


def test_store_list_is_brand_scoped(api: TestClient) -> None:
    """Her workspace yalnızca kendi mağazalarını görür (spec §3A.2)."""
    kahveji = api.get(
        "/kahveji/stores", headers=_login(api, "demo@mokkalabs.com", "kahveji")
    ).json()
    alessi = api.get("/alessi/stores", headers=_login(api, "demo@mokkalabs.com", "alessi")).json()

    assert [store["name"] for store in kahveji] == ["Kahveji — Trendyol"]
    assert sorted(store["name"] for store in alessi) == ["Alessi D2B", "Alessi — Trendyol"]
    assert not {store["id"] for store in kahveji} & {store["id"] for store in alessi}


def test_create_and_update_store(api: TestClient, admin: dict[str, str]) -> None:
    """Mağaza eklenir ve güncellenir."""
    created = api.post(
        "/kahveji/stores",
        headers=admin,
        json={"channel": "shopify", "name": "Kahveji — Shopify", "external_seller_id": "kahveji"},
    )
    assert created.status_code == 201
    assert created.json()["credentials"]["configured"] is False

    store_id = created.json()["id"]
    updated = api.patch(
        f"/kahveji/stores/{store_id}",
        headers=admin,
        json={"name": "Kahveji D2C", "is_active": False},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Kahveji D2C"
    assert updated.json()["is_active"] is False


def test_viewer_cannot_create_store(api: TestClient, viewer: dict[str, str]) -> None:
    """Viewer rolü yazma yapamaz (spec §3A.3)."""
    response = api.post(
        "/kahveji/stores", headers=viewer, json={"channel": "n11", "name": "Deneme"}
    )
    assert response.status_code == 403


def test_store_of_other_brand_is_not_found(api: TestClient, admin: dict[str, str]) -> None:
    """Karşı markanın mağazasına erişim 404 — id bilinse bile."""
    alessi_headers = _login(api, "demo@mokkalabs.com", "alessi")
    alessi_store_id = _first_store_id(api, alessi_headers, brand="alessi")

    response = api.get(f"/kahveji/stores/{alessi_store_id}/credentials", headers=admin)
    assert response.status_code == 404


# --- credential kasası ------------------------------------------------------


def test_credentials_are_stored_encrypted(
    api: TestClient, admin: dict[str, str], db_session: Session
) -> None:
    """Credential şifreli saklanır; DB'de düz metin bulunmaz (spec §3.6)."""
    store_id = _first_store_id(api, admin)

    response = api.post(
        f"/kahveji/stores/{store_id}/credentials", headers=admin, json={"values": TRENDYOL_SECRET}
    )
    assert response.status_code == 200
    assert response.json()["configured"] is True

    with system_scope():
        stored = db_session.scalar(
            select(StoreCredential).where(StoreCredential.store_id == store_id)
        )
    assert stored is not None
    assert b"TY-API-KEY-GIZLI" not in stored.encrypted_payload
    assert b"TY-API-SECRET-COK-GIZLI" not in stored.encrypted_payload


def test_credentials_never_appear_in_responses(api: TestClient, admin: dict[str, str]) -> None:
    """Hiçbir yanıt credential içeriğini döndürmez."""
    store_id = _first_store_id(api, admin)
    api.post(
        f"/kahveji/stores/{store_id}/credentials", headers=admin, json={"values": TRENDYOL_SECRET}
    )

    bodies = [
        api.get("/kahveji/stores", headers=admin).text,
        api.get(f"/kahveji/stores/{store_id}/credentials", headers=admin).text,
        api.post(
            f"/kahveji/stores/{store_id}/credentials",
            headers=admin,
            json={"values": TRENDYOL_SECRET},
        ).text,
    ]
    for body in bodies:
        for secret_value in TRENDYOL_SECRET.values():
            assert secret_value not in body


def test_credentials_can_be_decrypted_by_service(
    api: TestClient, admin: dict[str, str], db_session: Session
) -> None:
    """Connector katmanı (KVN-05) credential'ı çözebilir."""
    store_id = _first_store_id(api, admin)
    api.post(
        f"/kahveji/stores/{store_id}/credentials", headers=admin, json={"values": TRENDYOL_SECRET}
    )

    with system_scope():
        store = db_session.get(Store, store_id)
        assert store is not None
        assert store_service.load_credentials(db_session, store) == TRENDYOL_SECRET


def test_missing_required_fields_are_rejected(api: TestClient, admin: dict[str, str]) -> None:
    """Trendyol için api_key/api_secret/seller_id zorunlu (spec §4)."""
    store_id = _first_store_id(api, admin)

    response = api.post(
        f"/kahveji/stores/{store_id}/credentials",
        headers=admin,
        json={"values": {"api_key": "sadece-key"}},
    )
    assert response.status_code == 422
    assert "api_secret" in response.text


def test_blank_values_are_rejected(api: TestClient, admin: dict[str, str]) -> None:
    """Boş değerle credential kaydedilemez."""
    store_id = _first_store_id(api, admin)
    response = api.post(
        f"/kahveji/stores/{store_id}/credentials",
        headers=admin,
        json={"values": {**TRENDYOL_SECRET, "api_secret": "   "}},
    )
    assert response.status_code == 422


def test_viewer_cannot_write_credentials(api: TestClient, viewer: dict[str, str]) -> None:
    """Credential yazma yalnızca admin rolünde (spec §3A.3)."""
    store_id = _first_store_id(api, viewer)
    response = api.post(
        f"/kahveji/stores/{store_id}/credentials", headers=viewer, json={"values": TRENDYOL_SECRET}
    )
    assert response.status_code == 403


def test_credential_rotation_keeps_content(
    api: TestClient, admin: dict[str, str], db_session: Session
) -> None:
    """Rotasyon kaydı yeniden şifreler, içerik değişmez."""
    store_id = _first_store_id(api, admin)
    api.post(
        f"/kahveji/stores/{store_id}/credentials", headers=admin, json={"values": TRENDYOL_SECRET}
    )
    with system_scope():
        before = db_session.scalar(
            select(StoreCredential.encrypted_payload).where(StoreCredential.store_id == store_id)
        )

    response = api.post(f"/kahveji/stores/{store_id}/credentials/rotate", headers=admin)
    assert response.status_code == 200
    assert response.json()["rotated_at"] is not None

    with system_scope():
        after_record = db_session.scalar(
            select(StoreCredential).where(StoreCredential.store_id == store_id)
        )
        store = db_session.get(Store, store_id)
        assert after_record is not None and store is not None
        assert after_record.encrypted_payload != before
        assert store_service.load_credentials(db_session, store) == TRENDYOL_SECRET


def test_credentials_can_be_deleted(api: TestClient, admin: dict[str, str]) -> None:
    """Silme sonrası durum `configured: false` döner."""
    store_id = _first_store_id(api, admin)
    api.post(
        f"/kahveji/stores/{store_id}/credentials", headers=admin, json={"values": TRENDYOL_SECRET}
    )

    assert api.delete(f"/kahveji/stores/{store_id}/credentials", headers=admin).status_code == 204
    assert api.get(f"/kahveji/stores/{store_id}/credentials", headers=admin).json() == {
        "configured": False,
        "created_at": None,
        "rotated_at": None,
    }
    # İkinci silme 404.
    assert api.delete(f"/kahveji/stores/{store_id}/credentials", headers=admin).status_code == 404


def test_vault_unavailable_returns_503(
    api: TestClient, admin: dict[str, str], monkeypatch: Any
) -> None:
    """Anahtar yoksa credential yazılmaz — sessizce düz metin kaydedilmez."""
    store_id = _first_store_id(api, admin)
    monkeypatch.setattr("app.api.stores.crypto.is_available", lambda: False)

    response = api.post(
        f"/kahveji/stores/{store_id}/credentials", headers=admin, json={"values": TRENDYOL_SECRET}
    )
    assert response.status_code == 503
    assert "KAVUN_ENCRYPTION_KEY" in response.json()["detail"]


def test_credential_write_repr_hides_values() -> None:
    """Şema nesnesi log/exception içine düşse bile değerler görünmez."""
    from app.schemas.store import CredentialWrite

    payload = CredentialWrite(values=TRENDYOL_SECRET)
    assert "TY-API-KEY-GIZLI" not in repr(payload)
    assert "TY-API-KEY-GIZLI" not in str(payload)
    assert "api_key" in repr(payload)


def test_credential_values_never_reach_logs(
    api: TestClient, admin: dict[str, str], capsys: pytest.CaptureFixture[str]
) -> None:
    """Kaydetme akışı boyunca üretilen loglarda secret geçmez (CLAUDE.md §2)."""
    store_id = _first_store_id(api, admin)
    capsys.readouterr()

    api.post(
        f"/kahveji/stores/{store_id}/credentials", headers=admin, json={"values": TRENDYOL_SECRET}
    )
    output = capsys.readouterr()
    combined = output.out + output.err
    for secret_value in TRENDYOL_SECRET.values():
        assert secret_value not in combined
    assert json.dumps(TRENDYOL_SECRET) not in combined
