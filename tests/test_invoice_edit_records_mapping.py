from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from kontura.infra.models.invoice import Invoice
from tests.conftest import auth_headers

TENANT_A_HEADERS = auth_headers("acme-corp")

BASE_INVOICE = {
    "invoice_number": "RE-G43-001",
    "vendor_name": "Testlieferant GmbH",
    "invoice_date": "2025-01-15",
    "total_amount": "119.00",
    "currency": "EUR",
}


async def _create_invoice(client: AsyncClient) -> dict[str, object]:
    response = await client.post("/invoices", json=BASE_INVOICE, headers=TENANT_A_HEADERS)
    assert response.status_code == 201, response.text
    return response.json()  # type: ignore[no-any-return]


@pytest.mark.asyncio
async def test_patch_with_creditor_account_records_mapping(
    client: AsyncClient, session: AsyncSession
) -> None:
    invoice = await _create_invoice(client)

    response = await client.patch(
        f"/invoices/{invoice['id']}",
        json={"expected_version": 1, "creditor_account_number": 70042},
        headers=TENANT_A_HEADERS,
    )

    assert response.status_code == 200, response.text
    result = await session.execute(
        text(
            "SELECT creditor_account_number, vendor_name_normalized "
            "FROM vendor_account_mappings WHERE tenant_id = 'acme-corp'"
        )
    )
    row = result.one()
    assert row[0] == 70042
    assert row[1] == "testlieferant"


@pytest.mark.asyncio
async def test_patch_without_creditor_account_no_mapping_change(
    client: AsyncClient, session: AsyncSession
) -> None:
    invoice = await _create_invoice(client)

    response = await client.patch(
        f"/invoices/{invoice['id']}",
        json={"expected_version": 1, "vendor_name": "Neuer Lieferant GmbH"},
        headers=TENANT_A_HEADERS,
    )

    assert response.status_code == 200, response.text
    result = await session.execute(text("SELECT COUNT(*) FROM vendor_account_mappings"))
    assert result.scalar_one() == 0


def test_creditor_account_field_does_not_appear_on_invoice_model() -> None:
    assert "creditor_account_number" not in Invoice.__table__.columns
