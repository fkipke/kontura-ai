"""HTTP-Endpoints fuer Eingangsrechnungen (tenant-isoliert)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from kontura.api.dependencies import TenantDep
from kontura.api.invoices.repository import InvoiceRepository
from kontura.api.invoices.schemas import InvoiceCreate, InvoiceRead
from kontura.core.exceptions import ConflictError, NotFoundError
from kontura.infra.db import get_session

router = APIRouter(prefix="/invoices", tags=["Invoices"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.post(
    "",
    response_model=InvoiceRead,
    status_code=status.HTTP_201_CREATED,
    summary="Legt eine neue Eingangsrechnung an",
    responses={
        401: {"description": "JWT fehlt oder ungueltig"},
        409: {"description": "Rechnungsnummer existiert bereits fuer diesen Tenant"},
    },
)
async def create_invoice(
    payload: InvoiceCreate,
    tenant: TenantDep,
    session: SessionDep,
) -> InvoiceRead:
    repo = InvoiceRepository(session)
    try:
        invoice = await repo.create(tenant, payload)
        await session.commit()
    except IntegrityError as exc:
        # K4: composite UniqueConstraint (tenant_id, invoice_number) verletzt.
        await session.rollback()
        raise ConflictError(
            f"Rechnungsnummer '{payload.invoice_number}' existiert bereits "
            f"fuer Tenant '{tenant.tenant_id}'."
        ) from exc
    await session.refresh(invoice)
    return InvoiceRead.model_validate(invoice)


@router.get(
    "",
    response_model=list[InvoiceRead],
    summary="Listet Eingangsrechnungen (sortiert nach Anlage-Datum)",
)
async def list_invoices(
    tenant: TenantDep,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[InvoiceRead]:
    repo = InvoiceRepository(session)
    invoices = await repo.list_all(tenant, limit=limit, offset=offset)
    return [InvoiceRead.model_validate(inv) for inv in invoices]


@router.get(
    "/{invoice_id}",
    response_model=InvoiceRead,
    summary="Liefert eine einzelne Eingangsrechnung",
    responses={404: {"description": "Rechnung nicht gefunden (im Tenant)"}},
)
async def get_invoice(
    invoice_id: uuid.UUID,
    tenant: TenantDep,
    session: SessionDep,
) -> InvoiceRead:
    repo = InvoiceRepository(session)
    invoice = await repo.get_by_id(tenant, invoice_id)
    if invoice is None:
        raise NotFoundError(f"Invoice mit id={invoice_id} nicht gefunden")
    return InvoiceRead.model_validate(invoice)
