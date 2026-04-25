"""Alembic-Umgebung fuer Kontura AI.

Senior-Setup:
- Async-Engine wird zur Laufzeit aus kontura.infra.db importiert
- DB-URL kommt aus settings (Single-Source-of-Truth)
- target_metadata = Base.metadata fuer Autogenerate
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from kontura.core.config import settings
from kontura.infra.db import Base

# Hier alle Modelle importieren, damit Alembic sie kennt (Autogenerate).
# Sobald wir Modelle haben, ergaenzen wir die Importe hier.
# Beispiel: from kontura.infra.models import invoice  # noqa: F401

config = context.config

# DB-URL zur Laufzeit aus settings setzen (statt aus alembic.ini)
config.set_main_option("sqlalchemy.url", settings.database_url)

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


def do_run_migrations(connection: Connection) -> None:
    """Synchroner Migrations-Lauf innerhalb der Async-Connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,  # erkennt Spalten-Typ-Aenderungen
        compare_server_default=True,  # erkennt DEFAULT-Aenderungen
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Migrations mit aktiver Async-DB-Verbindung."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Default-Migrations-Modus (online, mit DB-Verbindung)."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
