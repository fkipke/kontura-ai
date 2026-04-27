"""Pytest-Fixtures fuer Kontura AI.

Senior-Setup:
- Eigene Test-DB ('kontura_test'), damit Tests NIE Production-Daten zerstoeren.
- Engine ist function-scoped: jeder Test bekommt einen frischen Event-Loop +
  eine frische Engine. Vermeidet asyncpg-"another operation in progress"-Errors.
- Schema wird vor jedem Test angelegt und nach jedem Test wieder geloescht.
- Dependency-Override leitet die App-Session auf die Test-Session um.
"""

import os
from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

import kontura.infra.models  # noqa: F401  # registriert ALLE Modelle bei Base.metadata
from kontura.infra.db import Base, get_session
from kontura.main import app

# Test-DB-URL: nutzt TEST_DATABASE_URL falls gesetzt (CI), sonst eigene Test-DB
# 'kontura_test'. So koennen Tests die DB risikolos droppen/recreaten,
# ohne die lokale Dev-DB ('kontura') zu zerstoeren.
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://kontura:dev_local_password@localhost:5433/kontura_test",
)


@pytest_asyncio.fixture
async def engine() -> AsyncGenerator[AsyncEngine, None]:
    """Erzeugt eine Test-Engine pro Test (Event-Loop-sicher).

    Die NullPool-Strategie verhindert, dass Connections ueber Event-Loop-Grenzen
    hinweg wiederverwendet werden - das ist der haeufigste asyncpg-Stolperstein.
    """
    eng = create_async_engine(TEST_DATABASE_URL, echo=False, future=True, poolclass=None)
    async with eng.begin() as conn:
        # pgvector-Extension aktivieren (idempotent)
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield eng
    finally:
        async with eng.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await eng.dispose()


@pytest_asyncio.fixture
async def session(engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Eine AsyncSession pro Test."""
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        yield s


@pytest_asyncio.fixture
async def client(session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """HTTP-Client gegen die App, mit get_session-Dependency-Override."""

    async def _override_get_session() -> AsyncGenerator[AsyncSession, None]:
        yield session

    app.dependency_overrides[get_session] = _override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
