"""Smoke-Test fuer den Embedding-Layer (echter OpenAI-Call + Production-DB).

Wird per Default UEBERSPRUNGEN. Aufruf manuell vor Releases:
    uv run pytest -m smoke -v -s

Was passiert:
1. Eine Test-Rechnung mit absichtlicher IBAN im Vendor-Feld wird angelegt.
2. EmbeddingService baut Text -> maskiert -> ruft OpenAI -> speichert.
3. find_similar() laeuft und liefert die gerade angelegte Rechnung zurueck.
4. Wir verifizieren: keine PII im DB-source_text + Audit-Eintrag existiert.

Hinweis: Schreibt in die echte 'kontura'-DB (nicht Test-DB) und macht einen
echten OpenAI-Call. Kostet ein paar Cent. Dafuer beweist es: alles laeuft live.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy import select

from kontura.ai import get_ai_provider
from kontura.ai.embeddings import EmbeddingRepository, EmbeddingService
from kontura.core.config import settings
from kontura.core.tenant import TenantContext
from kontura.infra.db import SessionFactory
from kontura.infra.models import Invoice, InvoiceStatus, LLMAuditEntry


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_embedding_pipeline_end_to_end_with_real_openai() -> None:
    """End-to-End: Invoice -> PII-Mask -> OpenAI-Embed -> pgvector -> Similarity-Search."""
    tenant = TenantContext(tenant_id="smoke-tenant")

    async with SessionFactory() as session:
        # 1) Invoice mit verschmutzten Daten anlegen (echte IBAN im Vendor!)
        inv = Invoice(
            tenant_id=tenant.tenant_id,
            invoice_number=f"SMOKE-{dt.datetime.now(dt.UTC).strftime('%H%M%S')}",
            vendor_name="Telekom IBAN DE89370400440532013000 GmbH",
            invoice_date=dt.date(2026, 4, 28),
            total_amount=Decimal("119.99"),
            currency="EUR",
            status=InvoiceStatus.RECEIVED,
        )
        session.add(inv)
        await session.flush()
        print(f"\n[1/4] Invoice angelegt: id={inv.id} number={inv.invoice_number}")

        # 2) Embedding erzeugen (Audit-Decorator -> OpenAI -> DB)
        service = EmbeddingService(
            provider=get_ai_provider(),
            repository=EmbeddingRepository(session),
            embedding_model=settings.openai_embedding_model,
        )
        entry = await service.embed_invoice(tenant, inv)
        await session.commit()
        print(
            f"[2/4] Embedding erzeugt: id={entry.id} dim={len(entry.embedding)} model={entry.model}"
        )
        print(f"      source_text in DB: {entry.source_text!r}")

        # 3) Verifizieren: keine PII im source_text
        assert "DE89370400440532013000" not in entry.source_text, "PII-LECK!"
        assert "[IBAN_1]" in entry.source_text
        print("[3/4] PII-Check OK -> [IBAN_1] statt echter IBAN gespeichert")

        # 4) find_similar mit dem eigenen Embedding -> sollte sich selbst finden
        repo = EmbeddingRepository(session)
        results = await repo.find_similar(tenant, entry.embedding, limit=3)
        assert any(r.invoice_id == inv.id for r in results), (
            "find_similar lieferte sich selbst nicht"
        )
        print(f"[4/4] find_similar OK -> {len(results)} Treffer, eigene Rechnung dabei")

        # Bonus: Audit-Eintrag verifizieren
        last_audit = await session.execute(
            select(LLMAuditEntry).order_by(LLMAuditEntry.created_at.desc()).limit(1)
        )
        audit_entry = last_audit.scalar_one()
        print(
            f"[BONUS] Audit-Log: provider={audit_entry.provider_name} "
            f"op={audit_entry.operation} duration_ms={audit_entry.duration_ms} "
            f"prompt={audit_entry.prompt_text!r}"
        )
        assert audit_entry.success is True
        assert "DE89370400440532013000" not in audit_entry.prompt_text

    print("\nSMOKE TEST PASSED")
