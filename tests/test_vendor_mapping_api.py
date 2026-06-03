from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from kontura.api.vendor_mappings.normalize import normalize_vendor_name
from kontura.infra.models.vendor_account_mapping import VendorAccountMapping
from tests.conftest import auth_headers

TENANT_A_HEADERS = auth_headers("acme-corp")
TENANT_B_HEADERS = auth_headers("other-corp")


async def _insert_mapping(
    session: AsyncSession,
    *,
    tenant_id: str = "acme-corp",
    raw: str,
    account: int,
    usage_count: int = 1,
    last_used_at: datetime | None = None,
) -> VendorAccountMapping:
    mapping = VendorAccountMapping(
        tenant_id=tenant_id,
        vendor_name_normalized=normalize_vendor_name(raw),
        vendor_name_raw=raw,
        creditor_account_number=account,
        usage_count=usage_count,
        last_used_at=last_used_at or datetime.now(tz=UTC),
    )
    session.add(mapping)
    await session.commit()
    await session.refresh(mapping)
    return mapping


@pytest.mark.asyncio
async def test_get_suggest_returns_null_for_unknown_vendor(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/vendor-mappings/suggest?vendor_name=Unbekannt",
        headers=TENANT_A_HEADERS,
    )

    assert response.status_code == 200
    assert response.json() is None


@pytest.mark.asyncio
async def test_get_suggest_returns_mapping_after_record(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _insert_mapping(session, raw="ACME Lieferant GmbH", account=70042, usage_count=2)

    response = await client.get(
        "/api/v1/vendor-mappings/suggest?vendor_name=ACME Lieferant GmbH",
        headers=TENANT_A_HEADERS,
    )

    assert response.status_code == 200
    assert response.json()["creditor_account_number"] == 70042


@pytest.mark.asyncio
async def test_put_creates_new_mapping(client: AsyncClient) -> None:
    response = await client.put(
        "/api/v1/vendor-mappings",
        headers=TENANT_A_HEADERS,
        json={"vendor_name": "ACME Lieferant GmbH", "creditor_account_number": 70042},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["vendor_name_normalized"] == "acme lieferant"
    assert body["usage_count"] == 1


@pytest.mark.asyncio
async def test_put_updates_existing_mapping(client: AsyncClient, session: AsyncSession) -> None:
    await _insert_mapping(session, raw="ACME Lieferant GmbH", account=70042, usage_count=3)

    response = await client.put(
        "/api/v1/vendor-mappings",
        headers=TENANT_A_HEADERS,
        json={"vendor_name": "ACME Lieferant GmbH", "creditor_account_number": 70042},
    )

    assert response.status_code == 200
    assert response.json()["usage_count"] == 4


@pytest.mark.asyncio
async def test_get_list_paginated(client: AsyncClient, session: AsyncSession) -> None:
    await _insert_mapping(
        session,
        raw="Älterer Lieferant GmbH",
        account=70041,
        last_used_at=datetime.now(tz=UTC) - timedelta(days=1),
    )
    await _insert_mapping(session, raw="Neuer Lieferant GmbH", account=70042)

    response = await client.get(
        "/api/v1/vendor-mappings?limit=1&offset=0",
        headers=TENANT_A_HEADERS,
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["vendor_name_raw"] == "Neuer Lieferant GmbH"


@pytest.mark.asyncio
async def test_delete_removes_mapping(client: AsyncClient, session: AsyncSession) -> None:
    mapping = await _insert_mapping(session, raw="ACME Lieferant GmbH", account=70042)

    response = await client.delete(
        f"/api/v1/vendor-mappings/{mapping.id}",
        headers=TENANT_A_HEADERS,
    )

    assert response.status_code == 204


@pytest.mark.asyncio
async def test_tenant_isolation_on_all_endpoints(
    client: AsyncClient, session: AsyncSession
) -> None:
    mapping = await _insert_mapping(session, raw="ACME Lieferant GmbH", account=70042)

    suggest = await client.get(
        "/api/v1/vendor-mappings/suggest?vendor_name=ACME Lieferant GmbH",
        headers=TENANT_B_HEADERS,
    )
    listing = await client.get("/api/v1/vendor-mappings", headers=TENANT_B_HEADERS)
    delete = await client.delete(
        f"/api/v1/vendor-mappings/{mapping.id}",
        headers=TENANT_B_HEADERS,
    )

    assert suggest.status_code == 200
    assert suggest.json() is None
    assert listing.status_code == 200
    assert listing.json() == []
    assert delete.status_code == 404


@pytest.mark.asyncio
async def test_invalid_account_number_rejected_422(client: AsyncClient) -> None:
    response = await client.put(
        "/api/v1/vendor-mappings",
        headers=TENANT_A_HEADERS,
        json={"vendor_name": "ACME Lieferant GmbH", "creditor_account_number": 999},
    )

    assert response.status_code == 422
