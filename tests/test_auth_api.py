"""API-Tests fuer Auth: Register + Login.

Wir testen:
- Register legt Tenant + User an, gibt JWT zurueck.
- Login mit korrekten Credentials -> 200 + JWT.
- Login mit falschem Passwort -> 401.
- Doppel-Register -> 409.
- Validation: Schwache Passwoerter, ungueltige Slugs.
"""

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


# ---------- Register ----------


@pytest.mark.asyncio
async def test_register_creates_tenant_and_returns_jwt(client: AsyncClient) -> None:
    response = await client.post("/api/v1/auth/register", json=VALID_REGISTER_PAYLOAD)
    assert response.status_code == 201
    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert body["expires_in_seconds"] > 0
    # Token ist kein leerer String und enthaelt 2 Punkte (header.payload.sig)
    assert body["access_token"].count(".") == 2


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


# ---------- Login ----------


@pytest.mark.asyncio
async def test_login_with_correct_credentials_returns_jwt(client: AsyncClient) -> None:
    await client.post("/api/v1/auth/register", json=VALID_REGISTER_PAYLOAD)
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "tenant_slug": "acme-corp",
            "email": "admin@acme.com",
            "password": "supersecret123",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body


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


# ---------- End-to-End: JWT auf geschuetztem Endpoint ----------


@pytest.mark.asyncio
async def test_jwt_from_register_works_on_protected_endpoint(client: AsyncClient) -> None:
    """KRITISCH: Token aus /auth/register laesst sich an /invoices nutzen."""
    register_resp = await client.post("/api/v1/auth/register", json=VALID_REGISTER_PAYLOAD)
    token = register_resp.json()["access_token"]

    response = await client.get("/invoices", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_invalid_jwt_on_protected_endpoint_returns_401(client: AsyncClient) -> None:
    """Gefaelschtes Token darf nicht durchkommen."""
    response = await client.get(
        "/invoices",
        headers={"Authorization": "Bearer this-is-not-a-real-jwt"},
    )
    assert response.status_code == 401
