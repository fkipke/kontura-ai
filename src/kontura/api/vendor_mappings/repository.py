"""Repository fuer Vendor→Kreditor-Mappings."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kontura.core.tenant import TenantContext
from kontura.infra.models.vendor_account_mapping import VendorAccountMapping


class VendorMappingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_exact(
        self, tenant: TenantContext, normalized: str
    ) -> VendorAccountMapping | None:
        stmt = select(VendorAccountMapping).where(
            VendorAccountMapping.tenant_id == tenant.tenant_id,
            VendorAccountMapping.vendor_name_normalized == normalized,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_tenant(
        self, tenant: TenantContext, limit: int = 100, offset: int = 0
    ) -> list[VendorAccountMapping]:
        stmt = (
            select(VendorAccountMapping)
            .where(VendorAccountMapping.tenant_id == tenant.tenant_id)
            .order_by(VendorAccountMapping.last_used_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def upsert(
        self,
        tenant: TenantContext,
        *,
        vendor_name_raw: str,
        vendor_name_normalized: str,
        creditor_account_number: int,
    ) -> VendorAccountMapping:
        now = datetime.now(tz=UTC)
        existing = await self.get_exact(tenant, vendor_name_normalized)

        if existing is None:
            mapping = VendorAccountMapping(
                tenant_id=tenant.tenant_id,
                vendor_name_normalized=vendor_name_normalized,
                vendor_name_raw=vendor_name_raw,
                creditor_account_number=creditor_account_number,
                usage_count=1,
                last_used_at=now,
            )
            self._session.add(mapping)
            await self._session.flush()
            return mapping

        existing.vendor_name_raw = vendor_name_raw
        existing.last_used_at = now
        if existing.creditor_account_number == creditor_account_number:
            existing.usage_count += 1
        else:
            existing.creditor_account_number = creditor_account_number
            existing.usage_count = 1

        await self._session.flush()
        return existing

    async def delete(self, tenant: TenantContext, mapping_id: uuid.UUID) -> bool:
        stmt = select(VendorAccountMapping).where(
            VendorAccountMapping.id == mapping_id,
            VendorAccountMapping.tenant_id == tenant.tenant_id,
        )
        result = await self._session.execute(stmt)
        mapping = result.scalar_one_or_none()
        if mapping is None:
            return False

        await self._session.delete(mapping)
        await self._session.flush()
        return True
