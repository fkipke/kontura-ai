"""Repository fuer InvoiceFile-Zugriffe (tenant-isoliert).

Alle Methoden erhalten einen TenantContext und filtern IMMER nach tenant_id.
Kein Endpoint kann das vergessen - der TenantContext-Parameter ist Pflicht.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from kontura.core.tenant import TenantContext
from kontura.infra.models.invoice_file import InvoiceFile


class InvoiceFileRepository:
    """Daten-Zugriffs-Schicht fuer InvoiceFiles (tenant-aware)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_sha256(self, tenant: TenantContext, sha256: str) -> InvoiceFile | None:
        """Liefert einen bestehenden Eintrag fuer Deduplication-Check.

        Wird vor dem Upload geprueft: Gleiche sha256 im gleichen Tenant = Duplikat.
        """
        stmt = select(InvoiceFile).where(
            InvoiceFile.tenant_id == tenant.tenant_id,
            InvoiceFile.sha256 == sha256,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self,
        tenant: TenantContext,
        uploaded_by_user_id: uuid.UUID,
        filename: str,
        mime_type: str,
        size_bytes: int,
        sha256: str,
        storage_path: str,
    ) -> InvoiceFile:
        """Persistiert eine neue InvoiceFile im Tenant-Scope.

        COMMIT macht der Caller - nicht das Repository (Single-Responsibility).
        flush() materialisiert die ID ohne die Transaktion zu schliessen.
        """
        invoice_file = InvoiceFile(
            tenant_id=tenant.tenant_id,
            uploaded_by_user_id=uploaded_by_user_id,
            filename=filename,
            mime_type=mime_type,
            size_bytes=size_bytes,
            sha256=sha256,
            storage_path=storage_path,
        )
        self._session.add(invoice_file)
        await self._session.flush()
        return invoice_file

    async def get_by_id(self, tenant: TenantContext, file_id: uuid.UUID) -> InvoiceFile | None:
        """Liefert eine Datei - nur wenn sie zum Tenant gehoert.

        Gibt None zurueck wenn nicht gefunden ODER falscher Tenant (kein Info-Leak).
        """
        stmt = select(InvoiceFile).where(
            InvoiceFile.id == file_id,
            InvoiceFile.tenant_id == tenant.tenant_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(
        self, tenant: TenantContext, limit: int = 50, offset: int = 0
    ) -> Sequence[InvoiceFile]:
        """Listet alle Dateien des Tenants, sortiert nach created_at DESC."""
        stmt = (
            select(InvoiceFile)
            .where(InvoiceFile.tenant_id == tenant.tenant_id)
            .order_by(InvoiceFile.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def count_all(self, tenant: TenantContext) -> int:
        """Zaehlt alle Dateien des Tenants (fuer X-Total-Count Header)."""
        stmt = select(func.count()).where(
            InvoiceFile.tenant_id == tenant.tenant_id,
        )
        # Use scalar() which returns Optional[int]; fallback to 0
        result = await self._session.execute(stmt)
        count = result.scalar()
        return count if count is not None else 0
