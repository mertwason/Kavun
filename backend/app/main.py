"""FastAPI uygulama fabrikası."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging

API_TITLE = "Kavun API"
API_DESCRIPTION = "Pazaryeri kârlılık ve mutabakat platformu"
API_VERSION = "0.1.0"


def create_app(settings: Settings | None = None) -> FastAPI:
    """Uygulamayı kurar. Test'ler bu fabrikayı kendi ayarlarıyla çağırabilir."""
    settings = settings or get_settings()
    configure_logging(settings.log_level, json_output=settings.environment != "local")

    app = FastAPI(
        title=API_TITLE,
        description=API_DESCRIPTION,
        version=API_VERSION,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    return app


app = create_app()
