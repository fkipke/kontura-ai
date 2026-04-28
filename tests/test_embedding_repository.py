"""Tests fuer EmbeddingRepository - inkl. Tenant-Isolation.

Diese Tests sind kritisch: sie beweisen, dass Tenant A NIE Daten von B sieht.
Bei Multi-Mandanten-SaaS ist das die wichtigste Sicherheitsgarantie.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from kontura.ai.embeddings import EmbeddingRepository
from kontura.core.tenant import TenantContext
from kontura.infra.models import EMBEDDING_DIM, Invoice, InvoiceStatus


def _vec(seed: float) -> list[float]:
    """Erzeugt einen deterministischen Vektor der korrekten Dimension."""
    # Einfacher Trick: Ein konstanter Vektor mit kleinen Variationen pro seed.
    return [seed + (i * 0.0001) for i in range(EMBEDDING_DIM)]


async def _make_invoice(session: AsyncSession, number: str) -> Invoice:
    """Hilfsfunktion: legt eine Test-Invoice an (FK-Voraussetzung)."""
    inv = Invoice(
        invoice_number=number,
        vendor_name="Test Vendor",
        invoice_date=dt.date(2026, 1, 1),
        total_amount=Decimal("100.00"),
        currency="EUR",
        status=InvoiceStatus.RECEIVED,
    )
    session.add(inv)
    await session.flush()
    return inv


@pytest.mark.asyncio
async def test_add_persists_embedding(session: AsyncSession) -> None:
    repo = EmbeddingRepository(session)
    tenant = TenantContext(tenant_id="acme")
    inv = await _make_invoice(session, "INV-001")

    entry = await repo.add(
        tenant=tenant,
        invoice_id=inv.id,
        embedding=_vec(0.1),
        model="text-embedding-3-small",
        source_text="Test invoice text",
    )

    assert entry.id is not None
    assert entry.tenant_id == "acme"
    assert entry.invoice_id == inv.id
    assert entry.model == "text-embedding-3-small"


@pytest.mark.asyncio
async def test_get_by_invoice_returns_entry(session: AsyncSession) -> None:
    repo = EmbeddingRepository(session)
    tenant = TenantContext(tenant_id="acme")
    inv = await _make_invoice(session, "INV-002")
    await repo.add(tenant, inv.id, _vec(0.2), "test-model", "src")

    found = await repo.get_by_invoice(tenant, inv.id)

    assert found is not None
    assert found.invoice_id == inv.id


@pytest.mark.asyncio
async def test_get_by_invoice_returns_none_for_unknown(session: AsyncSession) -> None:
    repo = EmbeddingRepository(session)
    tenant = TenantContext(tenant_id="acme")

    found = await repo.get_by_invoice(tenant, uuid4())

    assert found is None


@pytest.mark.asyncio
async def test_tenant_isolation_get_by_invoice(session: AsyncSession) -> None:
    """KRITISCH: Tenant B darf das Embedding von Tenant A nicht sehen."""
    repo = EmbeddingRepository(session)
    tenant_a = TenantContext(tenant_id="tenant-a")
    tenant_b = TenantContext(tenant_id="tenant-b")
    inv = await _make_invoice(session, "INV-003")

    # Tenant A speichert ein Embedding
    await repo.add(tenant_a, inv.id, _vec(0.3), "test-model", "secret")

    # Tenant B versucht es zu lesen
    leaked = await repo.get_by_invoice(tenant_b, inv.id)

    assert leaked is None, "Tenant B darf NIEMALS Daten von Tenant A sehen!"


@pytest.mark.asyncio
async def test_find_similar_returns_results_sorted_by_distance(
    session: AsyncSession,
) -> None:
    repo = EmbeddingRepository(session)
    tenant = TenantContext(tenant_id="acme")

    inv1 = await _make_invoice(session, "INV-A")
    inv2 = await _make_invoice(session, "INV-B")
    inv3 = await _make_invoice(session, "INV-C")

    await repo.add(tenant, inv1.id, _vec(0.10), "m", "near")
    await repo.add(tenant, inv2.id, _vec(0.11), "m", "very-near")
    await repo.add(tenant, inv3.id, _vec(0.90), "m", "far")

    # Query nahe an _vec(0.10/0.11), weit weg von 0.90
    results = await repo.find_similar(tenant, _vec(0.105), limit=3)

    assert len(results) == 3
    # Sortiert: kleinste Distanz zuerst
    distances = [r.distance for r in results]
    assert distances == sorted(distances), "Ergebnisse muessen aufsteigend sortiert sein"


@pytest.mark.asyncio
async def test_find_similar_respects_tenant_isolation(session: AsyncSession) -> None:
    """KRITISCH: find_similar darf nur Embeddings des eigenen Tenants liefern."""
    repo = EmbeddingRepository(session)
    tenant_a = TenantContext(tenant_id="tenant-a")
    tenant_b = TenantContext(tenant_id="tenant-b")

    inv_a = await _make_invoice(session, "INV-A")
    inv_b = await _make_invoice(session, "INV-B")

    # Beide Tenants speichern Embeddings - identische Vektoren
    await repo.add(tenant_a, inv_a.id, _vec(0.5), "m", "tenant-a-secret")
    await repo.add(tenant_b, inv_b.id, _vec(0.5), "m", "tenant-b-secret")

    # Tenant A sucht - darf nur eigenes Embedding finden
    results_a = await repo.find_similar(tenant_a, _vec(0.5), limit=10)

    assert len(results_a) == 1, "Tenant A darf nur 1 Embedding sehen (sein eigenes)"
    assert results_a[0].invoice_id == inv_a.id
    assert "tenant-a" in results_a[0].source_text


@pytest.mark.asyncio
async def test_find_similar_rejects_invalid_limit(session: AsyncSession) -> None:
    repo = EmbeddingRepository(session)
    tenant = TenantContext(tenant_id="acme")

    with pytest.raises(ValueError, match="limit"):
        await repo.find_similar(tenant, _vec(0.5), limit=0)
