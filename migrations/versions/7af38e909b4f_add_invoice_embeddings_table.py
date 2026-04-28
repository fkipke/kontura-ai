"""add invoice embeddings table

Revision ID: 7af38e909b4f
Revises: 29e9635971a4
Create Date: 2026-04-28 08:45:43.761823

"""

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7af38e909b4f"
down_revision: str | Sequence[str] | None = "29e9635971a4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Erstellt die invoice_embeddings-Tabelle samt Indizes (inkl. IVFFlat)."""
    op.create_table(
        "invoice_embeddings",
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("invoice_id", sa.UUID(), nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(dim=1536), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("source_text", sa.String(length=2000), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
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
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_invoice_embeddings_invoice_id"),
        "invoice_embeddings",
        ["invoice_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_invoice_embeddings_tenant_id"),
        "invoice_embeddings",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_invoice_embeddings_tenant_invoice",
        "invoice_embeddings",
        ["tenant_id", "invoice_id"],
        unique=False,
    )

    # IVFFlat-Index fuer schnelle Cosine-Distance-Suche.
    # Senior-Konzept: IVFFlat clustert Vektoren in 'lists' (hier 100).
    # Bei der Suche werden nur die naechstgelegenen Cluster durchsucht statt alle Zeilen.
    # 'lists' ~ sqrt(erwartete Zeilenzahl): 100 ist gut fuer 10k-1M Embeddings.
    # Bei viel mehr Daten spaeter neu erstellen mit hoeherem 'lists'-Wert.
    op.execute(
        "CREATE INDEX ix_invoice_embeddings_embedding_cosine "
        "ON invoice_embeddings USING ivfflat (embedding vector_cosine_ops) "
        "WITH (lists = 100)"
    )


def downgrade() -> None:
    """Entfernt die invoice_embeddings-Tabelle samt Indizes."""
    op.execute("DROP INDEX IF EXISTS ix_invoice_embeddings_embedding_cosine")
    op.drop_index("ix_invoice_embeddings_tenant_invoice", table_name="invoice_embeddings")
    op.drop_index(op.f("ix_invoice_embeddings_tenant_id"), table_name="invoice_embeddings")
    op.drop_index(op.f("ix_invoice_embeddings_invoice_id"), table_name="invoice_embeddings")
    op.drop_table("invoice_embeddings")
