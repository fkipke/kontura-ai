"""LLMAuditEntry-Modell: jeder LLM-Call wird hier persistiert.

Zweck:
- Compliance / DSGVO-Audits (welche Daten gingen wann an welchen Provider?)
- Cost-Tracking (Aufrufe pro Modell pro Tag)
- Debugging (Reproduktion von KI-Antworten in Production)

Wichtig: prompt_text wird IMMER nach PII-Masking gespeichert.
Original-PII darf hier NIE landen.
"""

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from kontura.infra.db import Base
from kontura.infra.models._mixins import TimestampMixin, UUIDPrimaryKeyMixin


class LLMAuditEntry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Ein einzelner LLM-Aufruf (embed oder chat)."""

    __tablename__ = "llm_audit_entries"

    # Welcher Provider wurde gerufen? (openai, azure, ollama, ...)
    provider_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # embed | chat
    operation: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    # Modell-Identifier (z.B. text-embedding-3-small, gpt-4o-mini)
    model: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Maskierter Prompt-Text (KEINE PII!). Bei chat: serialisierter Verlauf.
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)

    # Char-Counts als preiswerter Cost-Proxy (echte Tokens kommen spaeter via tiktoken)
    prompt_chars: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    response_chars: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Latenz in Millisekunden
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Erfolgreich? Bei False steht in error_message der Grund.
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<LLMAuditEntry id={self.id} provider={self.provider_name} "
            f"op={self.operation} model={self.model} success={self.success} "
            f"duration_ms={self.duration_ms}>"
        )
