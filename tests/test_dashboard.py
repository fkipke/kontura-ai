"""Tests fuer Cluster 3: Dashboard-Endpoints."""

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
    total_amount: str = "119.00",
    tax_amount: str | None = "19.00",
    invoice_date: date | None = None,
    is_reviewed: bool = False,
    status: InvoiceStatus = InvoiceStatus.RECEIVED,
) -> Invoice:
    inv = Invoice(
        tenant_id=tenant_id,
        invoice_number=invoice_number,
        vendor_name=vendor_name,
        invoice_date=invoice_date or date.today(),
        total_amount=Decimal(total_amount),
        tax_amount=Decimal(tax_amount) if tax_amount else None,
        currency="EUR",
        status=status,
        is_reviewed=is_reviewed,
    )
    return inv


# ========================== KPIs ==========================


@pytest.mark.asyncio
async def test_kpis_empty_tenant(client: AsyncClient) -> None:
    """Leerer Tenant liefert Status 200, keine Exception."""
    resp = await client.get("/api/v1/dashboard/kpis", headers=HEADERS_A)
    assert resp.status_code == 200
    body = resp.json()
    assert body["open_invoices_count"] == 0
    assert body["open_invoices_total_amount"] == "0"
    assert body["paid_this_month_total"] == "0"
    assert body["skonto_expiring_soon_count"] == 0
    assert body["vat_balance_current_quarter"] == "0"


@pytest.mark.asyncio
async def test_kpis_counts_open_invoices(client: AsyncClient, session: AsyncSession) -> None:
    """KPIs zaehlt offene Rechnungen korrekt."""
    session.add_all(
        [
            _inv(TENANT_A, invoice_number="OPEN1"),
            _inv(TENANT_A, invoice_number="BOOKED1", status=InvoiceStatus.BOOKED, is_reviewed=True),
        ]
    )
    await session.commit()

    resp = await client.get("/api/v1/dashboard/kpis", headers=HEADERS_A)
    assert resp.status_code == 200
    body = resp.json()
    # OPEN1 is neither BOOKED nor reviewed
    assert body["open_invoices_count"] >= 1


@pytest.mark.asyncio
async def test_kpis_tenant_isolation(client: AsyncClient, session: AsyncSession) -> None:
    """KPIs enthaelt keine Daten anderer Tenants."""
    session.add(_inv(TENANT_B, invoice_number="B_INVOICE"))
    await session.commit()

    resp = await client.get("/api/v1/dashboard/kpis", headers=HEADERS_A)
    assert resp.status_code == 200
    body = resp.json()
    assert body["open_invoices_count"] == 0


# ========================== Cashflow ==========================


@pytest.mark.asyncio
async def test_cashflow_empty_returns_zero_points(client: AsyncClient) -> None:
    """Leerer Tenant liefert Cashflow mit Null-Punkten."""
    resp = await client.get("/api/v1/dashboard/cashflow?months=3", headers=HEADERS_A)
    assert resp.status_code == 200
    body = resp.json()
    assert "points" in body
    assert len(body["points"]) == 3
    for pt in body["points"]:
        assert pt["total_amount"] == "0"
        assert pt["invoice_count"] == 0


@pytest.mark.asyncio
async def test_cashflow_month_format(client: AsyncClient) -> None:
    """Cashflow-Monatslabels haben Format YYYY-MM."""
    resp = await client.get("/api/v1/dashboard/cashflow?months=6", headers=HEADERS_A)
    assert resp.status_code == 200
    points = resp.json()["points"]
    assert len(points) == 6
    for pt in points:
        parts = pt["month"].split("-")
        assert len(parts) == 2
        assert len(parts[0]) == 4
        assert len(parts[1]) == 2


@pytest.mark.asyncio
async def test_cashflow_includes_seeded_data(client: AsyncClient, session: AsyncSession) -> None:
    """Cashflow-Punkte enthalten geseedete Daten des Tenants."""
    session.add(
        _inv(TENANT_A, invoice_number="CF1", invoice_date=date.today(), total_amount="500.00")
    )
    await session.commit()

    resp = await client.get("/api/v1/dashboard/cashflow?months=2", headers=HEADERS_A)
    assert resp.status_code == 200
    points = resp.json()["points"]
    # Current month should have data
    current_month = date.today().strftime("%Y-%m")
    current = next((p for p in points if p["month"] == current_month), None)
    assert current is not None
    assert Decimal(current["total_amount"]) == Decimal("500.00")


@pytest.mark.asyncio
async def test_cashflow_tenant_isolation(client: AsyncClient, session: AsyncSession) -> None:
    """Cashflow enthaelt keine Daten anderer Tenants."""
    session.add(_inv(TENANT_B, invoice_number="B_CF1", invoice_date=date.today()))
    await session.commit()

    resp = await client.get("/api/v1/dashboard/cashflow?months=1", headers=HEADERS_A)
    assert resp.status_code == 200
    points = resp.json()["points"]
    assert all(p["total_amount"] == "0" for p in points)


# ========================== Top Vendors ==========================


