"""Kontura AI - FastAPI Application Entrypoint."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from kontura import __version__
from kontura.ai.audit.audited_provider import AuditedAIProvider
from kontura.ai.factory import get_ai_provider
from kontura.api.auth import router as auth_router
from kontura.api.error_handlers import register_exception_handlers
from kontura.api.invoices import router as invoices_router
from kontura.api.middleware import RequestContextMiddleware
from kontura.api.rate_limit import install_rate_limiter
from kontura.api.v1 import api_v1_router
from kontura.core.config import settings
from kontura.core.logging import configure_logging
from kontura.infra.db import dispose_engine

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan-Hook: Startup- und Shutdown-Logik."""
    configure_logging()
    logger.info(
        "application_started",
        app=settings.app_name,
        version=__version__,
        env=settings.app_env,
    )
    yield
    logger.info("application_shutting_down")

    provider = get_ai_provider()
    if isinstance(provider, AuditedAIProvider):
        await provider.audit_repo.dispose()
        logger.info("audit_repository_disposed")

    await dispose_engine()
    logger.info("application_stopped")


def create_app() -> FastAPI:
    """Application Factory: Erzeugt und konfiguriert die FastAPI-App."""
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description="KI-gestuetzte Rechnungsverarbeitung und Auto-Buchung fuer SAP FI und DATEV.",
        lifespan=lifespan,
    )

    # WICHTIG: Reihenfolge der Middleware
    # ====================================
    # add_middleware registriert in UMGEKEHRTER Reihenfolge -
    # zuletzt registrierte Middleware laeuft als ERSTE.
    #
    # Wir wollen:
    #   1. RequestContextMiddleware (Request-Id setzen, Logging)
    #   2. SlowAPIMiddleware (Rate-Limiting checken)
    #   3. Endpoint
    #
    # Also Reihenfolge der add_middleware-Aufrufe: erst SlowAPI, dann Context.
    install_rate_limiter(app)  # haengt SlowAPIMiddleware + 429-Handler an
    app.add_middleware(RequestContextMiddleware)

    # Zentrale Exception-Handler (RFC9457 Problem Details)
    register_exception_handlers(app)

    @app.get("/health", tags=["System"])
    async def health() -> dict[str, str]:
        """Health-Check-Endpoint fuer Monitoring und Load-Balancer."""
        return {
            "status": "ok",
            "version": __version__,
            "environment": settings.app_env,
        }

    # Domain-Router registrieren
    app.include_router(auth_router)
    app.include_router(invoices_router)
    app.include_router(api_v1_router)

    return app


app = create_app()
