"""Idempotentes Seed-Skript fuer den Demo-Tenant.

Usage:
    uv run python scripts/seed_demo_tenant.py
"""

import asyncio

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kontura.admin.demo_seed import seed_demo_tenant
from kontura.core.config import get_settings
from kontura.infra.db import engine

logger = structlog.get_logger(__name__)


def get_async_session_maker() -> async_sessionmaker[AsyncSession]:
    """Erzeugt eine Session-Factory fuer die konfigurierte Datenbank."""
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def main() -> None:
    settings = get_settings()
    session_maker = get_async_session_maker()
    async with session_maker() as session:
        async with session.begin():
            await seed_demo_tenant(session, tenant_id=settings.demo_tenant_id, settings=settings)
    logger.info("seed.complete", tenant_id=settings.demo_tenant_id)


if __name__ == "__main__":
    asyncio.run(main())
