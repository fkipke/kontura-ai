"""Repository fuer Invoice-Zugriffe (tenant-isoliert).

Senior-Konzept: Tenant-Filter zentral.
ALLE Methoden bekommen einen TenantContext und filtern IMMER nach tenant_id.
Kein Endpoint kann das vergessen - der TenantContext-Parameter ist Pflicht.
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kontura.api.invoices.schemas import InvoiceCreate
from kontura.core.tenant import TenantContext
from kontura.infra.models.invoice import Invoice
from kontura.infra.models.invoice_edit import InvoiceEdit


def _to_jsonb(value: Any) -> dict[str, Any]:
    """Serialisiert einen skalaren Wert in JSONB-kompatibles Dict."""
    return {"value": _json_safe(value)}


def _json_safe(value: Any) -> Any:
    """Konvertiert Pydantic-Modelle rekursiv in JSON-kompatible Primitive."""
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    return value


def _line_items_equal(a: Any, b: Any) -> bool:
    """Vergleicht zwei line_items-Werte auf inhaltliche Gleichheit."""
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return bool(_json_safe(a) == _json_safe(b))


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

    async def update_with_audit(
        self,
        invoice: Invoice,
        changes: dict[str, Any],
        user_id: uuid.UUID,
        is_reviewed_change: bool | None = None,
        reviewed_at: datetime | None = None,
        reviewed_by_user_id: uuid.UUID | None = None,
    ) -> Invoice:
        """Atomarer Update: Audit-Inserts + Feld-Updates + version++ in einer Transaktion.

        changes: Dict[field_name, new_value] - nur geaenderte Felder (ohne is_reviewed).
        is_reviewed_change: explizit uebergeben wenn is_reviewed sich aendert.
        """
        # 1. Audit-Eintraege fuer geaenderte Felder erzeugen
        for field_name, new_value in changes.items():
            old_value = getattr(invoice, field_name)

            # line_items: Deep-Equality-Check
            if field_name == "line_items":
                if _line_items_equal(old_value, new_value):
                    continue  # Kein Audit-Eintrag wenn ungeaendert
            else:
                if old_value == new_value:
                    continue  # Kein Audit-Eintrag wenn ungeaendert

            edit = InvoiceEdit(
                tenant_id=invoice.tenant_id,
                invoice_id=invoice.id,
                user_id=user_id,
                field=field_name,
                old_value=_to_jsonb(old_value),
                new_value=_to_jsonb(new_value),
            )
            self._session.add(edit)
            # Feld am ORM-Objekt setzen
            setattr(
                invoice,
                field_name,
                _json_safe(new_value) if field_name == "line_items" else new_value,
            )

        # 2. is_reviewed-Sonderfall
        if is_reviewed_change is not None:
            old_reviewed = invoice.is_reviewed
            if old_reviewed != is_reviewed_change:
                edit = InvoiceEdit(
                    tenant_id=invoice.tenant_id,
                    invoice_id=invoice.id,
                    user_id=user_id,
                    field="is_reviewed",
                    old_value={"value": old_reviewed},
                    new_value={"value": is_reviewed_change},
                )
                self._session.add(edit)
            invoice.is_reviewed = is_reviewed_change
            invoice.reviewed_at = reviewed_at
            invoice.reviewed_by_user_id = reviewed_by_user_id

        # 3. version++ (immer wenn diese Methode aufgerufen wird)
        invoice.version = invoice.version + 1

        # 4. updated_at aktualisieren
        invoice.updated_at = datetime.now(tz=UTC)

        await self._session.flush()
        return invoice
