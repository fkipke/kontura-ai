"""HTTP-Endpoint fuer DATEV-EXTF-Export inkl. Vorschau."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from kontura.api.dependencies import TenantDep, TokenDep
from kontura.api.exports.repository import ExportRepository
from kontura.api.exports.schemas import DatevExportPreviewResponse
from kontura.api.exports.service import DatevExportService
from kontura.api.rate_limit import limiter
from kontura.api.vendor_mappings.repository import VendorMappingRepository
from kontura.api.vendor_mappings.service import VendorMappingService
from kontura.core.config import settings
from kontura.core.exceptions import DomainValidationError
from kontura.infra.db import get_session

# Frueher 366 Tage (1 Jahr). Erhoeht auf 10 Jahre damit historische Migrations-
# Exports und Demo-Datensaetze in *einem* Stapel verarbeitet werden koennen.
# Realistische monatliche/quartalsweise Exporte bleiben weiterhin moeglich.
MAX_EXPORT_RANGE_DAYS = 3660

router = APIRouter(prefix="/exports", tags=["Exports"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def _validate_range(from_date: date, to_date: date) -> None:
    if from_date > to_date:
        raise DomainValidationError("'from' darf nicht nach 'to' liegen.")
    if (to_date - from_date).days > MAX_EXPORT_RANGE_DAYS:
        raise DomainValidationError("Zeitraum darf max. 10 Jahre umfassen.")


def _build_service(session: AsyncSession) -> DatevExportService:
    repository = ExportRepository(session)
    mapping_repo = VendorMappingRepository(session)
    mapping_service = VendorMappingService(mapping_repo)
    return DatevExportService(repository, vendor_mapping_service=mapping_service)


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
    include_all_years: Annotated[bool, Query()] = False,
) -> Response:
    _validate_range(from_date, to_date)

    service = _build_service(session)
    result = await service.export_buchungsstapel(
        tenant,
        from_date=from_date,
        to_date=to_date,
        include_all_years=include_all_years,
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


@router.get(
    "/datev/preview",
    response_model=DatevExportPreviewResponse,
    summary="Vorschau: welche Rechnungen wuerden im DATEV-Export landen",
)
@limiter.limit(settings.rate_limit_default_per_tenant)
async def preview_datev(
    request: Request,  # noqa: ARG001
    response: Response,  # noqa: ARG001
    tenant: TenantDep,
    token: TokenDep,  # noqa: ARG001
    session: SessionDep,
    from_date: Annotated[date, Query(alias="from")],
    to_date: Annotated[date, Query(alias="to")],
    include_all_years: Annotated[bool, Query()] = False,
) -> DatevExportPreviewResponse:
    _validate_range(from_date, to_date)

    service = _build_service(session)
    return await service.preview_buchungsstapel(
        tenant,
        from_date=from_date,
        to_date=to_date,
        include_all_years=include_all_years,
    )
