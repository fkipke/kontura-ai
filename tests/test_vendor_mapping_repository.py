from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from kontura.api.vendor_mappings.repository import VendorMappingRepository
from kontura.core.tenant import TenantContext
from kontura.infra.models.vendor_account_mapping import VendorAccountMapping

TENANT_A = TenantContext(tenant_id="acme-corp")
TENANT_B = TenantContext(tenant_id="other-corp")


@pytest.mark.asyncio
async def test_upsert_creates_new_mapping(session: AsyncSession) -> None:
    repository = VendorMappingRepository(session)

    mapping = await repository.upsert(
        TENANT_A,
        vendor_name_raw="ACME Lieferant GmbH",
        vendor_name_normalized="acme lieferant",
        creditor_account_number=70042,
    )

    assert mapping.tenant_id == "acme-corp"
    assert mapping.creditor_account_number == 70042
    assert mapping.usage_count == 1


@pytest.mark.asyncio
async def test_upsert_increments_usage_count_for_same_account(session: AsyncSession) -> None:
    repository = VendorMappingRepository(session)

    first = await repository.upsert(
        TENANT_A,
        vendor_name_raw="ACME Lieferant GmbH",
        vendor_name_normalized="acme lieferant",
        creditor_account_number=70042,
    )
    first_used_at = first.last_used_at
    second = await repository.upsert(
        TENANT_A,
        vendor_name_raw="ACME Lieferant GmbH",
        vendor_name_normalized="acme lieferant",
        creditor_account_number=70042,
    )

    assert second.id == first.id
    assert second.usage_count == 2
    assert second.last_used_at >= first_used_at


@pytest.mark.asyncio
async def test_upsert_resets_usage_count_when_account_changes(session: AsyncSession) -> None:
    repository = VendorMappingRepository(session)

    await repository.upsert(
        TENANT_A,
        vendor_name_raw="ACME Lieferant GmbH",
        vendor_name_normalized="acme lieferant",
        creditor_account_number=70042,
    )
    mapping = await repository.upsert(
        TENANT_A,
        vendor_name_raw="ACME Lieferant GmbH",
        vendor_name_normalized="acme lieferant",
        creditor_account_number=70043,
    )

    assert mapping.creditor_account_number == 70043
    assert mapping.usage_count == 1


@pytest.mark.asyncio
async def test_get_exact_returns_none_when_not_found(session: AsyncSession) -> None:
    repository = VendorMappingRepository(session)
    assert await repository.get_exact(TENANT_A, "missing") is None


@pytest.mark.asyncio
async def test_get_exact_is_tenant_isolated(session: AsyncSession) -> None:
    repository = VendorMappingRepository(session)
    await repository.upsert(
        TENANT_A,
        vendor_name_raw="ACME Lieferant GmbH",
        vendor_name_normalized="acme lieferant",
        creditor_account_number=70042,
    )

    assert await repository.get_exact(TENANT_B, "acme lieferant") is None


@pytest.mark.asyncio
async def test_list_returns_most_recent_first(session: AsyncSession) -> None:
    older = VendorAccountMapping(
        tenant_id="acme-corp",
        vendor_name_normalized="older",
        vendor_name_raw="Older GmbH",
        creditor_account_number=70041,
        usage_count=1,
        last_used_at=datetime.now(tz=UTC) - timedelta(days=1),
    )
    newer = VendorAccountMapping(
        tenant_id="acme-corp",
        vendor_name_normalized="newer",
        vendor_name_raw="Newer GmbH",
        creditor_account_number=70042,
        usage_count=1,
        last_used_at=datetime.now(tz=UTC),
    )
    session.add_all([older, newer])
    await session.commit()

    repository = VendorMappingRepository(session)
    mappings = await repository.list_for_tenant(TENANT_A)

    assert [mapping.vendor_name_normalized for mapping in mappings] == ["newer", "older"]


@pytest.mark.asyncio
async def test_delete_returns_false_for_other_tenant(session: AsyncSession) -> None:
    repository = VendorMappingRepository(session)
    mapping = await repository.upsert(
        TENANT_A,
        vendor_name_raw="ACME Lieferant GmbH",
        vendor_name_normalized="acme lieferant",
        creditor_account_number=70042,
    )
    await session.commit()

    deleted = await repository.delete(TENANT_B, mapping.id)

    assert deleted is False
