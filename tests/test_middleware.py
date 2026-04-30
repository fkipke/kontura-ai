"""Tests fuer Request-Id + Logging-Middleware."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from kontura.api.middleware import REQUEST_ID_HEADER


@pytest.mark.asyncio
async def test_request_id_is_added_to_response_header(client: AsyncClient) -> None:
    """Wenn Client KEINE Request-Id schickt, generiert Server eine."""
    response = await client.get("/health")
    assert response.status_code == 200
    assert REQUEST_ID_HEADER in response.headers
    # UUID4 hat 36 Zeichen mit Strichen.
    assert len(response.headers[REQUEST_ID_HEADER]) == 36


@pytest.mark.asyncio
async def test_request_id_from_client_is_preserved(client: AsyncClient) -> None:
    """Wenn Client eine Request-Id mitschickt, nutzt Server diese (Trace-Propagation)."""
    custom_id = "my-trace-id-1234"
    response = await client.get("/health", headers={REQUEST_ID_HEADER: custom_id})
    assert response.status_code == 200
    assert response.headers[REQUEST_ID_HEADER] == custom_id


@pytest.mark.asyncio
async def test_each_request_gets_unique_id(client: AsyncClient) -> None:
    """Zwei Requests ohne Client-Id bekommen verschiedene Server-Ids."""
    r1 = await client.get("/health")
    r2 = await client.get("/health")
    assert r1.headers[REQUEST_ID_HEADER] != r2.headers[REQUEST_ID_HEADER]
