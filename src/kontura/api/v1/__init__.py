"""V1 API-Router-Aggregation.

Sammelt alle Sub-Router unter dem Prefix '/api/v1'.

Versioning-Strategie:
- Breaking Changes -> neuer Prefix '/api/v2', alte Endpoints bleiben fuer
  einen Migrations-Zeitraum erhalten.
- Nicht-breaking Erweiterungen (neue Endpoints, neue optionale Felder)
  laufen weiter unter v1.
"""

from fastapi import APIRouter

from kontura.api.exports import router as exports_router
from kontura.api.v1.audit import router as audit_router
from kontura.api.v1.embeddings import router as embeddings_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(embeddings_router)
api_v1_router.include_router(audit_router)
api_v1_router.include_router(exports_router)

__all__ = ["api_v1_router"]
