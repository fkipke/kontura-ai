"""add tenant_id to invoices

Revision ID: a4e2c9f17b3d
Revises: 7af38e909b4f
Create Date: 2026-04-28 19:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a4e2c9f17b3d"
down_revision: str | Sequence[str] | None = "7af38e909b4f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Fuegt tenant_id-Spalte und Composite-Unique-Constraint hinzu (K2 + K4)."""
    # 1. Neue Spalte (nullable=False, weil DB leer ist - in Production waere
    #    ein Backfill noetig: erst nullable=True, dann backfill, dann NOT NULL).
    op.add_column(
        "invoices",
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
    )

    # 2. Alten Single-Index auf invoice_number entfernen.
    #    Der composite UniqueConstraint unten erzeugt einen besseren Index
    #    (leftmost-prefix-Property: schnelle Queries auf tenant_id allein).
    op.drop_index(op.f("ix_invoices_invoice_number"), table_name="invoices")

    # 3. Composite Unique Constraint: pro Tenant ist invoice_number eindeutig.
    #    Verhindert Doppelbuchungen (K4) und gibt uns gleichzeitig einen
    #    schnellen Tenant-Index "for free".
    op.create_unique_constraint(
        "uq_invoices_tenant_invoice_number",
        "invoices",
        ["tenant_id", "invoice_number"],
    )


def downgrade() -> None:
    """Rollback: Constraint + Spalte entfernen, alten Index wiederherstellen."""
    op.drop_constraint("uq_invoices_tenant_invoice_number", "invoices", type_="unique")
    op.create_index(
        op.f("ix_invoices_invoice_number"),
        "invoices",
        ["invoice_number"],
        unique=False,
    )
    op.drop_column("invoices", "tenant_id")
