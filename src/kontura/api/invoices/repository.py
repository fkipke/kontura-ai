"""Repository fuer Invoice-Zugriffe (tenant-isoliert).

Senior-Konzept: Tenant-Filter zentral.
ALLE Methoden bekommen einen TenantContext und filtern IMMER nach tenant_id.
Kein Endpoint kann das vergessen - der TenantContext-Parameter ist Pflicht.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kontura.api.invoices.schemas import InvoiceCreate
from kontura.core.tenant import TenantContext
from kontura.infra.models.invoice import Invoice


class InvoiceRepository:
    """Daten-Zugriffs-Schicht fuer Invoices (tenant-aware)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, tenant: TenantContext, data: InvoiceCreate) -> Invoice:
        """Persistiert eine neue Rechnung im Tenant-Scope.

        Wichtig: COMMIT macht der Caller (Endpoint/Service) - nicht das Repository.
        flush() materialisiert nur die ID, ohne die Transaktion zu schliessen.
        """
        invoice = Invoice(
            tenant_id=tenant.tenant_id,
            invoice_number=data.invoice_number,
            vendor_name=data.vendor_name,
            invoice_date=data.invoice_date,
            total_amount=data.total_amount,
            currency=data.currency,
        )
        self._session.add(invoice)
        await self._session.flush()
        return invoice

    async def get_by_id(self, tenant: TenantContext, invoice_id: uuid.UUID) -> Invoice | None:
        """Liefert die Rechnung - nur wenn sie zum Tenant gehoert."""
        stmt = select(Invoice).where(
            Invoice.id == invoice_id,
            Invoice.tenant_id == tenant.tenant_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(
        self, tenant: TenantContext, limit: int = 50, offset: int = 0
    ) -> Sequence[Invoice]:
        """Listet alle Rechnungen des Tenants, sortiert nach created_at DESC."""
        stmt = (
            select(Invoice)
            .where(Invoice.tenant_id == tenant.tenant_id)
            .order_by(Invoice.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()
