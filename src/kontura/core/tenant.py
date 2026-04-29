"""TenantContext: Repraesentiert den aktuellen Mandanten in einer Request.

Senior-Konzept 1: Tenant als typisiertes Objekt, nicht als String
================================================================
Statt 'tenant_id: str' ueberall durchzureichen, kapseln wir den Tenant in
einem Pydantic-Model. Vorteile:

1. **Validierung an genau EINER Stelle** (Format, Laenge, erlaubte Zeichen).
2. **Self-Documenting:** Funktionssignatur 'def x(tenant: TenantContext)'
   ist klarer als 'def x(tenant_id: str)'.
3. **Erweiterbar:** Spaeter koennen wir Felder ergaenzen (z.B. plan_tier,
   features, locale) ohne hunderte Signaturen anzufassen.
4. **Schwer zu faelschen:** Ein 'TenantContext' kann nur ueber den offiziellen
   Konstruktor entstehen - ein vergessener Filter ist sofort sichtbar.

Senior-Konzept 2: ContextVar fuer ambient Tenant-Propagation
============================================================
Cross-cutting Components (Logging, Audit, Metrics) brauchen den Tenant,
ohne dass jede Funktion ihn als Parameter durchschleift. Loesung: ContextVar -
Pythons Async-aware Thread-Local. Jeder Request-Task hat seinen eigenen Wert,
ohne sich mit anderen Tasks zu mischen.

Verwendung:
    # Im Dependency / Middleware:
    token = current_tenant_var.set(tenant)
    try:
        ...do work...
    finally:
        current_tenant_var.reset(token)  # wichtig: Token zuruecksetzen!

    # Wo immer der Tenant gebraucht wird (z.B. AuditedAIProvider):
    tenant = current_tenant_var.get()  # liefert den aktuellen Tenant

Default = SYSTEM_TENANT, damit Code ausserhalb von Requests (Cron, CLI,
Smoke-Tests) trotzdem laeuft.
"""

from __future__ import annotations

import re
from contextvars import ContextVar
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Tenant-IDs duerfen nur a-z, 0-9, '-' und '_' enthalten (URL-safe).
_TENANT_ID_PATTERN: Final = re.compile(r"^[a-z0-9_-]{2,64}$")


class TenantContext(BaseModel):
    """Identifiziert den aktuellen Mandanten."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tenant_id: str = Field(
        ...,
        min_length=2,
        max_length=64,
        description="Eindeutige Tenant-Kennung (lowercase, URL-safe).",
    )

    @field_validator("tenant_id")
    @classmethod
    def _validate_format(cls, v: str) -> str:
        if not _TENANT_ID_PATTERN.match(v):
            raise ValueError(
                "tenant_id darf nur a-z, 0-9, '-' und '_' enthalten (Laenge 2-64 Zeichen)."
            )
        return v

    def __str__(self) -> str:
        return self.tenant_id


# Sentinel-Tenant fuer Calls ohne Request-Kontext (Cron-Jobs, Smoke-Tests, CLI).
# Wird NIEMALS aus dem User-Code per Parameter angelegt - existiert nur als Default.
SYSTEM_TENANT: Final[TenantContext] = TenantContext(tenant_id="system")


# ContextVar fuer ambient Tenant-Propagation (siehe Modul-Docstring).
# Default = SYSTEM_TENANT, damit Background-Tasks lauffaehig sind.
current_tenant_var: ContextVar[TenantContext] = ContextVar("current_tenant", default=SYSTEM_TENANT)


def get_current_tenant() -> TenantContext:
    """Liefert den aktuellen Tenant aus dem ContextVar.

    Gibt SYSTEM_TENANT zurueck, wenn kein Tenant gesetzt ist (z.B. ausserhalb
    eines HTTP-Requests). Damit laufen Background-Jobs ohne explizites Setup.
    """
    return current_tenant_var.get()
