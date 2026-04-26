"""Integration-Tests fuer die Invoice-API.

Diese Tests laufen gegen eine echte PostgreSQL-DB.
Lokal: localhost:5433. CI: GitHub-Actions-Service-Container.
"""

import pytest
from httpx import AsyncClient

INVOICE_PAYLOAD = {
    "invoice_number": "RE-2026-001",
    "vendor_name": "Musterlieferant GmbH",
    "invoice_date": "2026-04-25",
    "total_amount": "1234.56",
    "currency": "EUR",
}


@pytest.mark.asyncio
async def test_create_invoice_returns_201_and_persists(client: AsyncClient) -> None:
    """POST /invoices legt eine Rechnung an und liefert sie als InvoiceRead zurueck."""
    response = await client.post("/invoices", json=INVOICE_PAYLOAD)

    assert response.status_code == 201
    body = response.json()
    assert body["invoice_number"] == INVOICE_PAYLOAD["invoice_number"]
    assert body["vendor_name"] == INVOICE_PAYLOAD["vendor_name"]
    assert body["currency"] == "EUR"
    assert body["status"] == "received"
    assert "id" in body
    assert "created_at" in body
    assert "updated_at" in body


@pytest.mark.asyncio
async def test_list_invoices_returns_created_invoice(client: AsyncClient) -> None:
    """GET /invoices liefert die zuvor erstellte Rechnung."""
    await client.post("/invoices", json=INVOICE_PAYLOAD)

    response = await client.get("/invoices")
    assert response.status_code == 200
    items = response.json()
    assert isinstance(items, list)
    assert len(items) == 1
    assert items[0]["invoice_number"] == INVOICE_PAYLOAD["invoice_number"]


@pytest.mark.asyncio
async def test_get_invoice_by_id_returns_200(client: AsyncClient) -> None:
    """GET /invoices/{id} liefert die Rechnung mit der passenden ID."""
    create_resp = await client.post("/invoices", json=INVOICE_PAYLOAD)
    invoice_id = create_resp.json()["id"]

    response = await client.get(f"/invoices/{invoice_id}")
    assert response.status_code == 200
    assert response.json()["id"] == invoice_id


@pytest.mark.asyncio
async def test_get_invoice_unknown_id_returns_404(client: AsyncClient) -> None:
    """GET /invoices/{id} mit unbekannter ID -> 404."""
    response = await client.get("/invoices/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_invoice_with_negative_amount_returns_422(client: AsyncClient) -> None:
    """Pydantic-Validation: negative Betraege werden abgewiesen."""
    bad_payload = {**INVOICE_PAYLOAD, "total_amount": "-50.00"}
    response = await client.post("/invoices", json=bad_payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_invoices_respects_limit(client: AsyncClient) -> None:
    """GET /invoices?limit=1 liefert hoechstens 1 Eintrag."""
    for i in range(3):
        await client.post(
            "/invoices",
            json={**INVOICE_PAYLOAD, "invoice_number": f"RE-2026-00{i}"},
        )

    response = await client.get("/invoices?limit=1")
    assert response.status_code == 200
    assert len(response.json()) == 1
