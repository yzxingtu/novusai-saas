"""Add long-term memory records table

Revision ID: 20260329_0030_memory_records
Revises: 20260329_0020
Create Date: 2026-03-29
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260329_0030_memory_records"
down_revision: str | Sequence[str] | None = "20260329_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "memory_records",
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("scope_type", sa.String(length=50), nullable=False),
        sa.Column("scope_key", sa.String(length=255), nullable=False),
        sa.Column("memory_type", sa.String(length=50), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("keywords", sa.JSON(), nullable=True),
        sa.Column("content_hash", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Integer(), nullable=False, server_default="70"),
        sa.Column("importance", sa.Integer(), nullable=False, server_default="50"),
        sa.Column(
            "source_kind",
            sa.String(length=50),
            nullable=False,
            server_default="conversation_turn",
        ),
        sa.Column("source_ref", sa.String(length=255), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="candidate",
        ),
        sa.Column("last_recalled_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("delete_level", sa.String(length=20), nullable=True),
        sa.Column("recycle_stage", sa.String(length=20), nullable=True),
        sa.Column("promoted_to_global_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_memory_records_id", "memory_records", ["id"], unique=False)
    op.create_index(
        "ix_memory_records_tenant_id", "memory_records", ["tenant_id"], unique=False
    )
    op.create_index(
        "ix_memory_records_agent_id", "memory_records", ["agent_id"], unique=False
    )
    op.create_index(
        "ix_memory_records_user_id", "memory_records", ["user_id"], unique=False
    )
    op.create_index(
        "ix_memory_records_scope_type",
        "memory_records",
        ["scope_type"],
        unique=False,
    )
    op.create_index(
        "ix_memory_records_scope_key",
        "memory_records",
        ["scope_key"],
        unique=False,
    )
    op.create_index(
        "ix_memory_records_memory_type",
        "memory_records",
        ["memory_type"],
        unique=False,
    )
    op.create_index(
        "ix_memory_records_content_hash",
        "memory_records",
        ["content_hash"],
        unique=False,
    )
    op.create_index(
        "ix_memory_records_status",
        "memory_records",
        ["status"],
        unique=False,
    )
    op.create_index(
        "idx_memory_records_scope_lookup",
        "memory_records",
        ["tenant_id", "scope_type", "scope_key", "status"],
        unique=False,
    )
    op.create_index(
        "idx_memory_records_scope_type_hash",
        "memory_records",
        ["tenant_id", "scope_type", "scope_key", "memory_type", "content_hash"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_memory_records_scope_type_hash", table_name="memory_records")
    op.drop_index("idx_memory_records_scope_lookup", table_name="memory_records")
    op.drop_index("ix_memory_records_status", table_name="memory_records")
    op.drop_index("ix_memory_records_content_hash", table_name="memory_records")
    op.drop_index("ix_memory_records_memory_type", table_name="memory_records")
    op.drop_index("ix_memory_records_scope_key", table_name="memory_records")
    op.drop_index("ix_memory_records_scope_type", table_name="memory_records")
    op.drop_index("ix_memory_records_user_id", table_name="memory_records")
    op.drop_index("ix_memory_records_agent_id", table_name="memory_records")
    op.drop_index("ix_memory_records_tenant_id", table_name="memory_records")
    op.drop_index("ix_memory_records_id", table_name="memory_records")
    op.drop_table("memory_records")
