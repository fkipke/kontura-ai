"""Factory: liefert die richtige AIProvider-Implementation basierend auf Settings.

Senior-Detail: der zurueckgegebene Provider ist IMMER ein AuditedAIProvider,
der den eigentlichen Provider (OpenAI, Azure, ...) umschliesst. Damit wird
JEDER Call automatisch ge-auditet.
"""

from functools import lru_cache

from kontura.ai.audit import AuditedAIProvider
from kontura.ai.base import AIProvider
from kontura.ai.openai_provider import OpenAIProvider
from kontura.core.config import settings


@lru_cache(maxsize=1)
def get_ai_provider() -> AIProvider:
    """Liefert die konfigurierte AIProvider-Instanz (Singleton via lru_cache).

    Welcher Provider zurueckkommt, wird via env-var AI_PROVIDER gesteuert.
    Dev-Default: 'openai' (siehe core.config.Settings).
    Wird IMMER mit Audit-Decorator umhuellt.
    """
    provider_name = settings.ai_provider.lower()

    real_provider: AIProvider
    if provider_name == "openai":
        real_provider = OpenAIProvider(
            api_key=settings.openai_api_key,
            embedding_model=settings.openai_embedding_model,
            chat_model=settings.openai_chat_model,
        )
    else:
        # Spaeter: azure, ollama, mistral
        raise ValueError(
            f"Unbekannter AI_PROVIDER '{provider_name}'. Aktuell unterstuetzt: 'openai'."
        )

    return AuditedAIProvider(wrapped=real_provider)
