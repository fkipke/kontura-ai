"""Invoice-Modell: Eingangsrechnung (tenant-isoliert)."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from kontura.infra.db import Base
from kontura.infra.models._mixins import TimestampMixin, UUIDPrimaryKeyMixin


class InvoiceStatus(StrEnum):
    """Lebenszyklus einer Eingangsrechnung in Kontura AI."""

    RECEIVED = "received"
    PROCESSING = "processing"
    BOOKED = "booked"
    ERROR = "error"


class Invoice(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Eingangsrechnung von einem Lieferanten - tenant-isoliert."""

    __tablename__ = "invoices"

    # Tenant-Isolation (K2): Jede Rechnung gehoert zu genau einem Mandanten.
    # Repository filtert IMMER nach tenant_id - so kann Tenant A nie Daten von B sehen.
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)

    # Externe Rechnungsnummer (vom Lieferanten vergeben).
    # KEIN Single-Index - der composite UniqueConstraint unten deckt Queries effizient ab.
    invoice_number: Mapped[str] = mapped_column(String(100), nullable=False)

    # Lieferant (spaeter: FK auf Vendor-Tabelle)
    vendor_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # Rechnungsdatum (NICHT zu verwechseln mit created_at)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Brutto-Gesamtbetrag (Decimal! Niemals Float fuer Geld!)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    # ISO 4217 Currency-Code (EUR, USD, CHF, ...)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")

    # Status im Verarbeitungs-Workflow
    status: Mapped[InvoiceStatus] = mapped_column(
        SAEnum(InvoiceStatus, name="invoice_status"),
        nullable=False,
        default=InvoiceStatus.RECEIVED,
        index=True,
    )

    # G2.1: Nettobetrag (nullable - Altdaten ohne Extraktion haben keinen Nettobetrag)
    net_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    # G2.1: Steuerbetrag (nullable - Altdaten ohne Extraktion haben keinen Steuerbetrag)
    tax_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    # G3.2: Optimistic Locking - wird bei jedem Edit inkrementiert
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    # G3.2: Buchhalter-Review-Flag - gesetzt wenn Buchhalter "Geprueft" klickt
    is_reviewed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    # G3.2: Zeitpunkt der letzten Pruefung (nullable - noch nicht geprueft)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # G3.2: Wer hat geprueft? (FK auf users.id, ON DELETE SET NULL - Audit bleibt erhalten)
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # G3.2: Editierbare Positionen als JSONB-Snapshot.
    # KI-Original bleibt in InvoiceFile.extraction_result (unveraenderlich, GoBD).
    line_items: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        # K4: invoice_number ist pro Tenant eindeutig (verhindert Doppel-Buchungen).
        # Composite-Index dient gleichzeitig als schneller Tenant-Filter
        # (leftmost-prefix tenant_id).
        UniqueConstraint("tenant_id", "invoice_number", name="uq_invoices_tenant_invoice_number"),
    )

    def __repr__(self) -> str:
        return (
            f"<Invoice id={self.id} tenant={self.tenant_id} "
            f"number={self.invoice_number!r} vendor={self.vendor_name!r} "
            f"amount={self.total_amount} {self.currency} status={self.status.value}>"
        )
