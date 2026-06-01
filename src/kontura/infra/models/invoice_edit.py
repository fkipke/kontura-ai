"""InvoiceEdit-Modell: GoBD-konformer Audit-Trail fuer Rechnungsfelder.

Jede manuelle Aenderung an einem Invoice-Feld erzeugt einen Eintrag hier.
- Unveraenderlich (kein UPDATE, kein DELETE ausser cascade)
- tenant_id fuer mandantenisolierte History-Abfragen
- old_value/new_value als JSONB fuer flexible Wert-Typen (Decimal, String, Array)
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from kontura.infra.db import Base
from kontura.infra.models._mixins import UUIDPrimaryKeyMixin


class InvoiceEdit(UUIDPrimaryKeyMixin, Base):
    """Audit-Trail-Eintrag fuer eine manuelle Aenderung an einem Invoice-Feld."""

    __tablename__ = "invoice_edits"

    # Tenant-Isolation: analog zu allen anderen Tabellen
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)

    # Rechnung, auf die sich dieser Edit bezieht (CASCADE DELETE - kein Waiseneintrag)
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Wer hat editiert? (SET NULL - Audit muss ueberleben wenn User geloescht wird)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Welches Feld wurde geaendert? (z.B. "vendor_name", "total_amount", "line_items")
    field: Mapped[str] = mapped_column(String(64), nullable=False)

    # Vorheriger Wert als JSONB.
    # Skalare: {"value": "ACME GmbH"}, Arrays: gesamtes Array als Snapshot.
    old_value: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # Neuer Wert als JSONB (gleiches Format wie old_value).
    new_value: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # Zeitpunkt des Edits (immutabel, server-seitig gesetzt)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        # Performance-Index fuer History-Abfragen pro Rechnung im Tenant
        Index("ix_invoice_edits_tenant_invoice", "tenant_id", "invoice_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<InvoiceEdit id={self.id} invoice={self.invoice_id} "
            f"field={self.field!r} user={self.user_id}>"
        )
