"""Sağlık ve hazır olma uçları — compose healthcheck ve CI smoke testi kullanır."""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.core.config import get_settings
from app.core.db import check_database

router = APIRouter(tags=["system"])


@router.get("/healthz", summary="Servis ayakta mı")
def healthz() -> dict[str, str]:
    """Bağımlılıklara bakmaz; yalnızca sürecin yaşadığını söyler."""
    settings = get_settings()
    return {"status": "ok", "app": settings.app_name, "environment": settings.environment}


@router.get("/readyz", summary="Bağımlılıklar hazır mı")
def readyz(response: Response) -> dict[str, object]:
    """DB erişilebilir değilse 503 döner (compose/CI bekleme mantığı buna bakar)."""
    database = check_database()
    ready = bool(database["ok"])
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ready" if ready else "degraded", "checks": {"database": database}}
