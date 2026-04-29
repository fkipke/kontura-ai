"""V1 API-Router-Aggregation.

Sammelt alle Sub-Router unter dem Prefix '/api/v1'.

Versioning-Strategie:
- Breaking Changes -> neuer Prefix '/api/v2', alte Endpoints bleiben fuer
  einen Migrations-Zeitraum erhalten.
- Nicht-breaking Erweiterungen (neue Endpoints, neue optionale Felder)
  laufen weiter unter v1.
"""

from fastapi import APIRouter

from kontura.api.v1.embeddings import router as embeddings_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(embeddings_router)

__all__ = ["api_v1_router"]
