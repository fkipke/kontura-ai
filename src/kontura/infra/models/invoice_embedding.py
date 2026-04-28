"""ORM-Modell fuer Invoice-Embeddings (Vector Storage).

Senior-Konzept: Multi-Tenancy via tenant_id-Spalte
==================================================
Jede Zeile gehoert zu genau einem Tenant. Queries MUESSEN immer mit
'WHERE tenant_id = :tid' filtern, sonst sieht ein Kunde Daten anderer Kunden.

Das Repository setzt diesen Filter zentral - keine Chance auf Vergesslichkeits-Bugs.

pgvector
========
Die 'embedding'-Spalte nutzt den VECTOR-Typ aus pgvector.
Dimension = 1536 (OpenAI text-embedding-3-small).
Ein IVFFlat-Index beschleunigt Cosine-Distance-Suche von O(n) auf O(log n).
"""

from __future__ import annotations

from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from kontura.infra.db import Base
from kontura.infra.models._mixins import TimestampMixin, UUIDPrimaryKeyMixin

# OpenAI text-embedding-3-small produziert 1536-dim Vektoren.
EMBEDDING_DIM = 1536


class InvoiceEmbedding(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Speichert das Embedding einer Rechnung fuer semantische Suche.

    Tenant-Isolation: Jede Zeile traegt eine tenant_id. Das Repository
    filtert IMMER zentral - so kann kein Code aus Versehen Daten anderer
    Tenants laden.
    """

    __tablename__ = "invoice_embeddings"

    # Wer "besitzt" diese Zeile? Zentraler Tenant-Filter.
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Welche Rechnung wird hier embedded? FK auf invoices.id.
    invoice_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Der eigentliche Vektor (1536 Dimensionen Float).
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)

    # Welches Modell wurde benutzt? Wichtig fuer spaeteres Re-Embedding bei Modell-Wechsel.
    model: Mapped[str] = mapped_column(String(100), nullable=False)

    # Welcher Source-Text wurde embedded? Fuer Debugging + Erklaerbarkeit.
    # Wir speichern den ge-PII-maskierten Text (nicht die Original-IBAN!).
    source_text: Mapped[str] = mapped_column(String(2000), nullable=False)

    # Composite-Index: Tenant + Invoice (haeufigste Query-Kombination).
    __table_args__ = (Index("ix_invoice_embeddings_tenant_invoice", "tenant_id", "invoice_id"),)

    def __repr__(self) -> str:
        return (
            f"<InvoiceEmbedding tenant={self.tenant_id} "
            f"invoice={self.invoice_id} model={self.model}>"
        )
