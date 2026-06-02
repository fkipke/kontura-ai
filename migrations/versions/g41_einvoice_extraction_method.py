"""G4.1: add extraction_method to invoice_files

Revision ID: g41a1b2c3d4e5
Revises: g32a1b2c3d4e5
Create Date: 2026-06-02 22:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "g41a1b2c3d4e5"
down_revision: str | Sequence[str] | None = "g32a1b2c3d4e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "invoice_files", sa.Column("extraction_method", sa.String(length=32), nullable=True)
    )
    op.execute(
        "UPDATE invoice_files "
        "SET extraction_method = 'ai_vision' "
        "WHERE extraction_status = 'completed' AND extraction_method IS NULL"
    )


def downgrade() -> None:
    op.drop_column("invoice_files", "extraction_method")
