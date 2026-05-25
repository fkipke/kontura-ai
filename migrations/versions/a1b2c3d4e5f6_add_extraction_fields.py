"""add extraction fields to invoice_files and invoices

Revision ID: a1b2c3d4e5f6
Revises: f3c2a1b9e4d7
Create Date: 2026-05-24 18:00:00.000000

G2.1 - KI-Extraktion:
- Neue Spalten auf invoice_files:
    extraction_status (ENUM pending|processing|completed|failed, default pending)
    extraction_result  (JSONB, nullable - vollstaendiges extrahiertes JSON)
    extraction_error   (TEXT, nullable - letzte Fehlermeldung bei failed)
    extracted_at       (TIMESTAMPTZ, nullable - Zeitpunkt letzter erfolgreicher Extraktion)
    extraction_attempts (INTEGER NOT NULL default 0 - Anzahl Versuche)
- Composite-Index (tenant_id, extraction_status) fuer Status-Queries
- Neue Spalten auf invoices: net_amount, tax_amount (NUMERIC(12,2) nullable)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "f3c2a1b9e4d7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# PostgreSQL ENUM-Typ fuer Extraction-Status
_extraction_status_enum = sa.Enum(
    "pending",
    "processing",
    "completed",
    "failed",
    name="extraction_status",
)


def upgrade() -> None:
    """Fuegt Extraction-Spalten zu invoice_files und invoice_files hinzu."""
    # ENUM-Typ anlegen
    _extraction_status_enum.create(op.get_bind(), checkfirst=True)

    # Neue Spalten auf invoice_files
    op.add_column(
        "invoice_files",
        sa.Column(
            "extraction_status",
            sa.Enum(
                "pending",
                "processing",
                "completed",
                "failed",
                name="extraction_status",
                create_type=False,  # Typ existiert schon
            ),
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column(
        "invoice_files",
        sa.Column("extraction_result", JSONB, nullable=True),
    )
    op.add_column(
        "invoice_files",
        sa.Column("extraction_error", sa.Text(), nullable=True),
    )
    op.add_column(
        "invoice_files",
        sa.Column(
            "extracted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "invoice_files",
        sa.Column(
            "extraction_attempts",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )

    # Composite-Index fuer Status-Queries
    op.create_index(
        "ix_invoice_files_tenant_extraction_status",
        "invoice_files",
        ["tenant_id", "extraction_status"],
        unique=False,
    )

    # Neue Spalten auf invoices (nullable - Altdaten ohne Extraktion)
    op.add_column(
        "invoices",
        sa.Column("net_amount", sa.Numeric(precision=12, scale=2), nullable=True),
    )
    op.add_column(
        "invoices",
        sa.Column("tax_amount", sa.Numeric(precision=12, scale=2), nullable=True),
    )


def downgrade() -> None:
    """Entfernt Extraction-Spalten und ENUM-Typ."""
    # Invoices-Spalten zuruecknehmen
    op.drop_column("invoices", "tax_amount")
    op.drop_column("invoices", "net_amount")

    # Index und Spalten auf invoice_files zuruecknehmen
    op.drop_index("ix_invoice_files_tenant_extraction_status", table_name="invoice_files")
    op.drop_column("invoice_files", "extraction_attempts")
    op.drop_column("invoice_files", "extracted_at")
    op.drop_column("invoice_files", "extraction_error")
    op.drop_column("invoice_files", "extraction_result")
    op.drop_column("invoice_files", "extraction_status")

    # ENUM-Typ loeschen
    _extraction_status_enum.drop(op.get_bind(), checkfirst=True)
