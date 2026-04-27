"""add llm audit entries table

Revision ID: 29e9635971a4
Revises: 345468c88a8b
Create Date: 2026-04-27 16:00:30.351223

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "29e9635971a4"
down_revision: str | Sequence[str] | None = "345468c88a8b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Erstellt die llm_audit_entries-Tabelle samt Indizes."""
    op.create_table(
        "llm_audit_entries",
        sa.Column("provider_name", sa.String(length=50), nullable=False),
        sa.Column("operation", sa.String(length=20), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("prompt_text", sa.Text(), nullable=False),
        sa.Column("prompt_chars", sa.Integer(), nullable=False),
        sa.Column("response_chars", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_llm_audit_entries_model"), "llm_audit_entries", ["model"], unique=False
    )
    op.create_index(
        op.f("ix_llm_audit_entries_operation"), "llm_audit_entries", ["operation"], unique=False
    )
    op.create_index(
        op.f("ix_llm_audit_entries_provider_name"),
        "llm_audit_entries",
        ["provider_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_llm_audit_entries_success"), "llm_audit_entries", ["success"], unique=False
    )


def downgrade() -> None:
    """Entfernt die llm_audit_entries-Tabelle samt Indizes."""
    op.drop_index(op.f("ix_llm_audit_entries_success"), table_name="llm_audit_entries")
    op.drop_index(op.f("ix_llm_audit_entries_provider_name"), table_name="llm_audit_entries")
    op.drop_index(op.f("ix_llm_audit_entries_operation"), table_name="llm_audit_entries")
    op.drop_index(op.f("ix_llm_audit_entries_model"), table_name="llm_audit_entries")
    op.drop_table("llm_audit_entries")
