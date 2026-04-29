"""Integration-Tests fuer die Invoice-API (mit JWT-Tenant-Isolation).

Die kritischen Tests beweisen:
- Ohne JWT -> 401
- Tenant B sieht NIEMALS Daten von Tenant A
- Doppelte Rechnungsnummer im selben Tenant -> 409 (K4)
- Gleiche Rechnungsnummer in DIFFERENT Tenants -> erlaubt
"""

import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers

INVOICE_PAYLOAD = {
    "invoice_number": "RE-2026-001",
    "vendor_name": "Musterlieferant GmbH",
    "invoice_date": "2026-04-25",
    "total_amount": "1234.56",
    "currency": "EUR",
}

TENANT_A_HEADERS = auth_headers("acme-corp")
TENANT_B_HEADERS = auth_headers("other-corp")


# --- Standard CRUD-Tests (mit Tenant) ---


@pytest.mark.asyncio
async def test_create_invoice_returns_201_and_persists(client: AsyncClient) -> None:
    response = await client.post("/invoices", json=INVOICE_PAYLOAD, headers=TENANT_A_HEADERS)
    assert response.status_code == 201
    body = response.json()
    assert body["invoice_number"] == INVOICE_PAYLOAD["invoice_number"]
    assert body["vendor_name"] == INVOICE_PAYLOAD["vendor_name"]
    assert body["currency"] == "EUR"
    assert body["status"] == "received"
    assert "id" in body


@pytest.mark.asyncio
async def test_list_invoices_returns_created_invoice(client: AsyncClient) -> None:
    await client.post("/invoices", json=INVOICE_PAYLOAD, headers=TENANT_A_HEADERS)
    response = await client.get("/invoices", headers=TENANT_A_HEADERS)
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert items[0]["invoice_number"] == INVOICE_PAYLOAD["invoice_number"]


@pytest.mark.asyncio
async def test_get_invoice_by_id_returns_200(client: AsyncClient) -> None:
    create_resp = await client.post("/invoices", json=INVOICE_PAYLOAD, headers=TENANT_A_HEADERS)
    invoice_id = create_resp.json()["id"]
    response = await client.get(f"/invoices/{invoice_id}", headers=TENANT_A_HEADERS)
    assert response.status_code == 200
    assert response.json()["id"] == invoice_id


@pytest.mark.asyncio
async def test_get_invoice_unknown_id_returns_404(client: AsyncClient) -> None:
    response = await client.get(
        "/invoices/00000000-0000-0000-0000-000000000000", headers=TENANT_A_HEADERS
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_invoice_with_negative_amount_returns_422(client: AsyncClient) -> None:
    bad_payload = {**INVOICE_PAYLOAD, "total_amount": "-50.00"}
    response = await client.post("/invoices", json=bad_payload, headers=TENANT_A_HEADERS)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_invoices_respects_limit(client: AsyncClient) -> None:
    for i in range(3):
        await client.post(
            "/invoices",
            json={**INVOICE_PAYLOAD, "invoice_number": f"RE-2026-00{i}"},
            headers=TENANT_A_HEADERS,
        )
    response = await client.get("/invoices?limit=1", headers=TENANT_A_HEADERS)
    assert response.status_code == 200
    assert len(response.json()) == 1


# --- Auth-Tests (kein JWT / falsches JWT) ---


@pytest.mark.asyncio
async def test_create_invoice_without_jwt_returns_401(client: AsyncClient) -> None:
    response = await client.post("/invoices", json=INVOICE_PAYLOAD)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_invoices_without_jwt_returns_401(client: AsyncClient) -> None:
    response = await client.get("/invoices")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_invalid_jwt_returns_401(client: AsyncClient) -> None:
    response = await client.get("/invoices", headers={"Authorization": "Bearer not-a-real-jwt"})
    assert response.status_code == 401


# --- Tenant-Isolation-Tests (KRITISCH) ---


@pytest.mark.asyncio
async def test_tenant_b_cannot_see_tenant_a_invoices_in_list(client: AsyncClient) -> None:
    """KRITISCH: Tenant B darf NIEMALS Rechnungen von A sehen."""
    await client.post("/invoices", json=INVOICE_PAYLOAD, headers=TENANT_A_HEADERS)
    response = await client.get("/invoices", headers=TENANT_B_HEADERS)
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_tenant_b_cannot_get_tenant_a_invoice_by_id(client: AsyncClient) -> None:
    """KRITISCH: Tenant B darf nicht via UUID auf Daten von A zugreifen -> 404."""
    create_resp = await client.post("/invoices", json=INVOICE_PAYLOAD, headers=TENANT_A_HEADERS)
    invoice_id = create_resp.json()["id"]
    response = await client.get(f"/invoices/{invoice_id}", headers=TENANT_B_HEADERS)
    assert response.status_code == 404


# --- K4: Unique-Constraint-Tests ---


@pytest.mark.asyncio
async def test_duplicate_invoice_number_same_tenant_returns_409(client: AsyncClient) -> None:
    """K4: Doppelte invoice_number im selben Tenant -> 409 Conflict."""
    r1 = await client.post("/invoices", json=INVOICE_PAYLOAD, headers=TENANT_A_HEADERS)
    assert r1.status_code == 201
    r2 = await client.post("/invoices", json=INVOICE_PAYLOAD, headers=TENANT_A_HEADERS)
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_same_invoice_number_different_tenants_allowed(client: AsyncClient) -> None:
    """Gleiche invoice_number in verschiedenen Tenants ist erlaubt."""
    r1 = await client.post("/invoices", json=INVOICE_PAYLOAD, headers=TENANT_A_HEADERS)
    r2 = await client.post("/invoices", json=INVOICE_PAYLOAD, headers=TENANT_B_HEADERS)
    assert r1.status_code == 201
    assert r2.status_code == 201
