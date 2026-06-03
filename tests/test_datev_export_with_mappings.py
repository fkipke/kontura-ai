"""Zusatztests fuer DATEV-Export mit Vendor-Mappings."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from kontura.api.vendor_mappings.normalize import normalize_vendor_name
from kontura.core.config import settings
from kontura.infra.models.vendor_account_mapping import VendorAccountMapping
from tests.conftest import auth_headers
from tests.test_datev_export import _make_invoice, _rows_from_response

TENANT_A_HEADERS = auth_headers("acme-corp")


async def _insert_mapping(
    session: AsyncSession,
    *,
    raw: str,
    account: int,
    usage_count: int,
) -> None:
    session.add(
        VendorAccountMapping(
            tenant_id="acme-corp",
            vendor_name_normalized=normalize_vendor_name(raw),
            vendor_name_raw=raw,
            creditor_account_number=account,
            usage_count=usage_count,
            last_used_at=datetime.now(tz=UTC),
        )
    )
    await session.commit()


@pytest.mark.asyncio
async def test_export_uses_default_account_when_no_mapping(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _make_invoice(session, vendor_name="Ohne Mapping GmbH")

    response = await client.get(
        "/api/v1/exports/datev?from=2026-01-01&to=2026-03-31",
        headers=TENANT_A_HEADERS,
    )

    assert _rows_from_response(response.content)[2][7] == str(
        settings.datev_default_creditor_account
    )


@pytest.mark.asyncio
async def test_export_uses_mapped_account_when_auto_apply(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _make_invoice(session, vendor_name="ACME Lieferant GmbH")
    await _insert_mapping(session, raw="ACME Lieferant GmbH", account=70042, usage_count=5)

    response = await client.get(
        "/api/v1/exports/datev?from=2026-01-01&to=2026-03-31",
        headers=TENANT_A_HEADERS,
    )

    assert _rows_from_response(response.content)[2][7] == "70042"


@pytest.mark.asyncio
async def test_export_uses_default_when_low_confidence(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _make_invoice(session, vendor_name="ACME Lieferant GmbH")
    await _insert_mapping(session, raw="ACME Lieferant GmbH", account=70042, usage_count=1)

    response = await client.get(
        "/api/v1/exports/datev?from=2026-01-01&to=2026-03-31",
        headers=TENANT_A_HEADERS,
    )

    assert _rows_from_response(response.content)[2][7] == "70000"


@pytest.mark.asyncio
async def test_export_fuzzy_match_does_not_auto_apply(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _make_invoice(session, vendor_name="Acmee")
    await _insert_mapping(session, raw="ACME GmbH", account=70042, usage_count=5)

    response = await client.get(
        "/api/v1/exports/datev?from=2026-01-01&to=2026-03-31",
        headers=TENANT_A_HEADERS,
    )

    assert _rows_from_response(response.content)[2][7] == "70000"


@pytest.mark.asyncio
async def test_multiple_invoices_different_vendors_different_accounts(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _make_invoice(
        session,
        invoice_number="RE-2026-001",
        vendor_name="ACME Lieferant GmbH",
        total_amount=Decimal("119.00"),
        invoice_date=date(2026, 3, 1),
    )
    await _make_invoice(
        session,
        invoice_number="RE-2026-002",
        vendor_name="Beta Lieferant GmbH",
        total_amount=Decimal("238.00"),
        invoice_date=date(2026, 3, 2),
    )
    await _insert_mapping(session, raw="ACME Lieferant GmbH", account=70042, usage_count=5)
    await _insert_mapping(session, raw="Beta Lieferant GmbH", account=70043, usage_count=5)

    response = await client.get(
        "/api/v1/exports/datev?from=2026-01-01&to=2026-03-31",
        headers=TENANT_A_HEADERS,
    )

    rows = _rows_from_response(response.content)
    assert rows[2][7] == "70042"
    assert rows[3][7] == "70043"
