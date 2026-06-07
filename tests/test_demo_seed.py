"""Tests fuer Cluster 5: Demo-Seed-Skript Idempotenz + Verteilung."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from kontura.admin.demo_seed import seed_demo_tenant
from kontura.core.config import Settings
from kontura.infra.models.invoice import Invoice
from kontura.infra.models.invoice_file import ExtractionStatus, InvoiceFile
from kontura.infra.models.user import User


def _demo_settings() -> Settings:
    return Settings(
        jwt_secret="ci-test-secret-do-not-use-in-production-please",
        demo_mode=True,
        demo_tenant_id="demo-tenant",
        demo_user_email="demo@kontura.ai",
        demo_user_password="demo",
    )


DEMO_TENANT = "demo-tenant"


@pytest.mark.asyncio
async def test_seed_creates_50_invoices(session: AsyncSession) -> None:
    """seed_demo_tenant legt 50 Rechnungen an."""
    await seed_demo_tenant(session, tenant_id=DEMO_TENANT, settings=_demo_settings())
    await session.commit()

    count = (
        await session.execute(
            select(func.count(Invoice.id)).where(Invoice.tenant_id == DEMO_TENANT)
        )
    ).scalar_one()
    assert count == 50


@pytest.mark.asyncio
async def test_seed_creates_demo_user(session: AsyncSession) -> None:
    """seed_demo_tenant erstellt den Demo-User."""
    settings = _demo_settings()
    await seed_demo_tenant(session, tenant_id=DEMO_TENANT, settings=settings)
    await session.commit()

    user = (
        await session.execute(
            select(User).where(
                User.tenant_id == DEMO_TENANT,
                User.email == settings.demo_user_email,
            )
        )
    ).scalar_one_or_none()
    assert user is not None


@pytest.mark.asyncio
async def test_seed_is_idempotent(session: AsyncSession) -> None:
    """Zweifaches Seeding loescht und legt neu an — exakt 50 Rechnungen, keine Duplikate."""
    settings = _demo_settings()
    await seed_demo_tenant(session, tenant_id=DEMO_TENANT, settings=settings)
    await session.commit()

    # Zweites Seeding
    await seed_demo_tenant(session, tenant_id=DEMO_TENANT, settings=settings)
    await session.commit()

    count = (
        await session.execute(
            select(func.count(Invoice.id)).where(Invoice.tenant_id == DEMO_TENANT)
        )
    ).scalar_one()
    assert count == 50  # Kein Akkumulieren von Daten


@pytest.mark.asyncio
async def test_seed_reviewed_ratio(session: AsyncSession) -> None:
    """Ungefaehr 20-40% der Rechnungen sind als reviewed markiert."""
    await seed_demo_tenant(session, tenant_id=DEMO_TENANT, settings=_demo_settings())
    await session.commit()

    total = (
        await session.execute(
            select(func.count(Invoice.id)).where(Invoice.tenant_id == DEMO_TENANT)
        )
    ).scalar_one()
    reviewed = (
        await session.execute(
            select(func.count(Invoice.id)).where(
                Invoice.tenant_id == DEMO_TENANT,
                Invoice.is_reviewed.is_(True),
            )
        )
    ).scalar_one()

    ratio = reviewed / total
    assert 0.20 <= ratio <= 0.40, f"Expected reviewed ratio 0.20-0.40, got {ratio:.2f}"


@pytest.mark.asyncio
async def test_seed_tenant_isolation(session: AsyncSession) -> None:
    """Seeding betrifft nur den Demo-Tenant, nicht andere Tenants."""
    from kontura.infra.models.invoice import Invoice  # noqa: PLC0415

    # Add invoice for another tenant first
    other_inv = Invoice(
        tenant_id="other-corp",
        invoice_number="OTHER-001",
        vendor_name="Other Vendor",
        invoice_date=__import__("datetime").date.today(),
        total_amount=__import__("decimal").Decimal("100.00"),
        currency="EUR",
    )
    session.add(other_inv)
    await session.commit()

    await seed_demo_tenant(session, tenant_id=DEMO_TENANT, settings=_demo_settings())
    await session.commit()

    # Other tenant's data should be untouched
    other_count = (
        await session.execute(
            select(func.count(Invoice.id)).where(Invoice.tenant_id == "other-corp")
        )
    ).scalar_one()
    assert other_count == 1


@pytest.mark.asyncio
async def test_seed_creates_invoice_files(session: AsyncSession) -> None:
    """seed_demo_tenant erstellt InvoiceFiles fuer alle Rechnungen."""
    await seed_demo_tenant(session, tenant_id=DEMO_TENANT, settings=_demo_settings())
    await session.commit()

    file_count = (
        await session.execute(
            select(func.count(InvoiceFile.id)).where(InvoiceFile.tenant_id == DEMO_TENANT)
        )
    ).scalar_one()
    assert file_count == 50


@pytest.mark.asyncio
async def test_seed_status_distribution(session: AsyncSession) -> None:
    """Status-Verteilung liegt in den erwarteten Toleranzbändern."""
    await seed_demo_tenant(session, tenant_id=DEMO_TENANT, settings=_demo_settings())
    await session.commit()

    files = (
        (await session.execute(select(InvoiceFile).where(InvoiceFile.tenant_id == DEMO_TENANT)))
        .scalars()
        .all()
    )

    total = len(files)
    completed = sum(1 for f in files if f.extraction_status == ExtractionStatus.COMPLETED)
    processing = sum(1 for f in files if f.extraction_status == ExtractionStatus.PROCESSING)

    # At least 50% completed (target 70%)
    assert completed / total >= 0.50, f"Expected >= 50% completed, got {completed / total:.1%}"
    # At least 10% processing (target 20%)
    assert processing / total >= 0.10, f"Expected >= 10% processing, got {processing / total:.1%}"
