"""AuditedAIProvider: Decorator, der jeden LLM-Call in der DB persistiert.

Senior-Pattern: Wrappt einen beliebigen AIProvider und implementiert das gleiche
Interface. Anwendungs-Code merkt nichts vom Audit-Layer.

Defense-in-Depth (K1): Der WRAPPED Provider bekommt IMMER den maskierten Text.
Damit ist es egal, wer 'AuditedAIProvider' aufruft - PII verlaesst diese Schicht
NIEMALS unmaskiert. Die Maskierung im EmbeddingService ist eine zusaetzliche
Verteidigungslinie, kein Single-Point-of-Failure.
"""

from __future__ import annotations

import json
import logging
import time

from kontura.ai.audit.repository import AuditRepository
from kontura.ai.base import AIProvider, ChatMessage
from kontura.ai.pii import PIIMasker, RegexMasker
from kontura.infra.models import LLMAuditEntry

logger = logging.getLogger(__name__)


class AuditedAIProvider:
    """Wrappt einen AIProvider und persistiert jeden Call als LLMAuditEntry.

    Effekte:
    - PII-Masking VOR jedem Provider-Call (Defense-in-Depth).
    - Audit-Eintrag mit Modell, Latenz, Erfolg/Fehler in DB nach jedem Call.
    - Bei Fehler: Eintrag mit success=False, exception wird re-raised.

    Implementiert das AIProvider-Protocol strukturell (gleiche Signatur).
    """

    def __init__(
        self,
        wrapped: AIProvider,
        audit_repo: AuditRepository | None = None,
        masker: PIIMasker | None = None,
    ) -> None:
        self._wrapped = wrapped
        self._audit_repo = audit_repo or AuditRepository()
        self._masker = masker or RegexMasker()

    @property
    def name(self) -> str:
        return self._wrapped.name

    @property
    def embedding_dimension(self) -> int:
        return self._wrapped.embedding_dimension

    @property
    def audit_repo(self) -> AuditRepository:
        """Exponiert das Audit-Repository (z.B. fuer Lifespan-Shutdown)."""
        return self._audit_repo

    async def embed(self, text: str) -> list[float]:
        # K1-Fix: Provider bekommt den MASKIERTEN Text - kein PII-Leak nach extern.
        masked = self._masker.mask(text)
        start = time.perf_counter()
        success = True
        error_message: str | None = None
        response_chars = 0
        try:
            vector = await self._wrapped.embed(masked.masked_text)
            response_chars = len(vector)
            return vector
        except Exception as exc:
            success = False
            error_message = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            duration_ms = int((time.perf_counter() - start) * 1000)
            await self._record(
                operation="embed",
                model=self._embedding_model_name(),
                prompt_text=masked.masked_text,
                prompt_chars=len(text),
                response_chars=response_chars,
                duration_ms=duration_ms,
                success=success,
                error_message=error_message,
            )

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> str:
        # K1-Fix: Auch der Chat-Provider bekommt nur maskierte Messages.
        masked_messages_for_provider: list[ChatMessage] = [
            ChatMessage(role=m.role, content=self._masker.mask(m.content).masked_text)
            for m in messages
        ]
        # Fuer das Audit-Log serialisieren wir die maskierten Messages.
        prompt_serialized = json.dumps(
            [{"role": m.role, "content": m.content} for m in masked_messages_for_provider],
            ensure_ascii=False,
        )

        start = time.perf_counter()
        success = True
        error_message: str | None = None
        result = ""
        try:
            result = await self._wrapped.chat(
                masked_messages_for_provider,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return result
        except Exception as exc:
            success = False
            error_message = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            duration_ms = int((time.perf_counter() - start) * 1000)
            await self._record(
                operation="chat",
                model=self._chat_model_name(),
                prompt_text=prompt_serialized,
                prompt_chars=sum(len(m.content) for m in messages),
                response_chars=len(result),
                duration_ms=duration_ms,
                success=success,
                error_message=error_message,
            )

    # ----- Helpers -----

    async def _record(
        self,
        *,
        operation: str,
        model: str,
        prompt_text: str,
        prompt_chars: int,
        response_chars: int,
        duration_ms: int,
        success: bool,
        error_message: str | None,
    ) -> None:
        entry = LLMAuditEntry(
            provider_name=self._wrapped.name,
            operation=operation,
            model=model,
            prompt_text=prompt_text,
            prompt_chars=prompt_chars,
            response_chars=response_chars,
            duration_ms=duration_ms,
            success=success,
            error_message=error_message,
        )
        await self._audit_repo.save(entry)

    def _embedding_model_name(self) -> str:
        # Best-effort: Provider-Implementations haben oft _embedding_model.
        return getattr(self._wrapped, "_embedding_model", "unknown")

    def _chat_model_name(self) -> str:
        return getattr(self._wrapped, "_chat_model", "unknown")
