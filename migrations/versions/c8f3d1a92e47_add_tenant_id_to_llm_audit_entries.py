"""add tenant_id to llm_audit_entries

Revision ID: c8f3d1a92e47
Revises: a4e2c9f17b3d
Create Date: 2026-04-29 09:00:00.000000

Senior-Pattern: 3-Phasen-Backfill (Production-safe)
====================================================
1. Spalte als nullable=True hinzufuegen   -> kein Schema-Lock-Drama
2. Bestehende Zeilen backfillen ('system') -> historische Audit-Eintraege bleiben
3. nullable=False setzen                  -> Vertrag fuer neue Zeilen scharf

Auf einer leeren DB ueberfluessig, aber genau so muss es in Production laufen.
Wir schreiben die Migration so, wie wir sie spaeter brauchen.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c8f3d1a92e47"
down_revision: str | Sequence[str] | None = "a4e2c9f17b3d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Fuegt tenant_id-Spalte zu llm_audit_entries hinzu (3-Phasen-Backfill)."""
    # Phase 1: Spalte als nullable=True
    op.add_column(
        "llm_audit_entries",
        sa.Column("tenant_id", sa.String(length=64), nullable=True),
    )

    # Phase 2: Backfill historischer Eintraege mit 'system'.
    # 'system' = LLM-Calls ohne Request-Kontext (z.B. Cron-Jobs, Migrations,
    # Smoke-Tests). Realer User-Tenant kann nicht rueckwirkend bestimmt werden.
    op.execute("UPDATE llm_audit_entries SET tenant_id = 'system' WHERE tenant_id IS NULL")

    # Phase 3: NOT NULL Constraint scharfstellen
    op.alter_column("llm_audit_entries", "tenant_id", nullable=False)

    # Index fuer schnelles Listing pro Tenant (Compliance-Endpoint)
    op.create_index(
        op.f("ix_llm_audit_entries_tenant_id"),
        "llm_audit_entries",
        ["tenant_id"],
        unique=False,
    )


def downgrade() -> None:
    """Rollback: Index + Spalte entfernen."""
    op.drop_index(op.f("ix_llm_audit_entries_tenant_id"), table_name="llm_audit_entries")
    op.drop_column("llm_audit_entries", "tenant_id")
