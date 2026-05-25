"""Pydantic-Schemas fuer die InvoiceFile-API.

Trennt Input (Upload) von Output (Response) strikt.
Das deduplicated-Flag zeigt dem Client, ob die Datei neu war oder schon existierte.
G2.1: extraction_status zeigt dem User direkt den KI-Extraktionsstatus.
"""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from kontura.infra.models.invoice_file import ExtractionStatus


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
