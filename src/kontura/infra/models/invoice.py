"""Invoice-Modell: Eingangsrechnung (tenant-isoliert)."""

from datetime import date
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import Date, Numeric, String, UniqueConstraint
from sqlalchemy import Enum as SAEnum
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
