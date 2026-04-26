"""Factory: liefert die richtige AIProvider-Implementation basierend auf Settings.

Zentraler Punkt fuer Provider-Wahl. Wenn spaeter Azure/Ollama dazukommen,
wird hier ein neuer Branch ergaenzt - Anwendungscode bleibt unveraendert.
"""

from functools import lru_cache

from kontura.ai.base import AIProvider
from kontura.ai.openai_provider import OpenAIProvider
from kontura.core.config import settings


@lru_cache(maxsize=1)
def get_ai_provider() -> AIProvider:
    """Liefert die konfigurierte AIProvider-Instanz (Singleton via lru_cache).

    Welcher Provider zurueckkommt, wird via env-var AI_PROVIDER gesteuert.
    Dev-Default: 'openai' (siehe core.config.Settings).
    """
    provider_name = settings.ai_provider.lower()

    if provider_name == "openai":
        return OpenAIProvider(
            api_key=settings.openai_api_key,
            embedding_model=settings.openai_embedding_model,
            chat_model=settings.openai_chat_model,
        )

    # Spaeter:
    # if provider_name == "azure":
    #     return AzureOpenAIProvider(...)
    # if provider_name == "ollama":
    #     return OllamaProvider(...)

    raise ValueError(f"Unbekannter AI_PROVIDER '{provider_name}'. Aktuell unterstuetzt: 'openai'.")
