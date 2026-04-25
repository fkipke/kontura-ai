"""Invoice-Modell: Eingangsrechnung."""

from datetime import date
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import Date, Numeric, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from kontura.infra.db import Base
from kontura.infra.models._mixins import TimestampMixin, UUIDPrimaryKeyMixin


class InvoiceStatus(StrEnum):
    """Lebenszyklus einer Eingangsrechnung in Kontura AI."""

    RECEIVED = "received"  # Eingang erfasst, noch nicht verarbeitet
    PROCESSING = "processing"  # Wird durch KI extrahiert / kontiert
    BOOKED = "booked"  # Erfolgreich an SAP/DATEV uebermittelt
    ERROR = "error"  # Fehler bei Verarbeitung, manuelle Pruefung noetig


class Invoice(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Eingangsrechnung von einem Lieferanten."""

    __tablename__ = "invoices"

    # Externe Rechnungsnummer (vom Lieferanten vergeben)
    invoice_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Lieferant (spaeter: FK auf Vendor-Tabelle)
    vendor_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # Rechnungsdatum (NICHT zu verwechseln mit created_at)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Brutto-Gesamtbetrag (Decimal! Niemals Float fuer Geld!)
    # Numeric(12, 2) = max. 9_999_999_999.99 EUR
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

    def __repr__(self) -> str:
        return (
            f"<Invoice id={self.id} number={self.invoice_number!r} "
            f"vendor={self.vendor_name!r} amount={self.total_amount} {self.currency} "
            f"status={self.status.value}>"
        )
