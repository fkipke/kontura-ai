"""Tests fuer Cluster 2.1 + 2.2: list_filtered + GET /invoices/vendors."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from kontura.infra.models.invoice import Invoice, InvoiceStatus
from tests.conftest import auth_headers

TENANT_A = "acme-corp"
TENANT_B = "other-corp"
HEADERS_A = auth_headers(TENANT_A)
HEADERS_B = auth_headers(TENANT_B)


def _inv(
    tenant_id: str,
    *,
    invoice_number: str,
    vendor_name: str = "Test GmbH",
    total_amount: str = "100.00",
    invoice_date: date | None = None,
    status: InvoiceStatus = InvoiceStatus.RECEIVED,
    is_reviewed: bool = False,
) -> Invoice:
    return Invoice(
        tenant_id=tenant_id,
        invoice_number=invoice_number,
        vendor_name=vendor_name,
        invoice_date=invoice_date or date(2024, 6, 15),
        total_amount=Decimal(total_amount),
        currency="EUR",
        status=status,
        is_reviewed=is_reviewed,
    )


@pytest.mark.asyncio
async def test_list_no_filter_returns_all(client: AsyncClient, session: AsyncSession) -> None:
    """Ohne Filter alle Rechnungen des Tenants zurueck."""
    invoices = [
        _inv(TENANT_A, invoice_number="A1"),
        _inv(TENANT_A, invoice_number="A2"),
    ]
    session.add_all(invoices)
    await session.commit()

    resp = await client.get("/invoices", headers=HEADERS_A)
    assert resp.status_code == 200
    assert len(resp.json()) == 2
    assert resp.headers["x-total-count"] == "2"


@pytest.mark.asyncio
async def test_search_filter(client: AsyncClient, session: AsyncSession) -> None:
    """search filtert auf invoice_number und vendor_name."""
    session.add_all(
        [
            _inv(TENANT_A, invoice_number="FIND-ME", vendor_name="Telekom GmbH"),
            _inv(TENANT_A, invoice_number="IGNORE", vendor_name="Other Corp"),
        ]
    )
    await session.commit()

    resp = await client.get("/invoices?search=Telekom", headers=HEADERS_A)
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["vendor_name"] == "Telekom GmbH"


@pytest.mark.asyncio
async def test_status_filter(client: AsyncClient, session: AsyncSession) -> None:
    """status-Filter gibt nur passende Statuses zurueck."""
    session.add_all(
        [
            _inv(TENANT_A, invoice_number="R1", status=InvoiceStatus.RECEIVED),
            _inv(TENANT_A, invoice_number="B1", status=InvoiceStatus.BOOKED),
        ]
    )
    await session.commit()

    resp = await client.get("/invoices?status=received", headers=HEADERS_A)
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["status"] == "received"


@pytest.mark.asyncio
async def test_reviewed_filter_true(client: AsyncClient, session: AsyncSession) -> None:
    """reviewed=true liefert nur geprueft Rechnungen."""
    session.add_all(
        [
            _inv(TENANT_A, invoice_number="REV1", is_reviewed=True),
            _inv(TENANT_A, invoice_number="UNREV1", is_reviewed=False),
        ]
    )
    await session.commit()

    resp = await client.get("/invoices?reviewed=true", headers=HEADERS_A)
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1


@pytest.mark.asyncio
async def test_amount_range_filter(client: AsyncClient, session: AsyncSession) -> None:
    """amount_min/amount_max filtert inklusiv."""
    session.add_all(
        [
            _inv(TENANT_A, invoice_number="CHEAP", total_amount="50.00"),
            _inv(TENANT_A, invoice_number="MID", total_amount="500.00"),
            _inv(TENANT_A, invoice_number="EXPENSIVE", total_amount="5000.00"),
        ]
    )
    await session.commit()

    resp = await client.get("/invoices?amount_min=100&amount_max=1000", headers=HEADERS_A)
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["invoice_number"] == "MID"


@pytest.mark.asyncio
async def test_date_range_filter(client: AsyncClient, session: AsyncSession) -> None:
    """date_from/date_to filtert inklusiv."""
    session.add_all(
        [
            _inv(TENANT_A, invoice_number="JAN", invoice_date=date(2024, 1, 15)),
            _inv(TENANT_A, invoice_number="MAR", invoice_date=date(2024, 3, 15)),
            _inv(TENANT_A, invoice_number="DEC", invoice_date=date(2024, 12, 15)),
        ]
    )
    await session.commit()

    resp = await client.get(
        "/invoices?date_from=2024-02-01&date_to=2024-11-30",
        headers=HEADERS_A,
    )
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["invoice_number"] == "MAR"


@pytest.mark.asyncio
async def test_vendor_filter(client: AsyncClient, session: AsyncSession) -> None:
    """vendor-Filter gibt nur passende Lieferanten zurueck."""
    session.add_all(
        [
            _inv(TENANT_A, invoice_number="V1", vendor_name="Amazon AWS"),
            _inv(TENANT_A, invoice_number="V2", vendor_name="Telekom"),
        ]
    )
    await session.commit()

    resp = await client.get("/invoices?vendor=Amazon+AWS", headers=HEADERS_A)
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["vendor_name"] == "Amazon AWS"


@pytest.mark.asyncio
async def test_empty_result(client: AsyncClient, session: AsyncSession) -> None:
    """Kein Ergebnis → leeres Array mit X-Total-Count: 0."""
    resp = await client.get("/invoices?search=NOTEXISTS", headers=HEADERS_A)
    assert resp.status_code == 200
    assert resp.json() == []
    assert resp.headers["x-total-count"] == "0"


@pytest.mark.asyncio
async def test_tenant_isolation(client: AsyncClient, session: AsyncSession) -> None:
    """Tenant A sieht keine Rechnungen von Tenant B."""
    session.add(_inv(TENANT_B, invoice_number="B_ONLY"))
    await session.commit()

    resp = await client.get("/invoices", headers=HEADERS_A)
    assert resp.status_code == 200
    assert resp.json() == []
    assert resp.headers["x-total-count"] == "0"


@pytest.mark.asyncio
async def test_sort_by_total_amount_asc(client: AsyncClient, session: AsyncSession) -> None:
    """sort_by=total_amount&sort_order=asc sortiert aufsteigend."""
    session.add_all(
        [
            _inv(TENANT_A, invoice_number="BIGONE", total_amount="1000.00"),
            _inv(TENANT_A, invoice_number="SMALL", total_amount="10.00"),
        ]
    )
    await session.commit()

    resp = await client.get("/invoices?sort_by=total_amount&sort_order=asc", headers=HEADERS_A)
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 2
    assert items[0]["invoice_number"] == "SMALL"
    assert items[1]["invoice_number"] == "BIGONE"


@pytest.mark.asyncio
async def test_pagination(client: AsyncClient, session: AsyncSession) -> None:
    """limit/offset gibt korrekten Ausschnitt zurueck."""
    for i in range(15):
        session.add(_inv(TENANT_A, invoice_number=f"PAG-{i:02d}"))
    await session.commit()

    resp = await client.get(
        "/invoices?limit=5&offset=10&sort_by=invoice_number&sort_order=asc",
        headers=HEADERS_A,
    )
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 5
    assert resp.headers["x-total-count"] == "15"


@pytest.mark.asyncio
async def test_combination_filters(client: AsyncClient, session: AsyncSession) -> None:
    """Kombination aus status + amount_range + date_range."""
    session.add_all(
        [
            _inv(
                TENANT_A,
                invoice_number="MATCH",
                status=InvoiceStatus.RECEIVED,
                total_amount="500.00",
                invoice_date=date(2024, 6, 15),
            ),
            _inv(
                TENANT_A,
                invoice_number="WRONG_STATUS",
                status=InvoiceStatus.BOOKED,
                total_amount="500.00",
                invoice_date=date(2024, 6, 15),
            ),
            _inv(
                TENANT_A,
                invoice_number="WRONG_AMOUNT",
                status=InvoiceStatus.RECEIVED,
                total_amount="5000.00",
                invoice_date=date(2024, 6, 15),
            ),
        ]
    )
    await session.commit()

    resp = await client.get(
        "/invoices?status=received&amount_min=100&amount_max=1000&date_from=2024-01-01&date_to=2024-12-31",
        headers=HEADERS_A,
    )
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["invoice_number"] == "MATCH"


@pytest.mark.asyncio
async def test_vendors_endpoint_distinct_sorted(client: AsyncClient, session: AsyncSession) -> None:
    """GET /invoices/vendors gibt sortierte eindeutige Lieferantennamen zurueck."""
    session.add_all(
        [
            _inv(TENANT_A, invoice_number="V1", vendor_name="Zebra GmbH"),
            _inv(TENANT_A, invoice_number="V2", vendor_name="Apple Inc"),
            _inv(TENANT_A, invoice_number="V3", vendor_name="Zebra GmbH"),  # Duplikat
        ]
    )
    await session.commit()

    resp = await client.get("/invoices/vendors", headers=HEADERS_A)
    assert resp.status_code == 200
    vendors = resp.json()
    assert vendors == ["Apple Inc", "Zebra GmbH"]  # Sortiert, keine Duplikate


@pytest.mark.asyncio
async def test_vendors_endpoint_tenant_isolation(
    client: AsyncClient, session: AsyncSession
) -> None:
    """GET /invoices/vendors gibt keine Daten anderer Tenants zurueck."""
    session.add(_inv(TENANT_B, invoice_number="V_B1", vendor_name="Secret Vendor"))
    await session.commit()

    resp = await client.get("/invoices/vendors", headers=HEADERS_A)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_vendors_endpoint_no_nulls_or_empties(
    client: AsyncClient, session: AsyncSession
) -> None:
    """GET /invoices/vendors filtert NULL und leere Strings heraus."""
    session.add_all(
        [
            _inv(TENANT_A, invoice_number="VALID_V", vendor_name="Valid Corp"),
        ]
    )
    await session.commit()

    resp = await client.get("/invoices/vendors", headers=HEADERS_A)
    assert resp.status_code == 200
    vendors = resp.json()
    assert "" not in vendors
    assert None not in vendors
    assert "Valid Corp" in vendors
