"""Kontura AI — FastAPI Application Entrypoint."""

import structlog
from fastapi import FastAPI

from kontura import __version__
from kontura.core.config import settings

logger = structlog.get_logger(__name__)


def create_app() -> FastAPI:
    """Application Factory: Erzeugt und konfiguriert die FastAPI-App."""
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description="KI-gestützte Rechnungsverarbeitung und Auto-Buchung für SAP FI und DATEV.",
    )

    @app.get("/health", tags=["System"])
    async def health() -> dict[str, str]:
        """Health-Check-Endpoint für Monitoring und Load-Balancer."""
        return {
            "status": "ok",
            "service": settings.app_name,
            "version": __version__,
            "environment": settings.app_env,
        }

    logger.info(
        "application_started",
        app=settings.app_name,
        version=__version__,
        env=settings.app_env,
    )
    return app


app = create_app()
