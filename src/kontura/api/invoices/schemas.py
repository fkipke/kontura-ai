"""Pydantic-Schemas fuer die Invoice-API (G3.2: Edit + Audit-Trail).

Trennt strikt:
- InvoiceCreate:        was der Client beim Anlegen schicken darf (Input)
- InvoiceRead:          was die Liste-Endpoints zurueckgeben (Output, kompakt)
- InvoiceUpdateRequest: was der Client beim PATCH schicken darf (G3.2)
- InvoiceResponse:      vollstaendiges Response-Objekt inkl. Warnings (G3.2)
- ValidationWarning:    Soft-Validation-Hinweis (nicht-blockierend)

Niemals ORM-Modelle direkt rausgeben - das leakt interne Felder.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

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
    """Ausgabe: API liefert eine vollstaendige Rechnung (kompakt, ohne Warnings)."""

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


# ============================================================
# G3.2: Edit-Request + vollstaendige Response
# ============================================================


class InvoiceLineItem(BaseModel):
    """Einzelne Rechnungsposition."""

    description: str | None = None
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    total_price: Decimal | None = None


class InvoiceUpdateRequest(BaseModel):
    """PATCH-Body. Alle Felder optional - nur gesetzte Felder werden geupdated.

    expected_version ist Pflicht fuer Optimistic Locking.
    Felder, die nicht im Body auftauchen, bleiben unveraendert.
    """

    expected_version: int = Field(..., ge=1, description="Aktuelle Version (Optimistic Lock)")
    vendor_name: str | None = Field(None, min_length=1, max_length=255)
    invoice_number: str | None = Field(None, min_length=1, max_length=100)
    invoice_date: date | None = None
    net_amount: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=2)
    tax_amount: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=2)
    total_amount: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=2)
    currency: str | None = Field(None, min_length=3, max_length=3)
    line_items: list[InvoiceLineItem] | None = None
    creditor_account_number: int | None = Field(None, ge=10000, le=999999)
    is_reviewed: bool | None = None


class ValidationWarning(BaseModel):
    """Soft-Validation-Hinweis: nicht-blockierend, informativ."""

    code: Literal["ust_total_mismatch", "future_invoice_date", "unusual_currency"]
    message: str
    field: str | None = None


class InvoiceResponse(BaseModel):
    """Vollstaendiges Invoice-Objekt inkl. Optimistic-Lock-Version und Warnings.

    Wird vom PATCH-Endpoint zurueckgegeben. Validation-Warnings sind IMMER enthalten
    (auch als leeres Array bei keinen Warnungen).
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: str
    version: int
    is_reviewed: bool
    reviewed_at: datetime | None
    reviewed_by_user_id: uuid.UUID | None
    vendor_name: str
    invoice_number: str
    invoice_date: date
    net_amount: Decimal | None
    tax_amount: Decimal | None
    total_amount: Decimal
    currency: str
    line_items: list[InvoiceLineItem] | None
    status: InvoiceStatus
    created_at: datetime
    updated_at: datetime
    validation_warnings: list[ValidationWarning] = Field(default_factory=list)

    @classmethod
    def from_invoice(
        cls, invoice: object, warnings: list[ValidationWarning] | None = None
    ) -> "InvoiceResponse":
        """Erzeugt InvoiceResponse aus ORM-Objekt + optionalen Warnings."""
        obj = cls.model_validate(invoice)
        if warnings:
            obj.validation_warnings = warnings
        return obj