@pytest.mark.asyncio
async def test_top_vendors_empty(client: AsyncClient) -> None:
    """Leerer Tenant → leere Vendors-Liste."""
    resp = await client.get("/api/v1/dashboard/top-vendors", headers=HEADERS_A)
    assert resp.status_code == 200
    assert resp.json()["vendors"] == []


@pytest.mark.asyncio
async def test_top_vendors_ordered_by_amount(client: AsyncClient, session: AsyncSession) -> None:
    """Top-Vendors sind nach Gesamtbetrag absteigend sortiert."""
    session.add_all(
        [
            _inv(TENANT_A, invoice_number="V1", vendor_name="Small Corp", total_amount="10.00"),
            _inv(TENANT_A, invoice_number="V2", vendor_name="Big Corp", total_amount="9000.00"),
            _inv(TENANT_A, invoice_number="V3", vendor_name="Big Corp", total_amount="5000.00"),
        ]
    )
    await session.commit()

    resp = await client.get("/api/v1/dashboard/top-vendors?limit=2", headers=HEADERS_A)
    assert resp.status_code == 200
    vendors = resp.json()["vendors"]
    assert len(vendors) == 2
    assert vendors[0]["vendor_name"] == "Big Corp"
    assert Decimal(vendors[0]["total_amount"]) == Decimal("14000.00")


@pytest.mark.asyncio
async def test_top_vendors_tenant_isolation(client: AsyncClient, session: AsyncSession) -> None:
    """Top-Vendors enthaelt keine Daten anderer Tenants."""
    session.add(_inv(TENANT_B, invoice_number="B_V1", vendor_name="B Vendor"))
    await session.commit()

    resp = await client.get("/api/v1/dashboard/top-vendors", headers=HEADERS_A)
    assert resp.status_code == 200
    assert resp.json()["vendors"] == []


# ========================== Recent Activity ==========================


@pytest.mark.asyncio
async def test_recent_activity_empty(client: AsyncClient) -> None:
    """Leerer Tenant → leere Liste."""
    resp = await client.get("/api/v1/dashboard/recent-activity", headers=HEADERS_A)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_recent_activity_ordered_by_updated_at(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Recent-Activity gibt Rechnungen nach updated_at DESC zurueck."""
    invs = [_inv(TENANT_A, invoice_number=f"RA-{i}") for i in range(5)]
    session.add_all(invs)
    await session.commit()

    resp = await client.get("/api/v1/dashboard/recent-activity?limit=3", headers=HEADERS_A)
    assert resp.status_code == 200
    assert len(resp.json()) == 3


@pytest.mark.asyncio
async def test_recent_activity_tenant_isolation(client: AsyncClient, session: AsyncSession) -> None:
    """Recent-Activity enthaelt keine Daten anderer Tenants."""
    session.add(_inv(TENANT_B, invoice_number="B_RA1"))
    await session.commit()

    resp = await client.get("/api/v1/dashboard/recent-activity", headers=HEADERS_A)
    assert resp.status_code == 200
    assert resp.json() == []


# ========================== Alerts ==========================


@pytest.mark.asyncio
async def test_alerts_empty_tenant(client: AsyncClient) -> None:
    """Leerer Tenant → keine Alerts."""
    resp = await client.get("/api/v1/dashboard/alerts", headers=HEADERS_A)
    assert resp.status_code == 200
    assert resp.json() == {"alerts": []}


@pytest.mark.asyncio
async def test_alerts_potential_duplicate(client: AsyncClient, session: AsyncSession) -> None:
    """Doppelbuchung (gleiche Nr/Vendor/Betrag, unterschiedl. Datum) → danger Alert."""
    session.add_all(
        [
            _inv(
                TENANT_A,
                invoice_number="DUP-001",
                vendor_name="Dup GmbH",
                total_amount="100.00",
                invoice_date=date(2024, 1, 1),
            ),
            _inv(
                TENANT_A,
                invoice_number="DUP-001",
                vendor_name="Dup GmbH",
                total_amount="100.00",
                invoice_date=date(2024, 2, 1),
            ),
        ]
    )
    await session.commit()

    resp = await client.get("/api/v1/dashboard/alerts", headers=HEADERS_A)
    assert resp.status_code == 200
    alerts = resp.json()["alerts"]
    dup_alerts = [a for a in alerts if a["type"] == "potential_duplicate"]
    assert len(dup_alerts) >= 1
    assert dup_alerts[0]["severity"] == "danger"


@pytest.mark.asyncio
async def test_alerts_tenant_isolation(client: AsyncClient, session: AsyncSession) -> None:
    """Alerts enthaelt keine Daten anderer Tenants."""
    # Create duplicate for tenant B
    session.add_all(
        [
            _inv(
                TENANT_B,
                invoice_number="B-DUP",
                vendor_name="B Vendor",
                total_amount="999.00",
                invoice_date=date(2024, 1, 1),
            ),
            _inv(
                TENANT_B,
                invoice_number="B-DUP",
                vendor_name="B Vendor",
                total_amount="999.00",
                invoice_date=date(2024, 2, 1),
            ),
        ]
    )
    await session.commit()

    resp = await client.get("/api/v1/dashboard/alerts", headers=HEADERS_A)
    assert resp.status_code == 200
    assert resp.json() == {"alerts": []}
