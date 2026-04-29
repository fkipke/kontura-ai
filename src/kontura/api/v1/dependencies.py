"""FastAPI-Dependencies fuer V1 API.

Nutzt die geteilte Tenant-Resolution aus 'kontura.api.dependencies' und
ergaenzt sie um v1-spezifische Service-Wirings (EmbeddingService).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from kontura.ai.base import AIProvider
from kontura.ai.embeddings import EmbeddingRepository, EmbeddingService
from kontura.ai.factory import get_ai_provider
from kontura.api.dependencies import TenantDep, get_tenant
from kontura.core.config import settings
from kontura.infra.db import get_session


def get_ai_provider_dep() -> AIProvider:
    """Wrappt die Singleton-Factory fuer FastAPI."""
    return get_ai_provider()


def get_embedding_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    provider: Annotated[AIProvider, Depends(get_ai_provider_dep)],
) -> EmbeddingService:
    """Liefert einen EmbeddingService, frisch fuer jeden Request."""
    return EmbeddingService(
        provider=provider,
        repository=EmbeddingRepository(session),
        embedding_model=settings.openai_embedding_model,
    )


# Type-Aliase fuer kuerzere Endpoint-Signaturen
SessionDep = Annotated[AsyncSession, Depends(get_session)]
EmbeddingServiceDep = Annotated[EmbeddingService, Depends(get_embedding_service)]

__all__ = [
    "EmbeddingServiceDep",
    "SessionDep",
    "TenantDep",
    "get_tenant",
]
