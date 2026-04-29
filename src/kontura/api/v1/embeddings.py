"""V1 Embedding-Endpoints.

Routes (alle relativ zu '/api/v1'):
- POST /invoices/{invoice_id}/embed     - Erzeugt + persistiert das Embedding
- GET  /invoices/{invoice_id}/similar   - Findet aehnliche Rechnungen via Cosine
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from kontura.api.v1.dependencies import EmbeddingServiceDep, SessionDep, TenantDep
from kontura.api.v1.schemas import (
    EmbeddingResponse,
    SimilarInvoiceResponse,
    SimilarInvoicesResponse,
)
from kontura.infra.models import Invoice, InvoiceEmbedding

router = APIRouter(tags=["Embeddings"])


@router.post(
    "/invoices/{invoice_id}/embed",
    response_model=EmbeddingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Embedding fuer eine Rechnung erzeugen",
    description=(
        "Vektorisiert die Rechnung via OpenAI und persistiert sie tenant-isoliert. "
        "Der gespeicherte source_text ist PII-maskiert (IBAN/Email/USt-ID)."
    ),
    responses={
        404: {"description": "Rechnung nicht gefunden (im Tenant)"},
        409: {"description": "Embedding existiert bereits fuer diese Rechnung"},
    },
)
async def create_invoice_embedding(
    invoice_id: UUID,
    tenant: TenantDep,
    service: EmbeddingServiceDep,
    session: SessionDep,
) -> EmbeddingResponse:
    """Erzeugt ein Embedding fuer die Rechnung."""
    invoice = await session.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rechnung {invoice_id} nicht gefunden.",
        )

    # Idempotenz: kein doppeltes Embedding fuer dieselbe Rechnung pro Tenant
    existing_stmt = select(InvoiceEmbedding).where(
        InvoiceEmbedding.tenant_id == tenant.tenant_id,
        InvoiceEmbedding.invoice_id == invoice_id,
    )
    existing = (await session.execute(existing_stmt)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Embedding fuer Rechnung {invoice_id} existiert bereits.",
        )

    entry = await service.embed_invoice(tenant, invoice)
    await session.commit()
    await session.refresh(entry)

    return EmbeddingResponse(
        id=entry.id,
        invoice_id=entry.invoice_id,
        model=entry.model,
        source_text=entry.source_text,
        dimension=len(entry.embedding),
        created_at=entry.created_at,
    )


@router.get(
    "/invoices/{invoice_id}/similar",
    response_model=SimilarInvoicesResponse,
    summary="Aehnliche Rechnungen finden",
    description=(
        "Liefert die top-N aehnlichsten Rechnungen im Tenant via Cosine-Distance "
        "(pgvector IVFFlat-Index). Die Eingabe-Rechnung selbst kann im Ergebnis "
        "vorkommen (sinnvoll als Identitaets-Sanity-Check)."
    ),
    responses={
        404: {"description": "Eingabe-Rechnung oder ihr Embedding nicht gefunden"},
    },
)
async def find_similar_invoices(
    invoice_id: UUID,
    tenant: TenantDep,
    service: EmbeddingServiceDep,
    session: SessionDep,
    limit: int = Query(default=5, ge=1, le=50, description="Maximale Anzahl Treffer"),
) -> SimilarInvoicesResponse:
    """Findet aehnliche Rechnungen zur uebergebenen Rechnung."""
    # Embedding der Eingabe-Rechnung holen (nur im eigenen Tenant!)
    stmt = select(InvoiceEmbedding).where(
        InvoiceEmbedding.tenant_id == tenant.tenant_id,
        InvoiceEmbedding.invoice_id == invoice_id,
    )
    source = (await session.execute(stmt)).scalar_one_or_none()
    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Kein Embedding fuer Rechnung {invoice_id} gefunden. "
                "Erst POST /invoices/{id}/embed ausfuehren."
            ),
        )

    results = await service._repository.find_similar(  # noqa: SLF001
        tenant=tenant,
        query_embedding=source.embedding,
        limit=limit,
    )

    return SimilarInvoicesResponse(
        results=[
            SimilarInvoiceResponse(
                invoice_id=r.invoice_id,
                embedding_id=r.embedding_id,
                distance=r.distance,
                source_text=r.source_text,
            )
            for r in results
        ],
        count=len(results),
    )
