"""KI-Provider-Layer fuer Kontura AI.

Zentral fuer alle Embeddings, Chat-Calls und PII-Masking.
Provider-agnostisch: heute OpenAI, spaeter Azure/Ollama/Mistral - ohne API-Bruch.
"""

from kontura.ai.base import AIProvider, ChatMessage
from kontura.ai.factory import get_ai_provider
from kontura.ai.pii import MaskedText, PIIEntity, PIIMasker, RegexMasker

__all__ = [
    "AIProvider",
    "ChatMessage",
    "MaskedText",
    "PIIEntity",
    "PIIMasker",
    "RegexMasker",
    "get_ai_provider",
]
