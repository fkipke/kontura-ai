"""Repository fuer Invoice-Zugriffe.

Kapselt alle DB-Queries fuer Invoices an EINER Stelle.
Endpoints kennen kein SQL - sie rufen nur Repository-Methoden auf.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kontura.api.invoices.schemas import InvoiceCreate
from kontura.infra.models.invoice import Invoice


class InvoiceRepository:
    """Daten-Zugriffs-Schicht fuer Invoices."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, data: InvoiceCreate) -> Invoice:
        """Legt eine neue Rechnung an und committet die Transaktion."""
        invoice = Invoice(
            invoice_number=data.invoice_number,
            vendor_name=data.vendor_name,
            invoice_date=data.invoice_date,
            total_amount=data.total_amount,
            currency=data.currency,
        )
        self._session.add(invoice)
        await self._session.commit()
        await self._session.refresh(invoice)
        return invoice

    async def get_by_id(self, invoice_id: uuid.UUID) -> Invoice | None:
        """Liefert die Rechnung mit der gegebenen ID, oder None."""
        return await self._session.get(Invoice, invoice_id)

    async def list_all(self, limit: int = 50, offset: int = 0) -> Sequence[Invoice]:
        """Liefert alle Rechnungen, sortiert nach created_at DESC."""
        stmt = select(Invoice).order_by(Invoice.created_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return result.scalars().all()
