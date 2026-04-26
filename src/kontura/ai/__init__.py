"""KI-Provider-Layer fuer Kontura AI.

Zentral fuer alle Embeddings & Chat-Calls.
Provider-agnostisch: heute OpenAI, spaeter Azure/Ollama/Mistral - ohne API-Bruch.
"""

from kontura.ai.base import AIProvider, ChatMessage
from kontura.ai.factory import get_ai_provider

__all__ = ["AIProvider", "ChatMessage", "get_ai_provider"]
