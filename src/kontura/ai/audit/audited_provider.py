"""AuditedAIProvider: Decorator, der jeden LLM-Call in der DB persistiert.

Senior-Pattern: Wrappt einen beliebigen AIProvider und implementiert das gleiche
Interface. Anwendungs-Code merkt nichts vom Audit-Layer.

Defense-in-Depth (K1): Der WRAPPED Provider bekommt IMMER den maskierten Text.
Damit ist es egal, wer 'AuditedAIProvider' aufruft - PII verlaesst diese Schicht
NIEMALS unmaskiert. Die Maskierung im EmbeddingService ist eine zusaetzliche
Verteidigungslinie, kein Single-Point-of-Failure.

Tenant-Propagation: Der aktive Tenant wird per ContextVar gelesen
(siehe core.tenant.current_tenant_var). Damit muss kein einziger Aufrufer
seinen Tenant durch die Provider-Signatur durchschleifen.

G2.1-Erweiterung: extract_structured() wird ebenfalls ge-auditet.
Hinweis zu Image-Bytes: Diese werden NICHT im prompt_text gespeichert
(weder b64 noch raw). Nur System-Prompt und user_text werden maskiert und
im Audit festgehalten. Bild-Inhalte sind fluechtiger Kontext, kein PII-Text.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from kontura.ai.audit.repository import AuditRepository
from kontura.ai.base import AIProvider, ChatMessage
from kontura.ai.pii import PIIMasker, RegexMasker
from kontura.core.tenant import get_current_tenant
from kontura.infra.models import LLMAuditEntry

logger = logging.getLogger(__name__)


class AuditedAIProvider:
    """Wrappt einen AIProvider und persistiert jeden Call als LLMAuditEntry."""

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
        masked_messages_for_provider: list[ChatMessage] = [
            ChatMessage(role=m.role, content=self._masker.mask(m.content).masked_text)
            for m in messages
        ]
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
        """Delegiert an den wrapped Provider und schreibt einen Audit-Eintrag.

        PII-Masking: system_prompt und user_text werden maskiert.
        Image-Bytes werden NICHT im Audit gespeichert (nur Metadaten: Anzahl Seiten).
        """
        masked_system = self._masker.mask(system_prompt).masked_text
        masked_user = self._masker.mask(user_text).masked_text if user_text else ""

        prompt_summary = json.dumps(
            {
                "system": masked_system,
                "user_text": masked_user,
                "image_pages": len(image_bytes_list),
            },
            ensure_ascii=False,
        )
        prompt_chars = len(system_prompt) + len(user_text or "")

        start = time.perf_counter()
        success = True
        error_message: str | None = None
        prompt_tokens = 0
        completion_tokens = 0
        try:
            result_dict, prompt_tokens, completion_tokens = await self._wrapped.extract_structured(
                system_prompt=system_prompt,
                user_text=user_text,
                image_bytes_list=image_bytes_list,
                json_schema=json_schema,
                model=model,
                temperature=temperature,
            )
            return result_dict, prompt_tokens, completion_tokens
        except Exception as exc:
            success = False
            error_message = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            duration_ms = int((time.perf_counter() - start) * 1000)
            await self._record(
                operation="extract",
                model=model or self._vision_model_name(),
                prompt_text=prompt_summary,
                prompt_chars=prompt_tokens or prompt_chars,
                response_chars=completion_tokens,
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
        # Tenant aus dem ContextVar lesen (gesetzt vom get_tenant-Dependency).
        # Default = SYSTEM_TENANT, falls ausserhalb eines HTTP-Requests gerufen.
        tenant = get_current_tenant()

        entry = LLMAuditEntry(
            tenant_id=tenant.tenant_id,
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
        return getattr(self._wrapped, "_embedding_model", "unknown")

    def _chat_model_name(self) -> str:
        return getattr(self._wrapped, "_chat_model", "unknown")

    def _vision_model_name(self) -> str:
        return getattr(self._wrapped, "_vision_model", "unknown")
