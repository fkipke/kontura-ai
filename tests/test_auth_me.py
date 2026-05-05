"""Tests fuer GET /api/v1/auth/me und POST /api/v1/auth/logout.

Senior-Test-Pattern:
- Wir testen das End-to-End-Verhalten via TestClient
- Fuer /me brauchen wir einen echten JWT - den holen wir uns durch
  einen vorgeschalteten Login-Call (oder direkt encode_token).
- Wir testen die wichtigen Pfade:
    1. Happy-Path: gueltiger JWT -> 200 + korrekte Felder
    2. Auth-Path: kein Header -> 401
    3. Auth-Path: ungueltiger JWT -> 401
"""

from __future__ import annotations

import datetime as dt

import pytest
from fastapi import status
from httpx import AsyncClient

from kontura.core.jwt import encode_token


@pytest.mark.asyncio
async def test_me_with_valid_jwt_returns_user_info(client: AsyncClient) -> None:
    """Happy-Path: gueltiger JWT -> /me liefert die Felder aus dem Token."""
    token = encode_token(
        sub="00000000-0000-0000-0000-000000000001",
        tenant_id="acme-corp",
        email="alice@acme.example",
    )

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["user_id"] == "00000000-0000-0000-0000-000000000001"
    assert body["tenant_id"] == "acme-corp"
    assert body["email"] == "alice@acme.example"
    # Expiry sollte in der Zukunft liegen (Token gerade erst erzeugt).
    assert body["token_expires_at"] > int(dt.datetime.now(dt.UTC).timestamp())


@pytest.mark.asyncio
async def test_me_without_authorization_header_returns_401(client: AsyncClient) -> None:
    """Auth-Path: kein Authorization-Header -> 401."""
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_me_with_invalid_token_returns_401(client: AsyncClient) -> None:
    """Auth-Path: gefaelschter / kaputter JWT -> 401."""
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer this-is-not-a-valid-jwt"},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_logout_with_valid_jwt_returns_204(client: AsyncClient) -> None:
    """Logout: korrekter JWT -> 204 No Content."""
    token = encode_token(
        sub="00000000-0000-0000-0000-000000000001",
        tenant_id="acme-corp",
        email="alice@acme.example",
    )

    response = await client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == status.HTTP_204_NO_CONTENT
    # 204 darf kein Response-Body haben.
    assert response.content == b""


@pytest.mark.asyncio
async def test_logout_without_authorization_returns_401(client: AsyncClient) -> None:
    """Logout: ohne Token -> 401 (nicht 204).

    Begruendung: ein nicht-eingeloggter Client hat nichts zum Auslogggen,
    und wir wollen API-Konsistenz mit anderen geschuetzten Endpoints.
    """
    response = await client.post("/api/v1/auth/logout")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
