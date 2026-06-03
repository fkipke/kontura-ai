"""HTTP-Endpoints fuer Vendor→Kreditor-Mappings."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from kontura.api.dependencies import TenantDep
from kontura.api.rate_limit import limiter
from kontura.api.vendor_mappings.repository import VendorMappingRepository
from kontura.api.vendor_mappings.schemas import (
    MappingSuggestionResponse,
    UpsertMappingPayload,
    VendorMappingResponse,
)
from kontura.api.vendor_mappings.service import VendorMappingService
from kontura.core.config import settings
from kontura.core.exceptions import NotFoundError
from kontura.infra.db import get_session

router = APIRouter(prefix="/vendor-mappings", tags=["vendor-mappings"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get(
    "/suggest",
    response_model=MappingSuggestionResponse | None,
    summary="Schlaegt ein Kreditorkonto fuer einen Lieferantennamen vor",
)
@limiter.limit(settings.rate_limit_default_per_tenant)
async def suggest_mapping(
    request: Request,  # noqa: ARG001
    response: Response,  # noqa: ARG001
    vendor_name: Annotated[str, Query(min_length=1, max_length=255)],
    tenant: TenantDep,
    session: SessionDep,
) -> MappingSuggestionResponse | None:
    repository = VendorMappingRepository(session)
    service = VendorMappingService(repository)
    suggestion = await service.suggest_for_vendor(tenant, vendor_name)
    if suggestion is None:
        return None
    return MappingSuggestionResponse.model_validate(suggestion)


@router.put(
    "",
    response_model=VendorMappingResponse,
    status_code=status.HTTP_200_OK,
    summary="Lernt oder aktualisiert ein Lieferant→Kreditor-Mapping",
)
@limiter.limit(settings.rate_limit_default_per_tenant)
async def upsert_mapping(
    request: Request,  # noqa: ARG001
    response: Response,  # noqa: ARG001
    payload: UpsertMappingPayload,
    tenant: TenantDep,
    session: SessionDep,
) -> VendorMappingResponse:
    repository = VendorMappingRepository(session)
    service = VendorMappingService(repository)
    mapping = await service.record_mapping(
        tenant,
        vendor_name_raw=payload.vendor_name,
        creditor_account_number=payload.creditor_account_number,
    )
    await session.commit()
    await session.refresh(mapping)
    return VendorMappingResponse.model_validate(mapping)


@router.get(
    "",
    response_model=list[VendorMappingResponse],
    summary="Listet alle gelernten Mappings des Tenants",
)
@limiter.limit(settings.rate_limit_default_per_tenant)
async def list_mappings(
    request: Request,  # noqa: ARG001
    response: Response,  # noqa: ARG001
    tenant: TenantDep,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[VendorMappingResponse]:
    repository = VendorMappingRepository(session)
    mappings = await repository.list_for_tenant(tenant, limit=limit, offset=offset)
    return [VendorMappingResponse.model_validate(mapping) for mapping in mappings]


@router.delete(
    "/{mapping_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Loescht ein gelerntes Mapping",
)
@limiter.limit(settings.rate_limit_default_per_tenant)
async def delete_mapping(
    request: Request,  # noqa: ARG001
    response: Response,  # noqa: ARG001
    mapping_id: uuid.UUID,
    tenant: TenantDep,
    session: SessionDep,
) -> None:
    repository = VendorMappingRepository(session)
    deleted = await repository.delete(tenant, mapping_id)
    if not deleted:
        raise NotFoundError(f"Vendor-Mapping {mapping_id} nicht gefunden")

    await session.commit()
    return None
