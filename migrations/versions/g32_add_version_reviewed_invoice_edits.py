"""G3.2: add version/is_reviewed to invoices + invoice_edits audit table

Revision ID: g32a1b2c3d4e5
Revises: b7f9c2a4d1e0
Create Date: 2026-05-28 13:00:00.000000

Aenderungen:
- invoices: version (INTEGER NOT NULL DEFAULT 1)
- invoices: is_reviewed (BOOLEAN NOT NULL DEFAULT FALSE)
- invoices: reviewed_at (TIMESTAMPTZ NULL)
- invoices: reviewed_by_user_id (UUID NULL, FK users.id ON DELETE SET NULL)
- invoices: line_items (JSONB NULL) -- editierbare Positionen (KI-Original in extraction_result)
- Backfill: bestehende invoices bekommen version=1, is_reviewed=false
- Neue Tabelle invoice_edits fuer GoBD-konformen Audit-Trail
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision: str = "g32a1b2c3d4e5"
down_revision: str | Sequence[str] | None = "b7f9c2a4d1e0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Fuegt version/is_reviewed-Spalten zu invoices und neue invoice_edits-Tabelle hinzu."""
    # ---- invoices: neue Spalten ----
    op.add_column(
        "invoices",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "invoices",
        sa.Column("is_reviewed", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "invoices",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "invoices",
        sa.Column(
            "reviewed_by_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "invoices",
        sa.Column("line_items", JSONB, nullable=True),
    )

    # Backfill (server_default schon gesetzt, aber explizit fuer Konsistenz)
    op.execute("UPDATE invoices SET version = 1 WHERE version IS NULL")
    op.execute("UPDATE invoices SET is_reviewed = false WHERE is_reviewed IS NULL")

    # ---- invoice_edits: neue Audit-Trail-Tabelle ----
    op.create_table(
        "invoice_edits",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column(
            "invoice_id",
            UUID(as_uuid=True),
            sa.ForeignKey("invoices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("field", sa.String(64), nullable=False),
        sa.Column("old_value", JSONB, nullable=True),
        sa.Column("new_value", JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index(
        "ix_invoice_edits_tenant_invoice",
        "invoice_edits",
        ["tenant_id", "invoice_id"],
        unique=False,
    )


def downgrade() -> None:
    """Entfernt Audit-Tabelle und neue Spalten."""
    op.drop_index("ix_invoice_edits_tenant_invoice", table_name="invoice_edits")
    op.drop_table("invoice_edits")

    op.drop_column("invoices", "line_items")
    op.drop_column("invoices", "reviewed_by_user_id")
    op.drop_column("invoices", "reviewed_at")
    op.drop_column("invoices", "is_reviewed")
    op.drop_column("invoices", "version")
