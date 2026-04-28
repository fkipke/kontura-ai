"""Repository-Layer fuer InvoiceEmbedding.

Senior-Konzept: Repository-Pattern + Tenant-Isolation
=====================================================
Das Repository ist die EINZIGE Stelle, an der invoice_embeddings angefasst
werden. Alle Methoden bekommen einen TenantContext und filtern IMMER
nach tenant_id.

Damit ist es UNMOEGLICH, aus Versehen Daten anderer Tenants zu lesen oder
zu schreiben - der Compiler/Test wuerde scheitern, wenn jemand TenantContext
weglaesst.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kontura.core.tenant import TenantContext
from kontura.infra.models import InvoiceEmbedding


@dataclass(frozen=True, slots=True)
class SimilarInvoice:
    """Ergebnis einer Aehnlichkeits-Suche.

    distance: Cosine-Distanz (0.0 = identisch, 2.0 = entgegengesetzt).
              In der Praxis sind <0.3 sehr aehnlich, >0.7 unverwandt.
    """

    invoice_id: UUID
    embedding_id: UUID
    distance: float
    source_text: str


class EmbeddingRepository:
    """Persistiert und sucht Invoice-Embeddings - tenant-isoliert."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        tenant: TenantContext,
        invoice_id: UUID,
        embedding: list[float],
        model: str,
        source_text: str,
    ) -> InvoiceEmbedding:
        """Legt einen neuen Embedding-Eintrag fuer den Tenant an."""
        entry = InvoiceEmbedding(
            tenant_id=tenant.tenant_id,
            invoice_id=invoice_id,
            embedding=embedding,
            model=model,
            source_text=source_text,
        )
        self._session.add(entry)
        await self._session.flush()  # ID materialisieren, ohne Commit
        return entry

    async def get_by_invoice(
        self,
        tenant: TenantContext,
        invoice_id: UUID,
    ) -> InvoiceEmbedding | None:
        """Liefert das Embedding einer Rechnung - nur wenn es zum Tenant gehoert."""
        stmt = select(InvoiceEmbedding).where(
            InvoiceEmbedding.tenant_id == tenant.tenant_id,
            InvoiceEmbedding.invoice_id == invoice_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_similar(
        self,
        tenant: TenantContext,
        query_embedding: list[float],
        limit: int = 5,
    ) -> list[SimilarInvoice]:
        """Findet die 'limit' aehnlichsten Embeddings im Tenant via Cosine-Distance.

        Nutzt den IVFFlat-Index (vector_cosine_ops). Liefert Distanzen aufsteigend
        (kleinste Distanz = aehnlichste Rechnung).
        """
        if limit < 1:
            raise ValueError("limit muss >= 1 sein")

        # '<=>' ist der Cosine-Distance-Operator von pgvector.
        distance = InvoiceEmbedding.embedding.cosine_distance(query_embedding)

        stmt = (
            select(
                InvoiceEmbedding.id,
                InvoiceEmbedding.invoice_id,
                InvoiceEmbedding.source_text,
                distance.label("distance"),
            )
            .where(InvoiceEmbedding.tenant_id == tenant.tenant_id)
            .order_by(distance)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [
            SimilarInvoice(
                embedding_id=row.id,
                invoice_id=row.invoice_id,
                distance=float(row.distance),
                source_text=row.source_text,
            )
            for row in result.all()
        ]
