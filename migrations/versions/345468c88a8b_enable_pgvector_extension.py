"""enable pgvector extension

Revision ID: 345468c88a8b
Revises: e7ea957a3d93
Create Date: 2026-04-26 12:59:22.766027

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "345468c88a8b"
down_revision: str | Sequence[str] | None = "e7ea957a3d93"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Aktiviert die pgvector-Extension."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    """Deaktiviert die pgvector-Extension."""
    op.execute("DROP EXTENSION IF EXISTS vector")
