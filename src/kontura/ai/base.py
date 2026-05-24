"""KI-Provider-Interface.

Senior-Pattern: Protocol statt ABC (PEP 544).
- Provider-Klassen implementieren das Interface STRUKTURELL.
- Kein `class MyProvider(AIProvider)`-Zwang.
- Mypy checkt Konformitaet automatisch.

Wenn wir spaeter weitere Provider bauen (Azure, Ollama, Mistral),
muessen sie nur dieses Interface erfuellen - kein Zentral-Code aendert sich.
"""

from __future__ import annotations

from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel


class ChatMessage(BaseModel):
    """Eine Nachricht in einem Chat-Verlauf."""

    role: Literal["system", "user", "assistant"]
    content: str


@runtime_checkable
class AIProvider(Protocol):
    """Abstraktes Interface fuer alle KI-Provider.

    Implementierende Klassen muessen folgende Properties + Methoden bereitstellen.
    `runtime_checkable` erlaubt isinstance()-Checks (fuer Tests).
    """

    @property
    def name(self) -> str:
        """Eindeutiger Provider-Name fuer Audit-Logs (z.B. 'openai', 'azure-openai')."""
        ...

    @property
    def embedding_dimension(self) -> int:
        """Vektor-Dimension der Embeddings (z.B. 1536 fuer text-embedding-3-small).

        Wichtig fuer DB-Schema - Vektor-Spalte braucht feste Dimension.
        """
        ...

    async def embed(self, text: str) -> list[float]:
        """Erzeugt einen Embedding-Vektor fuer den gegebenen Text."""
        ...

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> str:
        """Erzeugt eine Chat-Completion fuer die gegebenen Messages."""
        ...

    async def extract_structured(
        self,
        *,
        system_prompt: str,
        user_text: str | None,
        image_bytes_list: list[bytes],
        json_schema: dict[str, Any],
        model: str | None = None,
        temperature: float = 0.0,
    ) -> tuple[dict[str, Any], int, int]:
        """Extrahiert strukturierte Daten aus Text und/oder Bildern via Vision-LLM.

        Liefert (parsed_json, prompt_tokens, completion_tokens).
        Wirft RuntimeError bei API-Fehler oder ungueltigem JSON.

        image_bytes_list: JPEG oder PNG bytes pro Seite (z.B. aus PDF gerendert).
        json_schema: OpenAI-strict-kompatibles JSON-Schema fuer structured outputs.
        model: Modell-Override (optional). Default: settings.openai_vision_model.
        """
        ...
