"""add invoice_files table

Revision ID: f3c2a1b9e4d7
Revises: d5b1e8f4a210
Create Date: 2026-05-24 10:30:00.000000

G2.0 - Invoice File Upload Backend:
- Tabelle invoice_files fuer hochgeladene PDF/PNG/JPG-Rechnungsdateien
- tenant_id + sha256 UniqueConstraint fuer serverseitige Deduplication
- Index auf (tenant_id, created_at) fuer effiziente List-Queries
- invoice_id nullable: wird erst in G2.1 nach KI-Extraktion gesetzt
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f3c2a1b9e4d7"
down_revision: str | Sequence[str] | None = "d5b1e8f4a210"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Erstellt die invoice_files-Tabelle samt Constraints und Indizes."""
    op.create_table(
        "invoice_files",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column(
            "uploaded_by_user_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "invoice_id",
            sa.UUID(),
            sa.ForeignKey("invoices.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=50), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_path", sa.String(length=500), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "sha256", name="uq_invoice_files_tenant_sha256"),
    )

    # Index fuer schnelle Deduplication-Queries (get_by_sha256)
    op.create_index(
        op.f("ix_invoice_files_sha256"),
        "invoice_files",
        ["sha256"],
        unique=False,
    )

    # Composite-Index fuer List-Queries: tenant_id ASC, created_at DESC
    op.create_index(
        "ix_invoice_files_tenant_created",
        "invoice_files",
        ["tenant_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Entfernt die invoice_files-Tabelle samt Indizes."""
    op.drop_index("ix_invoice_files_tenant_created", table_name="invoice_files")
    op.drop_index(op.f("ix_invoice_files_sha256"), table_name="invoice_files")
    op.drop_table("invoice_files")
