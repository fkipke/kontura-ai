"""Shared FastAPI-Dependencies fuer alle API-Versionen.

Zentral gehaltene Dependencies, die sowohl von '/invoices' (v0-style) als
auch von '/api/v1/...' verwendet werden. So gibt es nur EINE Stelle fuer
die Tenant-Resolution - egal welche API-Version aufgerufen wird.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from pydantic import ValidationError

from kontura.core.tenant import TenantContext


def get_tenant(
    x_tenant_id: Annotated[str | None, Header(alias="X-Tenant-Id")] = None,
) -> TenantContext:
    """Extrahiert den Tenant aus dem 'X-Tenant-Id'-Header.

    - Header fehlt -> 401 Unauthorized
    - Format ungueltig -> 400 Bad Request
    - Spaeter (Phase E): Auswertung des JWT-Claims statt Header.
      Aenderung NUR hier - kein Endpoint muss angefasst werden.
    """
    if not x_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Header 'X-Tenant-Id' wird benoetigt.",
        )
    try:
        return TenantContext(tenant_id=x_tenant_id)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ungueltige tenant_id: {exc.errors()[0]['msg']}",
        ) from exc


TenantDep = Annotated[TenantContext, Depends(get_tenant)]
