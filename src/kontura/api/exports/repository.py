"""Repository fuer DATEV-Exporte (tenant-isoliert, reviewed-only)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kontura.core.tenant import TenantContext
from kontura.infra.models.invoice import Invoice


class ExportRepository:
    """Read-only Export-Queries mit hartem Tenant- und reviewed-Filter."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_reviewed_in_range(
        self,
        tenant: TenantContext,
        *,
        from_date: date,
        to_date: date,
    ) -> Sequence[Invoice]:
        """Liefert nur gepruefte Rechnungen im Datumsbereich (inklusiv)."""
        stmt = (
            select(Invoice)
            .where(
                Invoice.tenant_id == tenant.tenant_id,
                Invoice.is_reviewed.is_(True),
                Invoice.invoice_date >= from_date,
                Invoice.invoice_date <= to_date,
            )
            .order_by(Invoice.invoice_date.asc(), Invoice.id.asc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()
