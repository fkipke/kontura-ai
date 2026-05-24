"""Kontura AI - FastAPI Application Entrypoint."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from kontura import __version__
from kontura.ai.audit.audited_provider import AuditedAIProvider
from kontura.ai.factory import get_ai_provider
from kontura.api.auth import router as auth_router
from kontura.api.error_handlers import register_exception_handlers
from kontura.api.invoice_files import router as invoice_files_router
from kontura.api.invoices import router as invoices_router
from kontura.api.middleware import RequestContextMiddleware
from kontura.api.rate_limit import install_rate_limiter
from kontura.api.v1 import api_v1_router
from kontura.core.config import settings
from kontura.core.logging import configure_logging
from kontura.infra.db import dispose_engine
from kontura.middleware.security_headers import SecurityHeadersMiddleware

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
    # zuletzt registrierte Middleware laeuft als ERSTE (am naechsten am Request).
    #
    # Gewuenschte Execution-Reihenfolge (Request rein -> Response raus):
    #   1. CORS                 (Origin pruefen, Preflight beantworten)
    #   2. SecurityHeaders      (OWASP-Header auf Response setzen)
    #   3. RequestContext       (Request-Id, strukturiertes Logging)
    #   4. SlowAPI (Rate-Limit) (Limits checken)
    #   5. Endpoint
    #
    # Also Reihenfolge der add_middleware-Aufrufe: UMGEKEHRT = SlowAPI zuerst,
    # CORS zuletzt.
    install_rate_limiter(app)  # haengt SlowAPIMiddleware + 429-Handler an
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(SecurityHeadersMiddleware, enable_hsts=settings.enable_hsts)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=settings.cors_allow_credentials,
        # GET/POST/PUT/PATCH/DELETE/OPTIONS - alles was REST braucht.
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        # Wildcard fuer Header - sonst muss man jeden Custom-Header einzeln auflisten.
        allow_headers=["*"],
        # Welche Header darf das Frontend lesen? Request-Id ist nuetzlich fuers Debugging.
        expose_headers=["X-Request-Id", "X-Deduplicated", "X-Total-Count"],
        # Preflight-Cache: Browser muss OPTIONS-Request nicht jedes Mal wiederholen.
        max_age=600,
    )

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
    app.include_router(invoice_files_router, prefix="/api/v1")
    app.include_router(api_v1_router)

    return app


app = create_app()
