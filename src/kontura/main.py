"""Kontura AI - FastAPI Application Entrypoint."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from kontura import __version__
from kontura.api.invoices import router as invoices_router
from kontura.core.config import settings
from kontura.infra.db import dispose_engine

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan-Hook: Startup- und Shutdown-Logik."""
    logger.info(
        "application_started",
        app=settings.app_name,
        version=__version__,
        env=settings.app_env,
    )
    yield
    logger.info("application_shutting_down")
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

    @app.get("/health", tags=["System"])
    async def health() -> dict[str, str]:
        """Health-Check-Endpoint fuer Monitoring und Load-Balancer."""
        return {
            "status": "ok",
            "service": settings.app_name,
            "version": __version__,
            "environment": settings.app_env,
        }

    # Domain-Router registrieren
    app.include_router(invoices_router)

    return app


app = create_app()
