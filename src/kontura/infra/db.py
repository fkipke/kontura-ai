"""Datenbank-Infrastruktur: Async-Engine, Session-Factory, ORM-Base.

Senior-Patterns hier:
- Single-Engine-Instance pro Anwendung (Connection-Pooling)
- async_sessionmaker fuer threadsichere Session-Erzeugung
- DeclarativeBase als Basis aller ORM-Modelle (SQLAlchemy 2.0-Stil)
- Dependency-Injection fuer FastAPI via get_session()
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from kontura.core.config import settings


class Base(DeclarativeBase):
    """Gemeinsame Basis-Klasse fuer alle ORM-Modelle.

    Alle Tabellen-Modelle (Invoice, Vendor, etc.) erben von dieser Klasse.
    SQLAlchemy nutzt sie, um das Schema zusammenzubauen.
    """


def _create_engine() -> AsyncEngine:
    """Erzeugt die Async-Engine mit produktionstauglichen Defaults.

    - pool_pre_ping: prueft Verbindungen vor Nutzung (verhindert "stale connection"-Fehler)
    - pool_size / max_overflow: Connection-Pool-Limits
    - echo: SQL-Logging im Debug-Modus
    """
    return create_async_engine(
        settings.database_url,
        echo=settings.app_env == "development" and settings.log_level == "DEBUG",
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        pool_recycle=3600,  # Verbindungen nach 1h erneuern (verhindert DB-Timeouts)
    )


# Single-Instance pro Prozess (Singleton-Pattern via Modul-Scope)
engine: AsyncEngine = _create_engine()

# Session-Factory: erzeugt neue Sessions auf Anforderung
SessionFactory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,  # Objekte bleiben nach commit() nutzbar
    autoflush=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI-Dependency: Liefert pro Request eine frische Session.

    Garantiert sauberes Aufraeumen (close) auch bei Exceptions.
    Verwendung in Endpoints:

        @app.get("/items")
        async def list_items(session: AsyncSession = Depends(get_session)):
            ...
    """
    async with SessionFactory() as session:
        yield session


async def dispose_engine() -> None:
    """Schliesst alle Pool-Verbindungen sauber.

    Wird beim Shutdown der Anwendung aufgerufen (Lifespan-Hook).
    """
    await engine.dispose()
