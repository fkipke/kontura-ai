"""Schemas fuer DATEV-Export-Service."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import uuid

from pydantic import BaseModel, ConfigDict


@dataclass(frozen=True)
class DatevExportResult:
    """Ergebnis eines DATEV-Exports inkl. Header-Metadaten."""

    content: bytes
    invoice_count: int
    skipped_count: int


class DatevExportPreviewInvoice(BaseModel):
    """Eine Rechnung, wie sie im DATEV-Export landen wuerde.

    Wird vom /preview-Endpoint zurueckgegeben. Inhaltlich aequivalent zu einer
    Zeile im Buchungsstapel-CSV, aber maschinen- *und* menschenlesbar serialisiert
    (Decimal als String, UUID als String, ISO-Datum) - damit das Frontend eine
    sauber gestylte Vorschautabelle rendern kann.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    invoice_number: str
    vendor_name: str
    invoice_date: date
    total_amount: Decimal
    net_amount: Decimal | None
    tax_amount: Decimal | None
    currency: str
    creditor_account: int
    expense_account: int


class DatevExportPreviewResponse(BaseModel):
    """Vollstaendige Vorschau eines DATEV-Exports inkl. Summary-Zahlen.

    Wird vom Frontend genutzt, um Nutzer*innen *vor* dem CSV-Download zu zeigen,
    welche Rechnungen, welche Konten und welche Summen im Buchungsstapel landen.
    """

    from_date: date
    to_date: date
    invoices: list[DatevExportPreviewInvoice]
    total_count: int
    skipped_outside_fiscal_year: int
    fiscal_year_start: date
    fiscal_year_end: date
    total_gross_amount: Decimal
    total_net_amount: Decimal
    total_tax_amount: Decimal
    consultant_number: int
    client_number: int
    default_expense_account: int
    default_creditor_account: int
    include_all_years: bool
