"""TenantContext: Repraesentiert den aktuellen Mandanten in einer Request.

Senior-Konzept: Tenant als typisiertes Objekt, nicht als String
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
"""

from __future__ import annotations

import re
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Tenant-IDs duerfen nur a-z, 0-9, '-' und '_' enthalten (URL-safe).
# Keine Punkte/Slashes -> kein Risiko fuer Path-Traversal in spaeterem Storage.
_TENANT_ID_PATTERN: Final = re.compile(r"^[a-z0-9_-]{2,64}$")


class TenantContext(BaseModel):
    """Identifiziert den aktuellen Mandanten.

    Wird via FastAPI-Dependency aus dem Request gezogen (z.B. JWT-Claim oder
    Header) und an Services/Repositories weitergegeben.
    """

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

    def __str__(self) -> str:  # praktisch fuers Logging
        return self.tenant_id
