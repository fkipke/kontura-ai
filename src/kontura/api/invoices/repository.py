"""Repository fuer Invoice-Zugriffe (tenant-isoliert).

Senior-Konzept: Tenant-Filter zentral.
ALLE Methoden bekommen einen TenantContext und filtern IMMER nach tenant_id.
Kein Endpoint kann das vergessen - der TenantContext-Parameter ist Pflicht.
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from kontura.api.invoices.schemas import InvoiceCreate, InvoiceLineItem
from kontura.core.tenant import TenantContext
from kontura.infra.models.invoice import Invoice, InvoiceStatus
from kontura.infra.models.invoice_edit import InvoiceEdit
from kontura.infra.models.invoice_file import ExtractionMethod
from kontura.infra.models.user import User


def _serialize_line_items(items: Any) -> list[dict[str, Any]] | None:
    """Konvertiert eine Liste von InvoiceLineItem (Pydantic) in JSON-safe Dicts.

    JSONB-Spalten gehen via asyncpg durch json.dumps - Pydantic-Modelle
    sind dort NICHT serialisierbar. Wir muessen vor jedem JSONB-Write
    auf primitive Typen runter (Decimal -> str, etc.). mode="json" macht
    genau das.
    """
    if items is None:
        return None
    result: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, InvoiceLineItem):
            result.append(item.model_dump(mode="json"))
        elif isinstance(item, dict):
            # Defensive: falls schon dict, ggf. Decimals stringifizieren
            result.append({k: str(v) if isinstance(v, Decimal) else v for k, v in item.items()})
        else:
            # Fallback: pack non-dict, non-pydantic items into a dict wrapper
            result.append({"value": item})
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
    # bool(...) macht mypy gluecklich (sonst "Returning Any").
    return bool(_serialize_line_items(a) == _serialize_line_items(b))


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

    async def get_by_id_with_user_email(
        self, tenant: TenantContext, invoice_id: uuid.UUID
    ) -> tuple[Invoice, str | None] | None:
        """Liefert (Invoice, user_email) mit LEFT JOIN auf users.

        reviewed_by_user_email ist None wenn kein reviewer gesetzt oder User geloescht.
        """
        stmt = (
            select(Invoice, User.email)
            .outerjoin(User, User.id == Invoice.reviewed_by_user_id)
            .where(
                Invoice.id == invoice_id,
                Invoice.tenant_id == tenant.tenant_id,
            )
        )
        result = await self._session.execute(stmt)
        row = result.one_or_none()
        if row is None:
            return None
        invoice, email = row
        return invoice, email

    async def list_filtered(
        self,
        tenant: TenantContext,
        *,
        search: str | None = None,
        status_filter: list[InvoiceStatus] | None = None,
        reviewed_filter: bool | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        amount_min: Decimal | None = None,
        amount_max: Decimal | None = None,
        vendor_filter: list[str] | None = None,
        method_filter: list[str] | None = None,
        sort_by: Literal[
            "invoice_date", "created_at", "total_amount", "vendor_name", "invoice_number", "status"
        ] = "invoice_date",
        sort_order: Literal["asc", "desc"] = "desc",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Invoice], int]:
        """Gibt (page_items, total_count) zurueck. total_count fuer X-Total-Count Header."""
        # Tenant-Filter IMMER zuerst
        base_where = [Invoice.tenant_id == tenant.tenant_id]

        if search:
            pattern = f"%{search}%"
            base_where.append(
                Invoice.invoice_number.ilike(pattern) | Invoice.vendor_name.ilike(pattern)
            )

        if status_filter:
            base_where.append(Invoice.status.in_(status_filter))

        if reviewed_filter is not None:
            base_where.append(Invoice.is_reviewed == reviewed_filter)

        if date_from is not None:
            base_where.append(Invoice.invoice_date >= date_from)

        if date_to is not None:
            base_where.append(Invoice.invoice_date <= date_to)

        if amount_min is not None:
            base_where.append(Invoice.total_amount >= amount_min)

        if amount_max is not None:
            base_where.append(Invoice.total_amount <= amount_max)

        if vendor_filter:
            base_where.append(Invoice.vendor_name.in_(vendor_filter))

        if method_filter:
            from kontura.infra.models.invoice_file import InvoiceFile  # noqa: PLC0415

            # Filter invoices that have at least one file with matching extraction_method
            method_enum_vals = [ExtractionMethod(m) for m in method_filter]
            sub = (
                select(InvoiceFile.invoice_id)
                .where(InvoiceFile.extraction_method.in_(method_enum_vals))
                .where(InvoiceFile.invoice_id.is_not(None))
            )
            base_where.append(Invoice.id.in_(sub))

        # Total count (separate query, no LIMIT/OFFSET)
        count_stmt = select(func.count()).select_from(Invoice).where(*base_where)
        total: int = (await self._session.execute(count_stmt)).scalar_one()

        # Sort column (validated against Literal allowlist via type system)
        sort_col = getattr(Invoice, sort_by)
        order_expr = sort_col.asc() if sort_order == "asc" else sort_col.desc()

        # Data query
        data_stmt = (
            select(Invoice).where(*base_where).order_by(order_expr).limit(limit).offset(offset)
        )
        rows = (await self._session.execute(data_stmt)).scalars().all()
        return list(rows), total

    async def list_distinct_vendors(self, tenant: TenantContext) -> list[str]:
        """Gibt sortierte, eindeutige Lieferantennamen des Tenants zurueck."""
        stmt = (
            select(Invoice.vendor_name)
            .where(Invoice.tenant_id == tenant.tenant_id)
            .where(Invoice.vendor_name.is_not(None))
            .where(Invoice.vendor_name != "")
            .distinct()
            .order_by(Invoice.vendor_name.asc())
        )
        result = await self._session.execute(stmt)
        return [row[0] for row in result.all()]

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
