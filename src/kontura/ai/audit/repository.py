"""Repository fuer LLMAuditEntry-Persistierung.

Bewusst eine eigene engine + sessionmaker, weil Audit-Calls oft AUSSERHALB
des Request-Lifecycles passieren (z.B. Background-Worker). Wir wollen NICHT,
dass ein fehlgeschlagenes Audit den eigentlichen LLM-Call killt.

Senior-Pattern: save() schluckt Exceptions (Audit darf nie crashen).
list_for_tenant() reicht Exceptions weiter (Endpoint will Fehler sehen).
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from kontura.core.config import settings
from kontura.core.tenant import TenantContext
from kontura.infra.models import LLMAuditEntry

logger = logging.getLogger(__name__)


class AuditRepository:
    """Persistiert und liest LLMAuditEntry-Eintraege.

    Nutzt eigene Engine, damit Audit-Logging nicht an Caller-Sessions gekoppelt ist.
    """

    def __init__(self, database_url: str | None = None) -> None:
        url = database_url or settings.database_url
        self._engine = create_async_engine(url, echo=False, future=True)
        self._sessionmaker = async_sessionmaker(
            self._engine, expire_on_commit=False, class_=AsyncSession
        )

    async def save(self, entry: LLMAuditEntry) -> None:
        """Speichert einen Audit-Eintrag. Failures werden geloggt, NICHT geraised."""
        try:
            async with self._sessionmaker() as session:
                session.add(entry)
                await session.commit()
        except Exception as exc:  # noqa: BLE001 - bewusst breit, Audit darf nie crashen
            logger.error("Audit-Eintrag konnte nicht gespeichert werden: %s", exc)

    async def list_for_tenant(
        self,
        tenant: TenantContext,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[LLMAuditEntry]:
        """Listet Audit-Eintraege des Tenants, neueste zuerst.

        Compliance-Endpoint: liefert exakt das, was Auditor sehen will.
        Keine Embeddings, keine Vendor-Daten - nur Audit-Metadaten.
        """
        if limit < 1:
            raise ValueError("limit muss >= 1 sein")
        if offset < 0:
            raise ValueError("offset muss >= 0 sein")

        async with self._sessionmaker() as session:
            stmt = (
                select(LLMAuditEntry)
                .where(LLMAuditEntry.tenant_id == tenant.tenant_id)
                .order_by(LLMAuditEntry.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            result = await session.execute(stmt)
            return result.scalars().all()

    async def dispose(self) -> None:
        """Schliesst die Engine sauber (z.B. beim App-Shutdown)."""
        await self._engine.dispose()
