"""V1 Audit-Endpoints.

Routes (alle relativ zu '/api/v1'):
- GET /audit/llm-calls   - Listet LLM-Audit-Eintraege des aktuellen Tenants

Compliance-Endpoint: liefert Auditor genau das, was er sehen will.
- Maskierte Prompts (keine PII)
- Latenz, Modell, Provider, Erfolg/Fehler
- Tenant-Filter ist HARTKODIERT - der Endpoint kann gar nicht versehentlich
  Daten anderer Mandanten zurueckgeben.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from kontura.api.v1.dependencies import AuditRepositoryDep, TenantDep
from kontura.api.v1.schemas import AuditEntriesResponse, AuditEntryResponse

router = APIRouter(tags=["Audit"])


@router.get(
    "/audit/llm-calls",
    response_model=AuditEntriesResponse,
    summary="Listet LLM-Audit-Eintraege des aktuellen Tenants",
    description=(
        "Compliance-Endpoint: liefert maskierte LLM-Calls mit Latenz, Modell und "
        "Erfolgsstatus. Sortiert nach created_at DESC (neueste zuerst). "
        "Die Eintraege enthalten KEINE PII - die wurde bereits beim Schreiben maskiert."
    ),
    responses={
        401: {"description": "X-Tenant-Id Header fehlt"},
        400: {"description": "Ungueltige Tenant-Id"},
    },
)
async def list_audit_entries(
    tenant: TenantDep,
    audit_repo: AuditRepositoryDep,
    limit: int = Query(default=50, ge=1, le=500, description="Maximale Anzahl Eintraege"),
    offset: int = Query(default=0, ge=0, description="Offset fuer Pagination"),
) -> AuditEntriesResponse:
    """Listet die LLM-Audit-Eintraege des aktuellen Tenants."""
    entries = await audit_repo.list_for_tenant(tenant, limit=limit, offset=offset)
    return AuditEntriesResponse(
        results=[AuditEntryResponse.model_validate(e) for e in entries],
        count=len(entries),
    )
