"""Tests fuer Cluster 1.3: InvoiceResponse.reviewed_by_user_email."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from kontura.infra.models.invoice import Invoice, InvoiceStatus
from tests.conftest import TEST_USER_IDS_BY_TENANT, auth_headers

TENANT_A = "acme-corp"
TENANT_B = "other-corp"
HEADERS_A = auth_headers(TENANT_A)
HEADERS_B = auth_headers(TENANT_B)


def _make_invoice(tenant_id: str, invoice_number: str = "RE-2024-001") -> Invoice:
    return Invoice(
        tenant_id=tenant_id,
        invoice_number=invoice_number,
        vendor_name="Test GmbH",
        invoice_date=datetime.now(tz=UTC).date(),
        total_amount=Decimal("119.00"),
        currency="EUR",
        status=InvoiceStatus.RECEIVED,
    )


@pytest.mark.asyncio
async def test_unreviewed_invoice_has_null_email(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Nicht-geprueft → reviewed_by_user_email ist null."""
    inv = _make_invoice(TENANT_A)
    session.add(inv)
    await session.commit()
    await session.refresh(inv)

    resp = await client.get(f"/invoices/{inv.id}", headers=HEADERS_A)
    assert resp.status_code == 200
    body = resp.json()
    assert body["reviewed_by_user_email"] is None


@pytest.mark.asyncio
async def test_reviewed_invoice_has_user_email(client: AsyncClient, session: AsyncSession) -> None:
    """Geprueft → reviewed_by_user_email ist die Email des Pruefenden."""
    user_id = uuid.UUID(TEST_USER_IDS_BY_TENANT[TENANT_A])
    inv = _make_invoice(TENANT_A, "RE-2024-REVIEWED")
    inv.is_reviewed = True
    inv.reviewed_at = datetime.now(tz=UTC)
    inv.reviewed_by_user_id = user_id
    session.add(inv)
    await session.commit()
    await session.refresh(inv)

    resp = await client.get(f"/invoices/{inv.id}", headers=HEADERS_A)
    assert resp.status_code == 200
    body = resp.json()
    assert body["reviewed_by_user_email"] == "test@example.com"


@pytest.mark.asyncio
async def test_reviewed_but_user_deleted_returns_null_email(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Reviewer-User wurde geloescht → LEFT JOIN liefert null, Invoice ist noch sichtbar."""
    missing_user_id = uuid.uuid4()  # User existiert nicht
    inv = _make_invoice(TENANT_A, "RE-2024-GHOST")
    inv.is_reviewed = True
    inv.reviewed_at = datetime.now(tz=UTC)
    inv.reviewed_by_user_id = missing_user_id
    session.add(inv)
    await session.commit()
    await session.refresh(inv)

    resp = await client.get(f"/invoices/{inv.id}", headers=HEADERS_A)
    assert resp.status_code == 200
    body = resp.json()
    # Invoice noch da, Email aber null wegen fehlenden Users (LEFT JOIN)
    assert body["id"] == str(inv.id)
    assert body["reviewed_by_user_email"] is None
