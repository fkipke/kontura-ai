"""KI-Provider-Interface.

Senior-Pattern: Protocol statt ABC (PEP 544).
- Provider-Klassen implementieren das Interface STRUKTURELL.
- Kein `class MyProvider(AIProvider)`-Zwang.
- Mypy checkt Konformitaet automatisch.

Wenn wir spaeter weitere Provider bauen (Azure, Ollama, Mistral),
muessen sie nur dieses Interface erfuellen - kein Zentral-Code aendert sich.
"""

from typing import Literal, Protocol, runtime_checkable

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
