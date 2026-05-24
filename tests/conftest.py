"""Pytest-Fixtures fuer Kontura AI.

Senior-Setup:
- Eigene Test-DB ('kontura_test'), damit Tests NIE Production-Daten zerstoeren.
- Engine ist function-scoped: jeder Test bekommt einen frischen Event-Loop +
  eine frische Engine. Vermeidet asyncpg-"another operation in progress"-Errors.
- Schema wird vor jedem Test angelegt und nach jedem Test wieder geloescht.
- Dependency-Override leitet die App-Session auf die Test-Session um.
- auth_headers(): Helper fuer Tests, die einen JWT brauchen.
"""

import os

# Rate-Limiting in Tests AUS - sonst kommen sich Tests gegenseitig ins Gehege.
# Spezifische Rate-Limit-Tests (test_rate_limit.py) aktivieren das Limit gezielt
# via direktem limiter.enabled-Toggle.
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

import pathlib
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
from sqlalchemy.pool import NullPool

import kontura.infra.models  # noqa: F401  # registriert ALLE Modelle bei Base.metadata
from kontura.api.dependencies import get_file_storage
from kontura.core.jwt import encode_token
from kontura.infra.db import Base, get_session
from kontura.infra.storage import LocalFilesystemStorage
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

    H1-Fix: poolclass=NullPool (NICHT None!). NullPool oeffnet pro Anfrage
    eine frische Connection und schliesst sie sofort wieder - so koennen keine
    Connections ueber Event-Loop-Grenzen hinweg wiederverwendet werden.
    """
    eng = create_async_engine(TEST_DATABASE_URL, echo=False, future=True, poolclass=NullPool)
    async with eng.begin() as conn:
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
async def client(
    session: AsyncSession, tmp_path: pathlib.Path
) -> AsyncGenerator[AsyncClient, None]:
    """HTTP-Client gegen die App, mit Dependency-Overrides fuer Session und FileStorage.

    tmp_path stellt sicher, dass jeder Test sein eigenes isoliertes Datei-Verzeichnis
    bekommt - keine Datei-Leaks zwischen Tests.
    """

    async def _override_get_session() -> AsyncGenerator[AsyncSession, None]:
        yield session

    def _override_get_file_storage() -> LocalFilesystemStorage:
        return LocalFilesystemStorage(base_dir=str(tmp_path / "invoice-files"))

    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[get_file_storage] = _override_get_file_storage
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


def auth_headers(tenant_id: str = "acme-corp", *, user_id: str = "test-user-id") -> dict[str, str]:
    """Erzeugt einen Authorization-Header mit gueltigem JWT.

    Tests, die einen Tenant brauchen, nutzen das hier statt 'X-Tenant-Id'.
    """
    token = encode_token(sub=user_id, tenant_id=tenant_id, email="test@example.com")
    return {"Authorization": f"Bearer {token}"}
