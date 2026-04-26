"""Smoke-Test: pgvector ist aktiviert und funktioniert.

Wir nutzen pgvector spaeter fuer aehnliche-Rechnungen-Suche (RAG).
Dieser Test stellt sicher, dass die Extension lebt und Vector-Queries laufen.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_pgvector_extension_is_enabled(session: AsyncSession) -> None:
    """Die vector-Extension muss in der Test-DB verfuegbar sein."""
    result = await session.execute(
        text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
    )
    row = result.first()
    assert row is not None, "pgvector extension is not enabled - did you run alembic upgrade?"


@pytest.mark.asyncio
async def test_pgvector_cosine_distance_works(session: AsyncSession) -> None:
    """Cosine-Distance zwischen zwei einfachen Vektoren liefert ein numerisches Ergebnis."""
    result = await session.execute(
        text("SELECT '[1,2,3]'::vector <=> '[3,2,1]'::vector AS distance")
    )
    row = result.first()
    assert row is not None
    distance = float(row[0])
    # Cosine-Distance liegt zwischen 0 (identisch) und 2 (entgegengesetzt).
    assert 0.0 < distance < 2.0
