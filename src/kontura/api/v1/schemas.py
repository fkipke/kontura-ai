"""Pydantic-Schemas fuer die V1 API.

Senior-Regel: ORM-Objekte verlassen NIEMALS die API-Schicht.
Wir mappen immer auf eigene Response-Modelle - so sind interne Aenderungen
am DB-Schema unsichtbar fuer API-Consumer.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EmbeddingResponse(BaseModel):
    """Antwort nach erfolgreicher Embedding-Erzeugung."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="ID des Embedding-Eintrags")
    invoice_id: UUID = Field(description="ID der zugehoerigen Rechnung")
    model: str = Field(description="Verwendetes Embedding-Modell")
    source_text: str = Field(
        description="PII-maskierter Quelltext, der embedded wurde",
    )
    dimension: int = Field(description="Anzahl Float-Werte im Vektor")
    created_at: datetime = Field(description="Zeitpunkt der Erzeugung (UTC)")


class SimilarInvoiceResponse(BaseModel):
    """Ein Treffer einer Aehnlichkeits-Suche."""

    invoice_id: UUID = Field(description="ID der gefundenen Rechnung")
    embedding_id: UUID = Field(description="ID des Embedding-Eintrags")
    distance: float = Field(
        description="Cosine-Distanz (0.0 = identisch, 2.0 = entgegengesetzt). "
        "Werte <0.3 sind sehr aehnlich, >0.7 unverwandt.",
    )
    source_text: str = Field(description="PII-maskierter Quelltext der Rechnung")


class SimilarInvoicesResponse(BaseModel):
    """Antwort fuer eine Aehnlichkeits-Suche."""

    results: list[SimilarInvoiceResponse]
    count: int = Field(description="Anzahl Treffer")


class ErrorResponse(BaseModel):
    """Standardisierte Fehlerantwort."""

    detail: str
