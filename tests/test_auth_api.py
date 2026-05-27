"""API-Tests fuer Auth: Register + Login."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

VALID_REGISTER_PAYLOAD = {
    "tenant_slug": "acme-corp",
    "tenant_display_name": "Acme Corporation",
    "email": "admin@acme.com",
    "password": "supersecret123",
    "full_name": "Admin User",
}


@pytest.mark.asyncio
async def test_register_creates_tenant_and_requires_email_verification(client: AsyncClient) -> None:
    response = await client.post("/api/v1/auth/register", json=VALID_REGISTER_PAYLOAD)
    assert response.status_code == 201
    body = response.json()
    assert body == {"email_verification_required": True}


@pytest.mark.asyncio
async def test_register_duplicate_tenant_returns_409(client: AsyncClient) -> None:
    r1 = await client.post("/api/v1/auth/register", json=VALID_REGISTER_PAYLOAD)
    assert r1.status_code == 201
    r2 = await client.post("/api/v1/auth/register", json=VALID_REGISTER_PAYLOAD)
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_register_invalid_slug_returns_422(client: AsyncClient) -> None:
    bad = {**VALID_REGISTER_PAYLOAD, "tenant_slug": "INVALID.SLUG"}
    response = await client.post("/api/v1/auth/register", json=bad)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_short_password_returns_422(client: AsyncClient) -> None:
    bad = {**VALID_REGISTER_PAYLOAD, "password": "short"}
    response = await client.post("/api/v1/auth/register", json=bad)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_with_wrong_password_returns_401(client: AsyncClient) -> None:
    await client.post("/api/v1/auth/register", json=VALID_REGISTER_PAYLOAD)
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "tenant_slug": "acme-corp",
            "email": "admin@acme.com",
            "password": "wrong-password",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_with_unknown_tenant_returns_401(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "tenant_slug": "does-not-exist",
            "email": "admin@acme.com",
            "password": "supersecret123",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_with_unknown_email_returns_401(client: AsyncClient) -> None:
    await client.post("/api/v1/auth/register", json=VALID_REGISTER_PAYLOAD)
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "tenant_slug": "acme-corp",
            "email": "nobody@acme.com",
            "password": "supersecret123",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_invalid_jwt_on_protected_endpoint_returns_401(client: AsyncClient) -> None:
    response = await client.get(
        "/invoices",
        headers={"Authorization": "Bearer invalid.jwt.token"},
    )
    assert response.status_code == 401
