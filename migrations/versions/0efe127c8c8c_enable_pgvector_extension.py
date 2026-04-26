"""enable pgvector extension

Revision ID: <wird automatisch gesetzt>
Revises: e7ea957a3d93
Create Date: <wird automatisch gesetzt>
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
# WICHTIG: revision und down_revision NICHT aendern, das hat Alembic schon befuellt.
# Hier sind Platzhalter - lass die Werte stehen, die in DEINER Datei drin sind!
revision: str = "<aus deiner generierten Datei>"
down_revision: str | None = "e7ea957a3d93"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # pgvector-Extension aktivieren (Postgres-Image hat sie bereits installiert)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS vector")
