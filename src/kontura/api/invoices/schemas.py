"""Pydantic-Schemas fuer die Invoice-API.

Trennt strikt:
- InvoiceCreate: was der Client SCHICKEN darf (Input)
- InvoiceRead:   was die API ZURUECKGIBT (Output)

Niemals ORM-Modelle direkt rausgeben - das leakt interne Felder.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from kontura.infra.models.invoice import InvoiceStatus


class InvoiceCreate(BaseModel):
    """Eingabe: Client legt eine neue Rechnung an."""

    invoice_number: str = Field(
        ..., min_length=1, max_length=100, description="Externe Rechnungsnummer"
    )
    vendor_name: str = Field(..., min_length=1, max_length=255, description="Name des Lieferanten")
    invoice_date: date = Field(..., description="Rechnungsdatum (ISO-8601)")
    total_amount: Decimal = Field(
        ..., gt=0, max_digits=12, decimal_places=2, description="Brutto-Gesamtbetrag"
    )
    currency: str = Field(default="EUR", min_length=3, max_length=3, description="ISO 4217 Code")


class InvoiceRead(BaseModel):
    """Ausgabe: API liefert eine vollstaendige Rechnung."""

    model_config = ConfigDict(from_attributes=True)  # erlaubt .model_validate(orm_obj)

    id: uuid.UUID
    invoice_number: str
    vendor_name: str
    invoice_date: date
    total_amount: Decimal
    currency: str
    status: InvoiceStatus
    created_at: datetime
    updated_at: datetime
