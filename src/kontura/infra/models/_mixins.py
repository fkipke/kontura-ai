"""Wiederverwendbare ORM-Mixins fuer Standard-Spalten.

Jede Tabelle in Kontura AI bekommt:
- UUID als Primary Key (NICHT Auto-Increment)
- created_at / updated_at als timezone-aware UTC-Timestamps

Diese Mixins werden via Mehrfachvererbung in Modelle eingebunden.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


class UUIDPrimaryKeyMixin:
    """Stellt einen UUID-Primary-Key bereit (Postgres-nativ)."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )


class TimestampMixin:
    """Stellt created_at / updated_at als UTC-Timestamps bereit.

    server_default=func.now() = Datenbank setzt den Wert beim INSERT.
    onupdate=func.now() = Datenbank aktualisiert ihn bei jedem UPDATE.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
