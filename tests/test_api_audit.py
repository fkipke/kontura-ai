"""API-Tests fuer den Audit-Endpoint (GET /api/v1/audit/llm-calls).

Wir nutzen einen monkeypatched AuditRepository - so muessen wir keinen
echten LLM-Call ausloesen, koennen aber trotzdem Tenant-Isolation,
Pagination und Filterung verifizieren.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import AsyncGenerator, Sequence
from typing import cast
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from kontura.ai.audit.repository import AuditRepository
from kontura.api.v1.dependencies import get_audit_repository
from kontura.core.tenant import TenantContext
from kontura.infra.models import LLMAuditEntry
from kontura.main import app
from tests.conftest import auth_headers

TENANT_A_HEADERS = auth_headers("tenant-a")
TENANT_B_HEADERS = auth_headers("tenant-b")


def _make_entry(tenant_id: str, *, success: bool = True) -> LLMAuditEntry:
    e = LLMAuditEntry(
        tenant_id=tenant_id,
        provider_name="fake",
        operation="embed",
        model="fake-model",
        prompt_text="hello [IBAN_1]",
        prompt_chars=20,
        response_chars=1536,
        duration_ms=42,
        success=success,
        error_message=None if success else "boom",
    )
    e.id = uuid4()
    e.created_at = dt.datetime.now(dt.UTC)
    e.updated_at = dt.datetime.now(dt.UTC)
    return e


class _FakeAuditRepository:
    def __init__(self, entries: Sequence[LLMAuditEntry]) -> None:
        self._entries = list(entries)

    async def list_for_tenant(
        self, tenant: TenantContext, limit: int = 50, offset: int = 0
    ) -> Sequence[LLMAuditEntry]:
        if limit < 1:
            raise ValueError("limit muss >= 1 sein")
        if offset < 0:
            raise ValueError("offset muss >= 0 sein")
        filtered = [e for e in self._entries if e.tenant_id == tenant.tenant_id]
        filtered.sort(key=lambda e: e.created_at, reverse=True)
        return filtered[offset : offset + limit]


@pytest_asyncio.fixture
async def audit_client() -> AsyncGenerator[AsyncClient, None]:
    entries = [
        _make_entry("tenant-a", success=True),
        _make_entry("tenant-a", success=False),
        _make_entry("tenant-b", success=True),
    ]
    fake_repo = _FakeAuditRepository(entries)

    def _override_audit_repo() -> AuditRepository:
        return cast(AuditRepository, fake_repo)

    app.dependency_overrides[get_audit_repository] = _override_audit_repo
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


# ---------- Auth ----------


@pytest.mark.asyncio
async def test_audit_endpoint_without_jwt_returns_401(audit_client: AsyncClient) -> None:
    response = await audit_client.get("/api/v1/audit/llm-calls")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_audit_endpoint_with_invalid_jwt_returns_401(audit_client: AsyncClient) -> None:
    response = await audit_client.get(
        "/api/v1/audit/llm-calls",
        headers={"Authorization": "Bearer not-a-real-jwt"},
    )
    assert response.status_code == 401


# ---------- Functional ----------


@pytest.mark.asyncio
async def test_audit_endpoint_returns_entries_for_tenant(audit_client: AsyncClient) -> None:
    response = await audit_client.get("/api/v1/audit/llm-calls", headers=TENANT_A_HEADERS)
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 2
    assert len(body["results"]) == 2
    first = body["results"][0]
    assert "id" in first
    assert first["provider_name"] == "fake"
    assert first["operation"] == "embed"
    assert "prompt_text" in first


# ---------- Tenant-Isolation (KRITISCH) ----------


@pytest.mark.asyncio
async def test_audit_endpoint_does_not_leak_other_tenants(audit_client: AsyncClient) -> None:
    response = await audit_client.get("/api/v1/audit/llm-calls", headers=TENANT_A_HEADERS)
    assert response.status_code == 200
    assert response.json()["count"] == 2


@pytest.mark.asyncio
async def test_audit_endpoint_tenant_b_sees_only_own(audit_client: AsyncClient) -> None:
    response = await audit_client.get("/api/v1/audit/llm-calls", headers=TENANT_B_HEADERS)
    assert response.status_code == 200
    assert response.json()["count"] == 1


# ---------- Pagination ----------


@pytest.mark.asyncio
async def test_audit_endpoint_respects_limit(audit_client: AsyncClient) -> None:
    response = await audit_client.get("/api/v1/audit/llm-calls?limit=1", headers=TENANT_A_HEADERS)
    assert response.status_code == 200
    assert response.json()["count"] == 1


@pytest.mark.asyncio
async def test_audit_endpoint_invalid_limit_returns_422(audit_client: AsyncClient) -> None:
    response = await audit_client.get("/api/v1/audit/llm-calls?limit=0", headers=TENANT_A_HEADERS)
    assert response.status_code == 422
