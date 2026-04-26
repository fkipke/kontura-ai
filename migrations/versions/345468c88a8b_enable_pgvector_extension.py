"""enable pgvector extension

Revision ID: 345468c88a8b
Revises: <aus deiner generierten Datei>
Create Date: 2026-04-26 12:59:22.766027

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "345468c88a8b"
down_revision: str | Sequence[str] | None = "<aus deiner generierten Datei>"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
