"""KVN-01: iskelet ayakta mı — sağlık uçları ve OpenAPI şeması."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from app.api import health


def test_healthz_returns_ok(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_openapi_schema_is_served(client: TestClient) -> None:
    """Frontend tipleri bu şemadan üretilir (CLAUDE.md §4) — kırılmamalı."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "Kavun API"
    assert "/healthz" in schema["paths"]


def test_readyz_reports_degraded_when_database_unreachable(
    client: TestClient, monkeypatch: Any
) -> None:
    monkeypatch.setattr(
        health, "check_database", lambda: {"ok": False, "error": "OperationalError"}
    )
    response = client.get("/readyz")
    assert response.status_code == 503
    assert response.json()["status"] == "degraded"


def test_readyz_reports_ready_when_database_reachable(client: TestClient, monkeypatch: Any) -> None:
    monkeypatch.setattr(health, "check_database", lambda: {"ok": True})
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "checks": {"database": {"ok": True}}}
