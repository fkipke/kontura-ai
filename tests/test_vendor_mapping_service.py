from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from kontura.api.vendor_mappings.repository import VendorMappingRepository
from kontura.api.vendor_mappings.service import VendorMappingService, calculate_confidence
from kontura.core.tenant import TenantContext
from kontura.infra.models.vendor_account_mapping import VendorAccountMapping

TENANT = TenantContext(tenant_id="acme-corp")


async def _insert_mapping(
    session: AsyncSession,
    *,
    normalized: str,
    raw: str,
    account: int,
    usage_count: int,
) -> None:
    session.add(
        VendorAccountMapping(
            tenant_id=TENANT.tenant_id,
            vendor_name_normalized=normalized,
            vendor_name_raw=raw,
            creditor_account_number=account,
            usage_count=usage_count,
            last_used_at=datetime.now(tz=UTC),
        )
    )
    await session.commit()


@pytest.mark.asyncio
async def test_suggest_exact_match_returns_full_confidence_after_5_uses(
    session: AsyncSession,
) -> None:
    await _insert_mapping(
        session,
        normalized="acme lieferant",
        raw="ACME Lieferant GmbH",
        account=70042,
        usage_count=5,
    )
    service = VendorMappingService(VendorMappingRepository(session))

    suggestion = await service.suggest_for_vendor(TENANT, "ACME Lieferant GmbH")

    assert suggestion is not None
    assert suggestion.confidence == 1.0
    assert suggestion.auto_apply is True
    assert suggestion.match_type == "exact"


@pytest.mark.asyncio
async def test_suggest_exact_match_low_confidence_first_time(session: AsyncSession) -> None:
    await _insert_mapping(
        session,
        normalized="acme lieferant",
        raw="ACME Lieferant GmbH",
        account=70042,
        usage_count=1,
    )
    service = VendorMappingService(VendorMappingRepository(session))

    suggestion = await service.suggest_for_vendor(TENANT, "ACME Lieferant GmbH")

    assert suggestion is not None
    assert suggestion.confidence == 0.2
    assert suggestion.auto_apply is False


@pytest.mark.asyncio
async def test_suggest_fuzzy_match_when_no_exact(session: AsyncSession) -> None:
    await _insert_mapping(
        session,
        normalized="acme",
        raw="ACME GmbH",
        account=70042,
        usage_count=5,
    )
    service = VendorMappingService(VendorMappingRepository(session))

    suggestion = await service.suggest_for_vendor(TENANT, "Acmee")

    assert suggestion is not None
    assert suggestion.match_type == "fuzzy"
    assert suggestion.creditor_account_number == 70042


@pytest.mark.asyncio
async def test_suggest_fuzzy_match_halves_confidence(session: AsyncSession) -> None:
    await _insert_mapping(
        session,
        normalized="acme",
        raw="ACME GmbH",
        account=70042,
        usage_count=4,
    )
    service = VendorMappingService(VendorMappingRepository(session))

    suggestion = await service.suggest_for_vendor(TENANT, "Acmee")

    assert suggestion is not None
    assert suggestion.confidence == 0.4
    assert suggestion.auto_apply is False


@pytest.mark.asyncio
async def test_suggest_returns_none_when_no_match(session: AsyncSession) -> None:
    service = VendorMappingService(VendorMappingRepository(session))
    assert await service.suggest_for_vendor(TENANT, "Unbekannt AG") is None


def test_auto_apply_threshold_at_0_8() -> None:
    assert calculate_confidence(4) == 0.8


@pytest.mark.asyncio
async def test_resolve_for_export_returns_default_when_low_confidence(
    session: AsyncSession,
) -> None:
    await _insert_mapping(
        session,
        normalized="acme lieferant",
        raw="ACME Lieferant GmbH",
        account=70042,
        usage_count=1,
    )
    service = VendorMappingService(VendorMappingRepository(session))

    resolved = await service.resolve_for_export(TENANT, "ACME Lieferant GmbH", 70000)

    assert resolved == 70000


@pytest.mark.asyncio
async def test_resolve_for_export_returns_mapped_account_when_auto_apply(
    session: AsyncSession,
) -> None:
    await _insert_mapping(
        session,
        normalized="acme lieferant",
        raw="ACME Lieferant GmbH",
        account=70042,
        usage_count=4,
    )
    service = VendorMappingService(VendorMappingRepository(session))

    resolved = await service.resolve_for_export(TENANT, "ACME Lieferant GmbH", 70000)

    assert resolved == 70042


@pytest.mark.asyncio
async def test_record_mapping_normalizes_vendor_name(session: AsyncSession) -> None:
    service = VendorMappingService(VendorMappingRepository(session))

    mapping = await service.record_mapping(
        TENANT,
        vendor_name_raw="Müller GmbH",
        creditor_account_number=70042,
    )

    assert mapping.vendor_name_normalized == "muller"
