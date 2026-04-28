"""Tests fuer EmbeddingService.

Strategie:
- Unit-Tests mit FakeAIProvider (kein OpenAI-Call -> CI-tauglich, deterministisch).
- Integration: Service -> Repository -> echte Postgres+pgvector-DB.
- Wir pruefen die kritischen Vertraege:
    * Text wird deterministisch gebaut.
    * PII (IBAN/Email/USt-ID) verlaesst den Service NIEMALS unmaskiert.
    * source_text in der DB enthaelt keine PII.
    * Tenant-Isolation wird durchgereicht.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from kontura.ai.base import AIProvider, ChatMessage
from kontura.ai.embeddings import EmbeddingRepository, EmbeddingService
from kontura.core.tenant import TenantContext
from kontura.infra.models import EMBEDDING_DIM, Invoice, InvoiceStatus

# ---------- Fakes ----------


class _FakeAIProvider:
    """Minimal-Implementation des AIProvider-Protocols fuer Tests."""

    def __init__(self) -> None:
        self.last_embed_input: str | None = None
        self.embed_calls: int = 0

    @property
    def name(self) -> str:
        return "fake"

    @property
    def embedding_dimension(self) -> int:
        return EMBEDDING_DIM

    async def embed(self, text: str) -> list[float]:
        self.last_embed_input = text
        self.embed_calls += 1
        # Deterministischer Vektor aus Textlaenge - reicht fuer Tests
        return [float(len(text) % 100) * 0.01 for _ in range(EMBEDDING_DIM)]

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> str:
        return "fake-response"


# ---------- Helpers ----------


async def _make_invoice(
    session: AsyncSession,
    *,
    number: str = "INV-2026-001",
    vendor: str = "Telekom Deutschland GmbH",
) -> Invoice:
    inv = Invoice(
        invoice_number=number,
        vendor_name=vendor,
        invoice_date=dt.date(2026, 4, 28),
        total_amount=Decimal("119.99"),
        currency="EUR",
        status=InvoiceStatus.RECEIVED,
    )
    session.add(inv)
    await session.flush()
    return inv


def _make_service(
    session: AsyncSession, provider: _FakeAIProvider | None = None
) -> tuple[EmbeddingService, _FakeAIProvider]:
    fake = provider or _FakeAIProvider()
    repo = EmbeddingRepository(session)
    service = EmbeddingService(
        provider=cast(AIProvider, fake),
        repository=repo,
        embedding_model="fake-embedding-model",
    )
    return service, fake


# ---------- build_invoice_text() ----------


def test_build_invoice_text_is_deterministic() -> None:
    inv = Invoice(
        invoice_number="INV-001",
        vendor_name="Acme GmbH",
        invoice_date=dt.date(2026, 1, 15),
        total_amount=Decimal("250.00"),
        currency="EUR",
        status=InvoiceStatus.RECEIVED,
    )
    text1 = EmbeddingService.build_invoice_text(inv)
    text2 = EmbeddingService.build_invoice_text(inv)
    assert text1 == text2


def test_build_invoice_text_contains_all_relevant_fields() -> None:
    inv = Invoice(
        invoice_number="INV-2026-042",
        vendor_name="Acme GmbH",
        invoice_date=dt.date(2026, 1, 15),
        total_amount=Decimal("250.00"),
        currency="EUR",
        status=InvoiceStatus.RECEIVED,
    )
    text = EmbeddingService.build_invoice_text(inv)
    assert "INV-2026-042" in text
    assert "Acme GmbH" in text
    assert "2026-01-15" in text
    assert "250.00" in text
    assert "EUR" in text
    assert "received" in text

# ---------- embed_invoice() ----------


@pytest.mark.asyncio
async def test_embed_invoice_persists_entry(session: AsyncSession) -> None:
    service, fake = _make_service(session)
    tenant = TenantContext(tenant_id="acme")
    inv = await _make_invoice(session)

    entry = await service.embed_invoice(tenant, inv)

    assert entry.id is not None
    assert entry.tenant_id == "acme"
    assert entry.invoice_id == inv.id
    assert entry.model == "fake-embedding-model"
    assert len(entry.embedding) == EMBEDDING_DIM
    assert fake.embed_calls == 1


@pytest.mark.asyncio
async def test_embed_invoice_sends_masked_text_to_provider(session: AsyncSession) -> None:
    """KRITISCH: Der AIProvider darf NIE unmaskiertes PII zu sehen bekommen."""
    service, fake = _make_service(session)
    tenant = TenantContext(tenant_id="acme")
    inv = await _make_invoice(
        session,
        # Vendor enthaelt eine echte IBAN - das simuliert verschmutzte Realdaten
        vendor="Telekom DE89370400440532013000 GmbH",
    )

    await service.embed_invoice(tenant, inv)

    # Der Provider hat NUR den maskierten Text gesehen
    assert fake.last_embed_input is not None
    assert "DE89370400440532013000" not in fake.last_embed_input
    assert "[IBAN_1]" in fake.last_embed_input


@pytest.mark.asyncio
async def test_embed_invoice_stores_masked_source_text(session: AsyncSession) -> None:
    """In der DB darf NIEMALS unmaskiertes PII landen."""
    service, _ = _make_service(session)
    tenant = TenantContext(tenant_id="acme")
    inv = await _make_invoice(
        session,
        vendor="Acme buero@firma.de GmbH",  # Email als PII
    )

    entry = await service.embed_invoice(tenant, inv)

    assert "buero@firma.de" not in entry.source_text
    assert "[EMAIL_1]" in entry.source_text


@pytest.mark.asyncio
async def test_embed_invoice_rejects_unpersisted_invoice() -> None:
    """Ohne ID gibts keinen FK -> klare Fehlermeldung statt DB-Fehler."""
    repo = EmbeddingRepository(cast(AsyncSession, None))  # session wird nie genutzt
    service = EmbeddingService(
        provider=cast(AIProvider, _FakeAIProvider()),
        repository=repo,
        embedding_model="fake",
    )
    tenant = TenantContext(tenant_id="acme")
    # ID weglassen -> nicht persistiert
    inv = Invoice(
        invoice_number="X",
        vendor_name="V",
        invoice_date=dt.date(2026, 1, 1),
        total_amount=Decimal("1.00"),
        currency="EUR",
        status=InvoiceStatus.RECEIVED,
    )

    with pytest.raises(ValueError, match="invoice.id ist None"):
        await service.embed_invoice(tenant, inv)


@pytest.mark.asyncio
async def test_embed_invoice_supports_find_similar_roundtrip(session: AsyncSession) -> None:
    """End-to-End: zwei Rechnungen embedden, dann eine als Query nutzen."""
    service, _ = _make_service(session)
    tenant = TenantContext(tenant_id="acme")

    inv1 = await _make_invoice(session, number="INV-001", vendor="Vodafone GmbH")
    inv2 = await _make_invoice(session, number="INV-002", vendor="Telekom GmbH")

    await service.embed_invoice(tenant, inv1)
    await service.embed_invoice(tenant, inv2)

    # Query: finde aehnliche zur ersten Rechnung
    repo = EmbeddingRepository(session)
    query_text = EmbeddingService.build_invoice_text(inv1)
    query_vec = [float(len(query_text) % 100) * 0.01 for _ in range(EMBEDDING_DIM)]

    results = await repo.find_similar(tenant, query_vec, limit=5)

    assert len(results) == 2
    invoice_ids = {r.invoice_id for r in results}
    assert inv1.id in invoice_ids
    assert inv2.id in invoice_ids
