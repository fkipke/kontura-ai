"""Repository fuer Invoice-Zugriffe (tenant-isoliert).

Senior-Konzept: Tenant-Filter zentral.
ALLE Methoden bekommen einen TenantContext und filtern IMMER nach tenant_id.
Kein Endpoint kann das vergessen - der TenantContext-Parameter ist Pflicht.
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kontura.api.invoices.schemas import InvoiceCreate, InvoiceLineItem
from kontura.core.tenant import TenantContext
from kontura.infra.models.invoice import Invoice
from kontura.infra.models.invoice_edit import InvoiceEdit


def _serialize_line_items(items: Any) -> Any:
    """Konvertiert eine Liste von InvoiceLineItem (Pydantic) in JSON-safe Dicts.

    JSONB-Spalten gehen via asyncpg durch json.dumps - Pydantic-Modelle
    sind dort NICHT serialisierbar. Wir muessen vor jedem JSONB-Write
    auf primitive Typen runter (Decimal -> str, etc.). mode="json" macht
    genau das.
    """
    if items is None:
        return None
    result = []
    for item in items:
        if isinstance(item, InvoiceLineItem):
            result.append(item.model_dump(mode="json"))
        elif isinstance(item, dict):
            # Defensive: falls schon dict, ggf. Decimals stringifizieren
            result.append({k: str(v) if isinstance(v, Decimal) else v for k, v in item.items()})
        else:
            result.append(item)
    return result


def _to_jsonb(value: Any) -> dict[str, Any]:
    """Serialisiert einen skalaren Wert in JSONB-kompatibles Dict."""
    if isinstance(value, Decimal):
        return {"value": str(value)}
    if isinstance(value, datetime):
        return {"value": value.isoformat()}
    if isinstance(value, date):
        # invoice_date ist ein date, kein datetime - separat behandeln,
        # sonst landet ein nicht-serialisierbares date-Objekt in JSONB.
        return {"value": value.isoformat()}
    if isinstance(value, list):
        return {"value": _serialize_line_items(value)}
    return {"value": value}


def _line_items_equal(a: Any, b: Any) -> bool:
    """Vergleicht zwei line_items-Werte auf inhaltliche Gleichheit."""
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    # Nutzt _serialize_line_items als Normalisierungs-Grundlage:
    # nach der Serialisierung sind Decimals als Strings vergleichbar.
    return _serialize_line_items(a) == _serialize_line_items(b)


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

            # line_items: Deep-Equality-Check + Pydantic-Serialisierung
            if field_name == "line_items":
                if _line_items_equal(old_value, new_value):
                    continue  # Kein Audit-Eintrag wenn ungeaendert

                # KRITISCH: Pydantic-Modelle MUESSEN vor JSONB-Insert in
                # JSON-safe Dicts konvertiert werden - sonst stirbt asyncpg
                # mit "Object of type InvoiceLineItem is not JSON serializable".
                serialized_new = _serialize_line_items(new_value)

                edit = InvoiceEdit(
                    tenant_id=invoice.tenant_id,
                    invoice_id=invoice.id,
                    user_id=user_id,
                    field=field_name,
                    old_value=_to_jsonb(old_value),
                    new_value=_to_jsonb(serialized_new),
                )
                self._session.add(edit)
                # Feld am ORM-Objekt setzen - mit der serialisierten Form,
                # damit die JSONB-Spalte auch beim UPDATE JSON-safe ist.
                setattr(invoice, field_name, serialized_new)
                continue

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
            setattr(invoice, field_name, new_value)

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
