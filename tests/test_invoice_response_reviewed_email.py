"""Tests fuer Cluster 1.3: InvoiceResponse.reviewed_by_user_email."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from kontura.infra.models.invoice import Invoice, InvoiceStatus
from kontura.infra.models.user import User
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
    """Reviewer-User wurde geloescht → Invoice bleibt sichtbar, Email ist null."""
    ghost_user = User(
        id=uuid.uuid4(),
        tenant_id=TENANT_A,
        email="ghost-reviewer@example.com",
        password_hash="$2b$12$dummy.hash.for.tests.only.not.real.bcrypt",
        email_verified_at=datetime.now(tz=UTC),
    )
    session.add(ghost_user)
    await session.commit()

    inv = _make_invoice(TENANT_A, "RE-2024-GHOST")
    inv.is_reviewed = True
    inv.reviewed_at = datetime.now(tz=UTC)
    inv.reviewed_by_user_id = ghost_user.id
    session.add(inv)
    await session.commit()
    await session.refresh(inv)
    invoice_id = inv.id

    await session.delete(ghost_user)
    await session.commit()

    resp = await client.get(f"/invoices/{invoice_id}", headers=HEADERS_A)
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(invoice_id)
    assert body["reviewed_by_user_email"] is None
