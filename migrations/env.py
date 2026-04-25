"""Alembic-Umgebung fuer Kontura AI.

Senior-Setup:
- Alembic laeuft SYNCHRON (Driver: psycopg).
- Die App selbst nutzt weiterhin asyncpg.
- DB-URL kommt aus settings, asyncpg-URL wird zu psycopg-URL konvertiert.
- target_metadata = Base.metadata fuer Autogenerate.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from kontura.core.config import settings
from kontura.infra.db import Base
from kontura.infra.models import Invoice  # noqa: F401  # registriert das Modell bei Base.metadata

# Hier alle Modelle importieren, damit Alembic sie kennt (Autogenerate).
# Wenn ein neues Modell dazukommt, in kontura.infra.models.__init__ exportieren
# und der Import oben sieht es automatisch.

config = context.config


def _sync_database_url(url: str) -> str:
    """Konvertiert eine async-DB-URL zu einer sync-URL fuer Alembic.

    asyncpg ist auf Windows + Docker Desktop instabil bei SCRAM-Auth.
    Alembic nutzt deshalb den synchronen psycopg-Driver.
    """
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


# DB-URL zur Laufzeit aus settings setzen (Sync-Variante)
config.set_main_option("sqlalchemy.url", _sync_database_url(settings.database_url))

# Logging-Konfiguration aus alembic.ini laden
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata, gegen die Alembic Autogenerate-Diffs erstellt
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Migrations ohne aktive DB-Verbindung (generiert SQL-Skripte).

    Nutzung: alembic upgrade head --sql
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Migrations mit aktiver DB-Verbindung (Standard-Modus, synchron)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,  # erkennt Spalten-Typ-Aenderungen
            compare_server_default=True,  # erkennt DEFAULT-Aenderungen
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
