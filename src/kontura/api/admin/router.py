"""Admin-Router: Admin-Endpoints (Demo-Reset, ...)."""

from __future__ import annotations

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from kontura.admin.demo_seed import seed_demo_tenant
from kontura.api.dependencies import SettingsDep
from kontura.infra.db import get_session

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.post(
    "/reset-demo",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Setzt den Demo-Tenant zurueck und befuellt ihn neu (nur im Demo-Modus)",
    responses={
        204: {"description": "Demo-Tenant erfolgreich zurueckgesetzt"},
        403: {"description": "Demo-Modus ist deaktiviert"},
    },
)
async def reset_demo(
    app_settings: SettingsDep,
    session: SessionDep,
) -> None:
    """Loescht alle Demo-Daten und legt 50 neue Mock-Rechnungen an.

    Nur aktiv wenn KONTURA_DEMO_MODE=true — gibt sonst 403 zurueck.
    """
    if not app_settings.demo_mode:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo mode ist deaktiviert.",
        )
    await seed_demo_tenant(session, tenant_id=app_settings.demo_tenant_id, settings=app_settings)
    await session.commit()
    logger.info("admin.reset_demo.complete", tenant_id=app_settings.demo_tenant_id)
