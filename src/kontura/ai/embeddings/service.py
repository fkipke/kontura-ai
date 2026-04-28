"""EmbeddingService: orchestriert Text-Build, PII-Masking, Embedding und Persistierung.

Senior-Konzept: Klare Schichten-Trennung
========================================
Der Service hat genau 4 Verantwortlichkeiten - jede in einer eigenen Methode:

1. **build_invoice_text()**  - Formatiert Invoice-Felder zu einem deterministischen Text.
2. **PII-Masking**           - Ersetzt IBAN/Email/USt-ID (DSGVO-by-design).
3. **provider.embed()**      - Schickt MASKIERTEN Text an AI-Provider.
4. **repository.add()**      - Persistiert Vektor + maskierten Text tenant-isoliert.

Warum maskieren wir VOR dem Embed-Call (nicht nur fuers Logging)?
- IBANs/Emails sind semantisches Rauschen - Clustering wird besser ohne sie.
- OpenAI bekommt keine PII zu sehen (DSGVO-konform, ohne Zusatzaufwand).
- Der Embedding-Vector ist konsistent mit dem source_text in der DB.
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

from kontura.ai.base import AIProvider
from kontura.ai.embeddings.repository import EmbeddingRepository
from kontura.ai.pii import PIIMasker, RegexMasker
from kontura.core.tenant import TenantContext
from kontura.infra.models import Invoice, InvoiceEmbedding

logger = logging.getLogger(__name__)

# Hard cap, damit der String das DB-Spalten-Limit nicht sprengt.
# (invoice_embeddings.source_text ist String(2000) - siehe Modell.)
_MAX_SOURCE_TEXT_LEN = 2000


class EmbeddingService:
    """Erzeugt und persistiert Embeddings fuer Rechnungen - tenant-isoliert."""

    def __init__(
        self,
        provider: AIProvider,
        repository: EmbeddingRepository,
        embedding_model: str,
        masker: PIIMasker | None = None,
    ) -> None:
        self._provider = provider
        self._repository = repository
        self._embedding_model = embedding_model
        self._masker = masker or RegexMasker()

    async def embed_invoice(
        self,
        tenant: TenantContext,
        invoice: Invoice,
    ) -> InvoiceEmbedding:
        """Erzeugt ein Embedding fuer die Rechnung und persistiert es.

        Der gespeicherte source_text ist die PII-maskierte Variante - in der DB
        liegen nie unmaskierte IBANs/Emails/USt-IDs.
        """
        if invoice.id is None:
            raise ValueError(
                "embed_invoice(): invoice.id ist None - Rechnung muss "
                "zuerst persistiert werden (session.flush())."
            )

        raw_text = self.build_invoice_text(invoice)
        masked = self._masker.mask(raw_text)
        source_text = masked.masked_text[:_MAX_SOURCE_TEXT_LEN]

        logger.info(
            "embedding invoice tenant=%s invoice_id=%s chars=%d",
            tenant,
            invoice.id,
            len(source_text),
        )

        # Wichtig: An den Provider geht der MASKIERTE Text - kein PII zu OpenAI.
        vector = await self._provider.embed(source_text)

        return await self._repository.add(
            tenant=tenant,
            invoice_id=invoice.id,
            embedding=vector,
            model=self._embedding_model,
            source_text=source_text,
        )

    @staticmethod
    def build_invoice_text(invoice: Invoice) -> str:
        """Erstellt eine kanonische Textrepraesentation der Rechnung.

        Deterministisch: Gleiche Felder => gleicher Text => gleicher Embedding-Vector.
        Format ist menschen-lesbar und enthaelt die fuer Aehnlichkeit relevanten
        Felder (Vendor, Datum, Betrag, Status).
        """
        return (
            f"Rechnung {invoice.invoice_number} "
            f"vom {_fmt_date(invoice.invoice_date)} "
            f"von {invoice.vendor_name} "
            f"ueber {_fmt_amount(invoice.total_amount)} {invoice.currency} "
            f"Status: {invoice.status.value}"
        )


def _fmt_date(d: date) -> str:
    return d.isoformat()


def _fmt_amount(a: Decimal) -> str:
    return f"{a:.2f}"
