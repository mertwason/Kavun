"""FastAPI uygulama fabrikası."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import analytics, auth, health, holding, stores, workspace
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging, get_logger
from app.core.scoping import BrandScopeViolation

log = get_logger("api")


async def _brand_scope_violation_handler(_: Request, exc: Exception) -> JSONResponse:
    """İzolasyon ihlali kullanıcı hatası değil, kod hatasıdır: 500 döner ve loglanır.

    İstemciye tablo adı gibi iç detay sızdırılmaz.
    """
    log.error("brand_scope.violation", error=str(exc))
    return JSONResponse(status_code=500, content={"detail": "Sunucu hatası"})


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
    app.add_exception_handler(BrandScopeViolation, _brand_scope_violation_handler)

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(holding.router)
    # Workspace router'ı en sonda: `/{brand_slug}` yakalayıcı olduğundan sabit
    # yollar (auth, holding, healthz) ondan önce eşleşmelidir.
    app.include_router(stores.router)
    app.include_router(analytics.router)
    app.include_router(workspace.router)
    return app


app = create_app()
