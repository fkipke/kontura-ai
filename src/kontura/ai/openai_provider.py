"""OpenAI-Implementation des AIProvider-Interfaces.

Nutzt das offizielle openai-Python-SDK (>= 1.50, async).
Konfiguration via Settings (API-Key, Modelle).

Hinweis: Datenfluss geht aktuell zu OpenAI USA. Fuer Production-SaaS
mit DSGVO-Compliance siehe spaetere Provider (Azure OpenAI EU, Ollama).
"""

from typing import cast

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from kontura.ai.base import ChatMessage

# Embedding-Dimensionen der OpenAI-Modelle (Stand 2026).
# Quelle: https://platform.openai.com/docs/guides/embeddings
_EMBEDDING_DIMENSIONS: dict[str, int] = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}


class OpenAIProvider:
    """OpenAI-Implementation des AIProvider-Protocols."""

    def __init__(
        self,
        api_key: str,
        embedding_model: str = "text-embedding-3-small",
        chat_model: str = "gpt-4o-mini",
    ) -> None:
        if not api_key:
            raise ValueError("OPENAI_API_KEY ist nicht gesetzt")
        if embedding_model not in _EMBEDDING_DIMENSIONS:
            raise ValueError(
                f"Unbekanntes Embedding-Modell '{embedding_model}'. "
                f"Bekannt: {list(_EMBEDDING_DIMENSIONS.keys())}"
            )

        self._client = AsyncOpenAI(api_key=api_key)
        self._embedding_model = embedding_model
        self._chat_model = chat_model

    @property
    def name(self) -> str:
        return "openai"

    @property
    def embedding_dimension(self) -> int:
        return _EMBEDDING_DIMENSIONS[self._embedding_model]

    async def embed(self, text: str) -> list[float]:
        if not text or not text.strip():
            raise ValueError("embed(): text darf nicht leer sein")

        response = await self._client.embeddings.create(
            model=self._embedding_model,
            input=text,
        )
        return response.data[0].embedding

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> str:
        if not messages:
            raise ValueError("chat(): messages darf nicht leer sein")

        # OpenAI-SDK hat strikte TypedDicts pro Role. Wir konstruieren das Dict
        # passend und nutzen cast(), damit Mypy die Union-Aufloesung versteht.
        openai_messages: list[ChatCompletionMessageParam] = [
            cast(ChatCompletionMessageParam, {"role": m.role, "content": m.content})
            for m in messages
        ]

        response = await self._client.chat.completions.create(
            model=self._chat_model,
            messages=openai_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = response.choices[0].message.content
        if content is None:
            raise RuntimeError("OpenAI lieferte leere Antwort zurueck")
        return content
