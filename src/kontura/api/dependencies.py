"""Shared FastAPI-Dependencies fuer alle API-Versionen.

Senior-Konzept: Tenant-Resolution aus JWT (nicht mehr aus Header)
=================================================================
Nach Phase E ist der einzige offizielle Weg, sich zu authentifizieren:
    Authorization: Bearer <JWT>

Aus dem JWT lesen wir tenant_id + user_id und setzen den ContextVar.
Damit kennt jede Cross-cutting Component (AuditedAIProvider, Logger) den
Tenant - ohne dass jeder Endpoint ihn als Parameter durchschleifen muss.

Senior-Detail: Try/Finally + ContextVar.reset()
================================================
Generator-Dependency garantiert sauberen ContextVar-Reset am Request-Ende.
Ohne Reset wuerde der Tenant in den naechsten Request 'lecken', der dieselbe
Worker-Coroutine nutzt - klassischer Multi-Tenant-Bug.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncEngine

from kontura.ai.base import AIProvider
from kontura.ai.factory import get_ai_provider

# Explicit `X as X` re-export pattern is required by mypy --strict (PEP 484).
# Tests and other modules import `get_settings` from this module as a stable
# DI seam; without the alias mypy treats the import as module-private and
# raises `attr-defined`. Settings and `settings` are also re-exported so the
# DI surface for FastAPI dependencies stays in one place.
from kontura.core.config import Settings as Settings
from kontura.core.config import get_settings as get_settings
from kontura.core.config import settings as settings
from kontura.core.jwt import TokenError, TokenPayload, decode_token
from kontura.core.tenant import TenantContext, current_tenant_var
from kontura.infra.db import engine as _module_engine
from kontura.infra.email import ConsoleEmailSender, EmailSender, SmtpEmailSender
from kontura.infra.storage import LocalFilesystemStorage

# HTTPBearer macht aus 'Authorization: Bearer ...' automatisch ein Credentials-Object.
# auto_error=False, damit WIR die Fehlermeldung kontrollieren (klare 401-Texte).
_bearer = HTTPBearer(auto_error=False, description="JWT aus /auth/login")


def get_token_payload(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> TokenPayload:
    """Validiert den JWT und liefert das Payload.

    - Header fehlt -> 401
    - Token abgelaufen / ungueltig / gefaelscht -> 401
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization-Header fehlt. Bitte 'Bearer <jwt>' senden.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return decode_token(credentials.credentials)
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


async def get_tenant(
    payload: Annotated[TokenPayload, Depends(get_token_payload)],
) -> AsyncGenerator[TenantContext, None]:
    """Extrahiert den Tenant aus dem JWT und setzt ihn als ContextVar.

    Generator-Dependency: try/finally garantiert sauberen Reset.
    """
    try:
        tenant = TenantContext(tenant_id=payload.tenant_id)
    except ValueError as exc:
        # Kann passieren, wenn ein altes Token einen ungueltigen tenant_id-Format hat.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token enthaelt ungueltige tenant_id: {exc}",
        ) from exc

    token = current_tenant_var.set(tenant)
    try:
        yield tenant
    finally:
        current_tenant_var.reset(token)


@lru_cache(maxsize=1)
def get_file_storage() -> LocalFilesystemStorage:
    """Singleton-Instanz des lokalen Datei-Speichers.

    lru_cache(maxsize=1) = Singleton-Pattern ohne globale Variable.
    Wechsel zu S3 spaeter: diese Funktion austauschen, alles andere bleibt.
    Nicht in Tests ueberschreiben noetig - Tests nutzen tmp_path als base_dir.
    """
    return LocalFilesystemStorage()


def get_db_engine() -> AsyncEngine:
    """Liefert die Modul-Engine. Per Dependency-Override in Tests austauschbar.

    Hintergrund: Background-Tasks koennen die Request-Session nicht weiterverwenden
    (die ist nach Response-Ende zu). Sie brauchen also Zugriff auf die Engine,
    um eine eigene Session zu oeffnen. In Tests muss diese Engine die Test-DB-Engine
    sein, nicht die Modul-Engine die auf die Prod-DB zeigt.
    """
    return _module_engine


@lru_cache(maxsize=1)
def get_email_sender() -> EmailSender:
    """Singleton-Instanz fuer den E-Mail-Versand."""
    if settings.email_backend == "smtp":
        if (
            settings.smtp_host is not None
            and settings.smtp_user is not None
            and settings.smtp_password is not None
        ):
            return SmtpEmailSender()
    return ConsoleEmailSender()


TenantDep = Annotated[TenantContext, Depends(get_tenant)]
TokenDep = Annotated[TokenPayload, Depends(get_token_payload)]
FileStorageDep = Annotated[LocalFilesystemStorage, Depends(get_file_storage)]
AIProviderDep = Annotated[AIProvider, Depends(get_ai_provider)]
EngineDep = Annotated[AsyncEngine, Depends(get_db_engine)]
EmailSenderDep = Annotated[EmailSender, Depends(get_email_sender)]

SettingsDep = Annotated[Settings, Depends(get_settings)]
