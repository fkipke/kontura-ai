"""Tests fuer den AuditedAIProvider.

Wir mocken sowohl den wrapped Provider als auch das AuditRepository.

Ergaenzte Tests (Etappe 3):
- ContextVar-Tenant landet im LLMAuditEntry.tenant_id
- Default = SYSTEM_TENANT, wenn kein Request-Kontext gesetzt ist
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from kontura.ai.audit.audited_provider import AuditedAIProvider
from kontura.ai.base import AIProvider, ChatMessage
from kontura.core.tenant import TenantContext, current_tenant_var


def _make_wrapped_provider() -> MagicMock:
    """Hilfs-Mock, der das AIProvider-Protocol erfuellt."""
    mock = MagicMock(spec=AIProvider)
    mock.name = "openai"
    mock.embedding_dimension = 1536
    mock._embedding_model = "text-embedding-3-small"
    mock._chat_model = "gpt-4o-mini"
    mock.embed = AsyncMock(return_value=[0.1, 0.2, 0.3])
    mock.chat = AsyncMock(return_value="Konto 6815")
    return mock


def test_audited_provider_exposes_wrapped_metadata() -> None:
    """name + embedding_dimension werden vom wrapped Provider durchgereicht."""
    wrapped = _make_wrapped_provider()
    audit_repo = MagicMock()
    audited = AuditedAIProvider(wrapped=wrapped, audit_repo=audit_repo)
    assert audited.name == "openai"
    assert audited.embedding_dimension == 1536


@pytest.mark.asyncio
async def test_embed_records_audit_entry_on_success() -> None:
    """embed() erzeugt einen LLMAuditEntry mit success=True."""
    wrapped = _make_wrapped_provider()
    audit_repo = MagicMock()
    audit_repo.save = AsyncMock()

    audited = AuditedAIProvider(wrapped=wrapped, audit_repo=audit_repo)
    result = await audited.embed("Telekom Rechnung")

    assert result == [0.1, 0.2, 0.3]
    audit_repo.save.assert_awaited_once()
    entry = audit_repo.save.await_args.args[0]
    assert entry.operation == "embed"
    assert entry.provider_name == "openai"
    assert entry.success is True
    assert entry.error_message is None
    assert entry.prompt_chars == len("Telekom Rechnung")


@pytest.mark.asyncio
async def test_embed_records_audit_entry_on_failure() -> None:
    """Bei Exception wird success=False geloggt, exception re-raised."""
    wrapped = _make_wrapped_provider()
    wrapped.embed = AsyncMock(side_effect=RuntimeError("API down"))
    audit_repo = MagicMock()
    audit_repo.save = AsyncMock()

    audited = AuditedAIProvider(wrapped=wrapped, audit_repo=audit_repo)
    with pytest.raises(RuntimeError, match="API down"):
        await audited.embed("Telekom Rechnung")

    audit_repo.save.assert_awaited_once()
    entry = audit_repo.save.await_args.args[0]
    assert entry.success is False
    assert "API down" in (entry.error_message or "")


@pytest.mark.asyncio
async def test_embed_masks_pii_in_audit_log() -> None:
    """Original-PII darf NICHT im prompt_text landen."""
    wrapped = _make_wrapped_provider()
    audit_repo = MagicMock()
    audit_repo.save = AsyncMock()

    audited = AuditedAIProvider(wrapped=wrapped, audit_repo=audit_repo)
    await audited.embed("Bitte zahlen auf DE89370400440532013000.")

    entry = audit_repo.save.await_args.args[0]
    assert "DE89370400440532013000" not in entry.prompt_text
    assert "[IBAN_1]" in entry.prompt_text


@pytest.mark.asyncio
async def test_chat_records_audit_entry_with_serialized_messages() -> None:
    """chat() loggt die Messages serialisiert (maskiert) als prompt_text."""
    wrapped = _make_wrapped_provider()
    audit_repo = MagicMock()
    audit_repo.save = AsyncMock()

    audited = AuditedAIProvider(wrapped=wrapped, audit_repo=audit_repo)
    result = await audited.chat(
        [
            ChatMessage(role="system", content="Du bist Buchhaltungs-KI."),
            ChatMessage(role="user", content="Welches Konto fuer ich@x.de?"),
        ]
    )

    assert result == "Konto 6815"
    entry = audit_repo.save.await_args.args[0]
    assert entry.operation == "chat"
    assert "ich@x.de" not in entry.prompt_text
    assert "[EMAIL_1]" in entry.prompt_text


@pytest.mark.asyncio
async def test_chat_records_failure_and_reraises() -> None:
    """chat()-Fehler werden geloggt + re-raised."""
    wrapped = _make_wrapped_provider()
    wrapped.chat = AsyncMock(side_effect=ValueError("rate limit"))
    audit_repo = MagicMock()
    audit_repo.save = AsyncMock()

    audited = AuditedAIProvider(wrapped=wrapped, audit_repo=audit_repo)
    with pytest.raises(ValueError, match="rate limit"):
        await audited.chat([ChatMessage(role="user", content="x")])

    entry = audit_repo.save.await_args.args[0]
    assert entry.success is False
    assert "rate limit" in (entry.error_message or "")


# ---------- ContextVar-Tenant-Propagation (Etappe 3) ----------


@pytest.mark.asyncio
async def test_audit_entry_picks_up_tenant_from_context_var() -> None:
    """KRITISCH: Tenant aus dem ContextVar landet automatisch in LLMAuditEntry.tenant_id."""
    wrapped = _make_wrapped_provider()
    audit_repo = MagicMock()
    audit_repo.save = AsyncMock()
    audited = AuditedAIProvider(wrapped=wrapped, audit_repo=audit_repo)

    tenant = TenantContext(tenant_id="acme-corp")
    token = current_tenant_var.set(tenant)
    try:
        await audited.embed("hello")
    finally:
        current_tenant_var.reset(token)

    entry = audit_repo.save.await_args.args[0]
    assert entry.tenant_id == "acme-corp"


@pytest.mark.asyncio
async def test_audit_entry_defaults_to_system_tenant_outside_request() -> None:
    """Calls ohne Request-Kontext (Smoke, Cron) werden mit tenant_id='system' geloggt."""
    wrapped = _make_wrapped_provider()
    audit_repo = MagicMock()
    audit_repo.save = AsyncMock()
    audited = AuditedAIProvider(wrapped=wrapped, audit_repo=audit_repo)

    # KEIN current_tenant_var.set(...) -> Default = SYSTEM_TENANT
    await audited.embed("hello from cron")

    entry = audit_repo.save.await_args.args[0]
    assert entry.tenant_id == "system"
