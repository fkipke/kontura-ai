"""add extraction_method to invoice_files

Revision ID: g44_add_extraction_method
Revises: g43a1b2c3d4e5
Create Date: 2026-06-06 19:45:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "g44_add_extraction_method"
down_revision: str | Sequence[str] | None = "g43a1b2c3d4e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_extraction_method_enum = sa.Enum(
    "xrechnung_ubl",
    "xrechnung_cii",
    "zugferd_v2",
    "ai_vision",
    name="extraction_method",
)


def upgrade() -> None:
    _extraction_method_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "invoice_files",
        sa.Column(
            "extraction_method",
            sa.Enum(
                "xrechnung_ubl",
                "xrechnung_cii",
                "zugferd_v2",
                "ai_vision",
                name="extraction_method",
                create_type=False,
            ),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("invoice_files", "extraction_method")
    _extraction_method_enum.drop(op.get_bind(), checkfirst=True)
