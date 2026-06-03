"""Pydantic-Schemas fuer die InvoiceFile-API.

Trennt Input (Upload) von Output (Response) strikt.
Das deduplicated-Flag zeigt dem Client, ob die Datei neu war oder schon existierte.
G2.1: extraction_status zeigt dem User direkt den KI-Extraktionsstatus.
G3.1b: Denormalisierte Extraction-Felder fuer Listings (n+1 vermeiden).
"""

import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict

from kontura.infra.models.invoice_file import ExtractionStatus

if TYPE_CHECKING:
    from kontura.infra.models.invoice_file import InvoiceFile


def _coerce_str(value: Any) -> str | None:
    """Wandelt einen Wert in str um, gibt None bei Fehler zurueck."""
    if value is None:
        return None
    try:
        return str(value).strip() or None
    except Exception:  # noqa: BLE001
        return None


def _coerce_date(value: Any) -> date | None:
    """Wandelt einen ISO-Date-String oder date-Objekt in date um, gibt None bei Fehler zurueck."""
    if value is None:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


def _coerce_decimal(value: Any) -> Decimal | None:
    """Wandelt einen Wert in Decimal um, gibt None bei Fehler zurueck."""
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


class InvoiceFileResponse(BaseModel):
    """Antwort-Schema fuer eine hochgeladene oder abgerufene Rechnungsdatei."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    mime_type: str
    size_bytes: int
    sha256: str
    created_at: datetime
    # Zeigt ob die Datei bereits existierte (Deduplication) oder neu hochgeladen wurde
    deduplicated: bool = False
    # G2.1: KI-Extraktionsstatus (fuer UX: User sieht direkt was schon ausgewertet ist)
    extraction_status: ExtractionStatus = ExtractionStatus.PENDING
    extraction_method: str | None = None
    # G3.1b: Denormalisierte Extraction-Felder fuer Listings (n+1 vermeiden).
    # Werden nur befuellt, wenn extraction_status == "completed".
    vendor_name: str | None = None
    invoice_date: date | None = None
    total_amount: Decimal | None = None
    currency: str | None = None

    @classmethod
    def from_model(cls, invoice_file: "InvoiceFile") -> "InvoiceFileResponse":
        """Projiziert ein InvoiceFile-Modell inkl. denormalisierter Extraction-Felder."""
        base = cls.model_validate(invoice_file).model_copy(
            update={"extraction_method": getattr(invoice_file, "extraction_method", None)}
        )
        if invoice_file.extraction_status.value == "completed" and isinstance(
            invoice_file.extraction_result, dict
        ):
            result = invoice_file.extraction_result
            # Werte vorsichtig parsen — LLM-Output kann Strings statt nativer Typen liefern.
            # Bei Parse-Fehler: Feld bleibt None (keine Exception nach oben).
            return base.model_copy(
                update={
                    "vendor_name": _coerce_str(result.get("vendor_name")),
                    "invoice_date": _coerce_date(result.get("invoice_date")),
                    "total_amount": _coerce_decimal(result.get("total_amount")),
                    "currency": _coerce_str(result.get("currency")),
                }
            )
        return base


class ExtractionStatusResponse(BaseModel):
    """Antwort-Schema fuer den Extraction-Status-Endpoint."""

    model_config = ConfigDict(from_attributes=True)

    file_id: uuid.UUID
    status: Literal["pending", "processing", "completed", "failed"]
    attempts: int
    extracted_at: datetime | None
    error: str | None
    result: dict[str, Any] | None
    linked_invoice_id: uuid.UUID | None
