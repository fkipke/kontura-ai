"""Pydantic-Schemas fuer die strukturierte Rechnungs-Extraktion.

Das LLM liefert JSON gemaess diesen Schemas. Pydantic validiert und castet
die Werte (z.B. String -> Decimal, String -> date).

Wichtig: model_json_schema() liefert das Schema fuer OpenAI structured outputs.
Der OpenAIProvider transformiert es in das strict-kompatible Format.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

from pydantic import BaseModel, Field, field_validator


class ExtractedLineItem(BaseModel):
    """Eine einzelne Rechnungsposition."""

    description: str
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    total_price: Decimal | None = None

    @field_validator("quantity", "unit_price", "total_price", mode="before")
    @classmethod
    def _coerce_decimal(cls, v: object) -> object:
        """Castet String-Zahlen zu Decimal. Wirft ValueError bei ungueltigem Wert."""
        if v is None or isinstance(v, Decimal):
            return v
        try:
            return Decimal(str(v))
        except InvalidOperation as exc:
            raise ValueError(f"Ungueltige Dezimalzahl: {v!r}") from exc


class ExtractedInvoiceData(BaseModel):
    """Strikte Schema-Definition fuer das LLM-Output.

    Wird als JSON-Schema an OpenAI gegeben. Pydantic validiert die Antwort
    und castet Typen (String -> Decimal, String -> date).

    Hard-Fail-Strategie: Bei nicht-castbaren Werten wirft Pydantic einen
    ValidationError, der zum 'failed'-Status der Extraktion fuehrt.
    """

    invoice_number: str = Field(..., description="Rechnungsnummer vom Lieferanten")
    vendor_name: str = Field(..., description="Name des Lieferanten/Rechnungsstellers")
    vendor_address: str | None = None
    invoice_date: date = Field(..., description="Rechnungsdatum im Format YYYY-MM-DD")
    due_date: date | None = None
    currency: str = Field(default="EUR", description="ISO-4217 Currency-Code")
    net_amount: Decimal | None = None
    tax_amount: Decimal | None = None
    total_amount: Decimal = Field(..., description="Brutto-Gesamtbetrag")
    line_items: list[ExtractedLineItem] = Field(default_factory=list)
    confidence_notes: str | None = Field(
        default=None, description="Optionale Hinweise vom LLM bei unsicheren Feldern"
    )

    @field_validator("net_amount", "tax_amount", "total_amount", mode="before")
    @classmethod
    def _coerce_decimal(cls, v: object) -> object:
        """Castet String-Zahlen zu Decimal. Wirft ValueError bei ungueltigem Wert."""
        if v is None or isinstance(v, Decimal):
            return v
        try:
            return Decimal(str(v))
        except InvalidOperation as exc:
            raise ValueError(f"Ungueltige Dezimalzahl: {v!r}") from exc

    @field_validator("invoice_date", "due_date", mode="before")
    @classmethod
    def _coerce_date(cls, v: object) -> object:
        """Castet String-Daten zu date. Wirft ValueError bei ungueltigem Format."""
        if v is None or isinstance(v, date):
            return v
        from datetime import date as dt_date

        try:
            return dt_date.fromisoformat(str(v))
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Ungueltige Datumsangabe: {v!r} (erwartet YYYY-MM-DD)") from exc
