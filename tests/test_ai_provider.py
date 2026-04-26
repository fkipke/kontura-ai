"""Tests fuer den AIProvider-Layer.

Wir mocken OpenAI - keine echten Calls in CI (Geld + Geschwindigkeit + Determinismus).
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from kontura.ai.base import AIProvider, ChatMessage
from kontura.ai.openai_provider import OpenAIProvider


def test_openai_provider_implements_interface() -> None:
    """OpenAIProvider muss strukturell das AIProvider-Protocol erfuellen."""
    provider = OpenAIProvider(api_key="sk-fake")
    assert isinstance(provider, AIProvider)


def test_openai_provider_name_and_dimension() -> None:
    """name + embedding_dimension liefern erwartete Werte."""
    provider = OpenAIProvider(api_key="sk-fake")
    assert provider.name == "openai"
    assert provider.embedding_dimension == 1536  # text-embedding-3-small


def test_openai_provider_rejects_empty_api_key() -> None:
    """Leerer API-Key -> ValueError."""
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        OpenAIProvider(api_key="")


def test_openai_provider_rejects_unknown_embedding_model() -> None:
    """Unbekanntes Embedding-Modell -> ValueError."""
    with pytest.raises(ValueError, match="Unbekanntes Embedding-Modell"):
        OpenAIProvider(api_key="sk-fake", embedding_model="some-fake-model")


@pytest.mark.asyncio
async def test_openai_provider_embed_calls_api() -> None:
    """embed() ruft die richtige OpenAI-API auf und gibt den Vektor zurueck."""
    provider = OpenAIProvider(api_key="sk-fake")

    mock_response = MagicMock()
    mock_response.data = [MagicMock(embedding=[0.1, 0.2, 0.3])]
    provider._client.embeddings.create = AsyncMock(return_value=mock_response)  # type: ignore[method-assign]

    vector = await provider.embed("Eine Rechnung von ACME.")

    assert vector == [0.1, 0.2, 0.3]
    provider._client.embeddings.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_openai_provider_embed_rejects_empty_text() -> None:
    """Leerer Text -> ValueError, kein API-Call."""
    provider = OpenAIProvider(api_key="sk-fake")
    with pytest.raises(ValueError, match="text darf nicht leer sein"):
        await provider.embed("")


@pytest.mark.asyncio
async def test_openai_provider_chat_returns_content() -> None:
    """chat() liefert den Content der Assistant-Antwort."""
    provider = OpenAIProvider(api_key="sk-fake")

    mock_message = MagicMock()
    mock_message.content = "Konto 6815 (Telekommunikation)"
    mock_choice = MagicMock(message=mock_message)
    mock_response = MagicMock(choices=[mock_choice])
    provider._client.chat.completions.create = AsyncMock(return_value=mock_response)  # type: ignore[method-assign]

    result = await provider.chat([ChatMessage(role="user", content="Welches Konto?")])

    assert result == "Konto 6815 (Telekommunikation)"


@pytest.mark.asyncio
async def test_openai_provider_chat_rejects_empty_messages() -> None:
    """Leere Message-Liste -> ValueError."""
    provider = OpenAIProvider(api_key="sk-fake")
    with pytest.raises(ValueError, match="messages darf nicht leer sein"):
        await provider.chat([])
