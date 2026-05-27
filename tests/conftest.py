"""Pytest-Fixtures fuer Kontura AI.

Senior-Setup:
- Eigene Test-DB ('kontura_test'), damit Tests NIE Production-Daten zerstoeren.
- Engine ist function-scoped: jeder Test bekommt einen frischen Event-Loop +
  eine frische Engine. Vermeidet asyncpg-"another operation in progress"-Errors.
- Schema wird vor jedem Test angelegt und nach jedem Test wieder geloescht.
- Dependency-Override leitet die App-Session auf die Test-Session um.
- auth_headers(): Helper fuer Tests, die einen JWT brauchen.
- FakeAIProvider: Stub fuer AI-Tests ohne echten OpenAI-Aufruf.
"""

import os
import uuid

# Rate-Limiting in Tests AUS - sonst kommen sich Tests gegenseitig ins Gehege.
# Spezifische Rate-Limit-Tests (test_rate_limit.py) aktivieren das Limit gezielt
# via direktem limiter.enabled-Toggle.
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

import pathlib
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pytest
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
from kontura.ai.base import ChatMessage
from kontura.ai.factory import get_ai_provider
from kontura.api.dependencies import get_email_sender, get_file_storage
from kontura.core.jwt import encode_token
from kontura.infra.db import Base, get_session
from kontura.infra.models.user import User
from kontura.infra.storage import LocalFilesystemStorage
from kontura.main import app

# Test-DB-URL: nutzt TEST_DATABASE_URL falls gesetzt (CI), sonst eigene Test-DB
# 'kontura_test'. So koennen Tests die DB risikolos droppen/recreaten,
# ohne die lokale Dev-DB ('kontura') zu zerstoeren.
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://kontura:dev_local_password@localhost:5433/kontura_test",
)

TEST_USER_IDS_BY_TENANT = {
    "acme-corp": "11111111-1111-1111-1111-111111111111",
    "other-corp": "22222222-2222-2222-2222-222222222222",
}

# Gueltiges Extraction-Ergebnis fuer FakeAIProvider (als Default-Rueckgabe)
VALID_EXTRACTION_RESULT: dict[str, Any] = {
    "invoice_number": "RE-2024-001",
    "vendor_name": "Test GmbH",
    "vendor_address": "Teststrasse 1, 12345 Berlin",
    "invoice_date": "2024-01-15",
    "due_date": "2024-02-15",
    "currency": "EUR",
    "net_amount": "100.00",
    "tax_amount": "19.00",
    "total_amount": "119.00",
    "line_items": [],
    "confidence_notes": None,
}


@dataclass
class SentEmail:
    to: str
    subject: str
    body_text: str
    body_html: str | None


class FakeEmailSender:
    """Sammelt versendete E-Mails fuer Assertions in Tests."""

    def __init__(self) -> None:
        self.sent_emails: list[SentEmail] = []

    async def send(
        self,
        to: str,
        subject: str,
        body_text: str,
        body_html: str | None = None,
    ) -> None:
        self.sent_emails.append(
            SentEmail(to=to, subject=subject, body_text=body_text, body_html=body_html)
        )


class FakeAIProvider:
    """Stub-Implementation des AIProvider-Protocols fuer Tests.

    Kein echter API-Aufruf - liefert konfigurierbare Ergebnisse.
    extract_call_count erlaubt Pruefung ob LLM aufgerufen wurde.
    """

    name = "fake"
    embedding_dimension = 8

    def __init__(self) -> None:
        self.extraction_return_value: dict[str, Any] | Exception = dict(VALID_EXTRACTION_RESULT)
        self.extract_call_count = 0

    async def embed(self, text: str) -> list[float]:  # noqa: ARG002
        return [0.0] * self.embedding_dimension

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> str:
        return "Fake LLM response"

    async def extract_structured(
        self,
        *,
        system_prompt: str,  # noqa: ARG002
        user_text: str | None,  # noqa: ARG002
        image_bytes_list: list[bytes],  # noqa: ARG002
        json_schema: dict[str, Any],  # noqa: ARG002
        model: str | None = None,  # noqa: ARG002
        temperature: float = 0.0,  # noqa: ARG002
    ) -> tuple[dict[str, Any], int, int]:
        self.extract_call_count += 1
        if isinstance(self.extraction_return_value, Exception):
            raise self.extraction_return_value
        return dict(self.extraction_return_value), 100, 200


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
async def test_user(session: AsyncSession) -> None:
    """Legt stabile Test-User fuer JWT-Sub/FK-Tests an."""
    session.add_all(
        [
            User(
                id=uuid.UUID(TEST_USER_IDS_BY_TENANT["acme-corp"]),
                tenant_id="acme-corp",
                email="test@example.com",
                password_hash="$2b$12$dummy.hash.for.tests.only.not.real.bcrypt",
                email_verified_at=datetime.now(tz=UTC),
            ),
            User(
                id=uuid.UUID(TEST_USER_IDS_BY_TENANT["other-corp"]),
                tenant_id="other-corp",
                email="other@example.com",
                password_hash="$2b$12$dummy.hash.for.tests.only.not.real.bcrypt",
                email_verified_at=datetime.now(tz=UTC),
            ),
        ]
    )
    await session.commit()


@pytest.fixture
def fake_ai_provider() -> FakeAIProvider:
    """Frische FakeAIProvider-Instanz pro Test."""
    return FakeAIProvider()


@pytest.fixture
def fake_email_sender() -> FakeEmailSender:
    return FakeEmailSender()


@pytest_asyncio.fixture
async def client(
    session: AsyncSession,
    tmp_path: pathlib.Path,
    test_user: None,  # noqa: ARG001
    fake_ai_provider: FakeAIProvider,
    fake_email_sender: FakeEmailSender,
) -> AsyncGenerator[AsyncClient, None]:
    """HTTP-Client gegen die App, mit Dependency-Overrides fuer Session und FileStorage.

    tmp_path stellt sicher, dass jeder Test sein eigenes isoliertes Datei-Verzeichnis
    bekommt - keine Datei-Leaks zwischen Tests.
    G2.1: get_ai_provider wird auf FakeAIProvider umgeleitet (kein echter API-Call).
    """

    async def _override_get_session() -> AsyncGenerator[AsyncSession, None]:
        yield session

    def _override_get_file_storage() -> LocalFilesystemStorage:
        return LocalFilesystemStorage(base_dir=str(tmp_path / "invoice-files"))

    def _override_get_ai_provider() -> FakeAIProvider:
        return fake_ai_provider

    def _override_get_email_sender() -> FakeEmailSender:
        return fake_email_sender

    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[get_file_storage] = _override_get_file_storage
    app.dependency_overrides[get_ai_provider] = _override_get_ai_provider
    app.dependency_overrides[get_email_sender] = _override_get_email_sender
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


def auth_headers(tenant_id: str = "acme-corp", *, user_id: str | None = None) -> dict[str, str]:
    """Erzeugt einen Authorization-Header mit gueltigem JWT.

    Tests, die einen Tenant brauchen, nutzen das hier statt 'X-Tenant-Id'.
    """
    effective_user_id = user_id or TEST_USER_IDS_BY_TENANT.get(
        tenant_id, TEST_USER_IDS_BY_TENANT["acme-corp"]
    )
    token = encode_token(sub=effective_user_id, tenant_id=tenant_id, email="test@example.com")
    return {"Authorization": f"Bearer {token}"}
