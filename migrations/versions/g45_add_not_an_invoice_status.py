"""add not_an_invoice value to extraction_status enum

Revision ID: g45_add_not_an_invoice_status
Revises: g44_add_extraction_method
Create Date: 2026-06-07 20:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "g45_add_not_an_invoice_status"
down_revision: str | Sequence[str] | None = "g44_add_extraction_method"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Postgres does not allow ALTER TYPE inside a transaction.
    # COMMIT ends the implicit transaction, then we add the value.
    op.execute("COMMIT")
    op.execute("ALTER TYPE extraction_status ADD VALUE IF NOT EXISTS 'not_an_invoice'")


def downgrade() -> None:
    # Postgres does not support removing enum values cleanly; no-op.
    pass
