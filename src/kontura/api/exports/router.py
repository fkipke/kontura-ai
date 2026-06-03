"""HTTP-Endpoint fuer DATEV-EXTF-Export."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from kontura.api.dependencies import TenantDep, TokenDep
from kontura.api.exports.repository import ExportRepository
from kontura.api.exports.service import DatevExportService
from kontura.api.rate_limit import limiter
from kontura.api.vendor_mappings.repository import VendorMappingRepository
from kontura.api.vendor_mappings.service import VendorMappingService
from kontura.core.config import settings
from kontura.core.exceptions import DomainValidationError
from kontura.infra.db import get_session

router = APIRouter(prefix="/exports", tags=["Exports"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get(
    "/datev",
    summary="Exportiert gepruefte Rechnungen als DATEV-EXTF-Buchungsstapel-CSV",
)
@limiter.limit(settings.rate_limit_default_per_tenant)
async def export_datev(
    request: Request,  # noqa: ARG001 - von slowapi benoetigt
    response: Response,  # noqa: ARG001 - von slowapi benoetigt
    tenant: TenantDep,
    token: TokenDep,  # noqa: ARG001 - JWT-Pflicht explizit machen
    session: SessionDep,
    from_date: Annotated[date, Query(alias="from")],
    to_date: Annotated[date, Query(alias="to")],
) -> Response:
    if from_date > to_date:
        raise DomainValidationError("'from' darf nicht nach 'to' liegen.")
    if (to_date - from_date).days > 366:
        raise DomainValidationError("Zeitraum darf max. 1 Jahr umfassen.")

    repository = ExportRepository(session)
    mapping_repo = VendorMappingRepository(session)
    mapping_service = VendorMappingService(mapping_repo)
    service = DatevExportService(repository, vendor_mapping_service=mapping_service)
    result = await service.export_buchungsstapel(
        tenant,
        from_date=from_date,
        to_date=to_date,
    )

    filename = (
        f"EXTF_Buchungsstapel_{from_date.strftime('%Y%m%d')}_{to_date.strftime('%Y%m%d')}.csv"
    )

    return Response(
        content=result.content,
        status_code=200,
        headers={
            "Content-Type": "text/csv; charset=windows-1252",
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Datev-Invoice-Count": str(result.invoice_count),
            "X-Datev-Skipped-Count": str(result.skipped_count),
        },
    )
