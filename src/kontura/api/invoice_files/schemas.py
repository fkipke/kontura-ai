"""Pydantic-Schemas fuer die InvoiceFile-API.

Trennt Input (Upload) von Output (Response) strikt.
Das deduplicated-Flag zeigt dem Client, ob die Datei neu war oder schon existierte.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


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
