"""OpenAI-Implementation des AIProvider-Interfaces.

Nutzt das offizielle openai-Python-SDK (>= 1.50, async).
Konfiguration via Settings (API-Key, Modelle).

Hinweis: Datenfluss geht aktuell zu OpenAI USA. Fuer Production-SaaS
mit DSGVO-Compliance siehe spaetere Provider (Azure OpenAI EU, Ollama).
"""

from __future__ import annotations

import base64
import copy
import json
from typing import Any, cast

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


def _make_strict_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Transformiert ein Pydantic-JSON-Schema in ein OpenAI-strict-kompatibles Schema.

    OpenAI strict mode erfordert:
    - Alle Properties in 'required' (auch optionale)
    - 'additionalProperties: false' auf allen Objekt-Typen
    - Verarbeitet rekursiv $defs, anyOf, items und properties.
    """
    schema = copy.deepcopy(schema)

    def _process(obj: dict[str, Any]) -> None:
        # $defs immer zuerst verarbeiten
        if "$defs" in obj:
            for def_schema in obj["$defs"].values():
                _process(def_schema)

        if obj.get("type") == "object" or "properties" in obj:
            props = obj.get("properties", {})
            obj["required"] = list(props.keys())
            obj["additionalProperties"] = False
            for prop_schema in props.values():
                _process(prop_schema)

        if "anyOf" in obj:
            for variant in obj["anyOf"]:
                _process(variant)

        if "items" in obj and isinstance(obj["items"], dict):
            _process(obj["items"])

    _process(schema)
    return schema


class OpenAIProvider:
    """OpenAI-Implementation des AIProvider-Protocols."""

    def __init__(
        self,
        api_key: str,
        embedding_model: str = "text-embedding-3-small",
        chat_model: str = "gpt-4o-mini",
        vision_model: str = "gpt-4o",
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
        self._vision_model = vision_model

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
        """Extrahiert strukturierte Daten aus Bildern/Text via GPT-4o Vision.

        Verwendet OpenAI structured outputs (response_format=json_schema, strict=True)
        fuer garantiert valides JSON ohne Regex-Parserei.

        DSGVO-Hinweis: Image-Bytes werden NICHT im Audit gespeichert.
        Der Prompt-Text (system_prompt + user_text) wird im Caller PII-maskiert,
        bevor er in den Audit-Log geht. Bild-Inhalte werden nur an OpenAI gesendet.
        """
        effective_model = model or self._vision_model
        strict_schema = _make_strict_schema(json_schema)

        # User-Message mit Text + Bildern aufbauen
        content_parts: list[dict[str, Any]] = []
        if user_text:
            content_parts.append({"type": "text", "text": user_text})

        for img_bytes in image_bytes_list:
            b64 = base64.b64encode(img_bytes).decode("ascii")
            content_parts.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "high"},
                }
            )

        openai_messages: list[ChatCompletionMessageParam] = [
            cast(ChatCompletionMessageParam, {"role": "system", "content": system_prompt}),
            cast(ChatCompletionMessageParam, {"role": "user", "content": content_parts}),
        ]

        response = await self._client.chat.completions.create(
            model=effective_model,
            messages=openai_messages,
            temperature=temperature,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "invoice_extraction",
                    "schema": strict_schema,
                    "strict": True,
                },
            },
        )

        raw_content = response.choices[0].message.content
        if raw_content is None:
            raise RuntimeError("OpenAI lieferte leere Extraction-Antwort zurueck")

        try:
            parsed: dict[str, Any] = json.loads(raw_content)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"OpenAI lieferte kein valides JSON: {exc}") from exc

        prompt_tokens = response.usage.prompt_tokens if response.usage else 0
        completion_tokens = response.usage.completion_tokens if response.usage else 0

        return parsed, prompt_tokens, completion_tokens
