"""G4.3: add vendor_account_mappings table.

Revision ID: g43a1b2c3d4e5
Revises: g32a1b2c3d4e5
Create Date: 2026-06-03 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "g43a1b2c3d4e5"
down_revision: str | Sequence[str] | None = "g32a1b2c3d4e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.create_table(
        "vendor_account_mappings",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("vendor_name_normalized", sa.String(length=200), nullable=False),
        sa.Column("vendor_name_raw", sa.String(length=255), nullable=False),
        sa.Column("creditor_account_number", sa.Integer(), nullable=False),
        sa.Column("usage_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "vendor_name_normalized",
            name="uq_vendor_account_mappings_tenant_normalized",
        ),
    )
    op.create_index(
        "ix_vendor_account_mappings_tenant_lastused",
        "vendor_account_mappings",
        ["tenant_id", "last_used_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_vendor_account_mappings_tenant_lastused",
        table_name="vendor_account_mappings",
    )
    op.drop_table("vendor_account_mappings")
