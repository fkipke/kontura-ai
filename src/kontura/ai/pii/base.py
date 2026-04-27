"""Interface + Datenmodelle fuer PII-Masking."""

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field


class PIIEntity(BaseModel):
    """Eine erkannte PII-Stelle im Originaltext."""

    entity_type: str = Field(description="z.B. 'IBAN', 'PERSON', 'EMAIL'")
    placeholder: str = Field(description="Token im maskierten Text, z.B. '[IBAN_1]'")
    original_value: str = Field(description="Der echte Wert (NICHT loggen!)")


class MaskedText(BaseModel):
    """Ergebnis einer Masking-Operation."""

    masked_text: str = Field(description="Text mit Platzhaltern statt PII")
    entities: list[PIIEntity] = Field(
        default_factory=list,
        description="Liste der ersetzten Werte fuer optionalen Reverse-Mapping",
    )

    def unmask(self, llm_response: str) -> str:
        """Ersetzt Platzhalter in einer LLM-Antwort wieder durch Originalwerte.

        Use-Case: Wenn die LLM-Antwort z.B. einen Platzhalter wie '[IBAN_1]'
        enthaelt, koennen wir den Originalwert beim User wieder einsetzen.

        Sicherheitshinweis: Reverse-Mapping NUR im Antwort-Pfad, niemals in Logs.
        """
        result = llm_response
        for entity in self.entities:
            result = result.replace(entity.placeholder, entity.original_value)
        return result


@runtime_checkable
class PIIMasker(Protocol):
    """Abstraktes Interface fuer PII-Masker."""

    def mask(self, text: str) -> MaskedText:
        """Erkennt und maskiert PII im Text.

        Args:
            text: Originaltext (z.B. Rechnungsbeschreibung).

        Returns:
            MaskedText mit Platzhaltern + Mapping fuer optionales Unmask.
        """
        ...
