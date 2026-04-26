"""HTTP-Endpoints fuer Eingangsrechnungen."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from kontura.api.invoices.repository import InvoiceRepository
from kontura.api.invoices.schemas import InvoiceCreate, InvoiceRead
from kontura.infra.db import get_session

router = APIRouter(prefix="/invoices", tags=["Invoices"])

# Type-Alias fuer DB-Session-Dependency.
# Annotated[...] ist der moderne FastAPI-Standard (statt Default-Arg mit Depends()).
SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.post(
    "",
    response_model=InvoiceRead,
    status_code=status.HTTP_201_CREATED,
    summary="Legt eine neue Eingangsrechnung an",
)
async def create_invoice(payload: InvoiceCreate, session: SessionDep) -> InvoiceRead:
    repo = InvoiceRepository(session)
    invoice = await repo.create(payload)
    return InvoiceRead.model_validate(invoice)


@router.get(
    "",
    response_model=list[InvoiceRead],
    summary="Listet Eingangsrechnungen (sortiert nach Anlage-Datum)",
)
async def list_invoices(
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[InvoiceRead]:
    repo = InvoiceRepository(session)
    invoices = await repo.list_all(limit=limit, offset=offset)
    return [InvoiceRead.model_validate(inv) for inv in invoices]


@router.get(
    "/{invoice_id}",
    response_model=InvoiceRead,
    summary="Liefert eine einzelne Eingangsrechnung",
)
async def get_invoice(invoice_id: uuid.UUID, session: SessionDep) -> InvoiceRead:
    repo = InvoiceRepository(session)
    invoice = await repo.get_by_id(invoice_id)
    if invoice is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice mit id={invoice_id} nicht gefunden",
        )
    return InvoiceRead.model_validate(invoice)
