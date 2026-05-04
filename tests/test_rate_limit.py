"""Tests fuer Rate-Limiting (slowapi).

Wir aktivieren das Limit pro Test gezielt - ueberschreibt die globale
RATE_LIMIT_ENABLED=false Default-Einstellung aus conftest.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from kontura.api.rate_limit import limiter
from kontura.main import app


@pytest_asyncio.fixture
async def rate_limited_client() -> AsyncGenerator[AsyncClient, None]:
    """Client mit aktiviertem Rate-Limit + sauberem Storage pro Test."""
    limiter.reset()
    limiter.enabled = True
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    limiter.enabled = False
    limiter.reset()


@pytest.mark.asyncio
async def test_login_blocks_after_too_many_attempts(
    rate_limited_client: AsyncClient,
) -> None:
    """11. Login-Versuch in 1 Minute -> 429 Too Many Requests."""
    payload = {
        "tenant_slug": "acme-corp",
        "email": "nobody@acme.com",
        "password": "wrong-password",
    }
    # Default: 10/minute fuer Login.
    last_status = None
    got_429 = False
    for _ in range(15):
        resp = await rate_limited_client.post("/api/v1/auth/login", json=payload)
        last_status = resp.status_code
        if resp.status_code == 429:
            got_429 = True
            break

    assert got_429, f"Erwartete 429 nach 10 Versuchen, bekam {last_status}"


@pytest.mark.asyncio
async def test_429_response_has_problem_details_and_retry_after(
    rate_limited_client: AsyncClient,
) -> None:
    """429-Response: RFC9457-Body + Retry-After Header."""
    payload = {
        "tenant_slug": "acme-corp",
        "email": "nobody@acme.com",
        "password": "wrong-password",
    }
    response = None
    for _ in range(15):
        response = await rate_limited_client.post("/api/v1/auth/login", json=payload)
        if response.status_code == 429:
            break

    assert response is not None and response.status_code == 429
    body = response.json()
    assert body["status"] == 429
    assert body["title"] == "Too Many Requests"
    assert "request_id" in body
    assert "Retry-After" in response.headers


@pytest.mark.asyncio
async def test_health_endpoint_is_not_rate_limited(
    rate_limited_client: AsyncClient,
) -> None:
    """KRITISCH: /health darf NIE rate-limited sein - sonst sperrt sich der LB selbst aus."""
    for _ in range(50):
        resp = await rate_limited_client.get("/health")
        assert resp.status_code == 200, f"Health geblockt nach {_} Calls!"
