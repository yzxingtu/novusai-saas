"""Add profile snapshots and memory embeddings

Revision ID: 20260330_0070_mem_prof
Revises: 20260330_0060_log_decision
Create Date: 2026-03-30
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260330_0070_mem_prof"
down_revision: str | Sequence[str] | None = "20260330_0060_log_decision"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "memory_records",
        sa.Column("embedding_model_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "memory_records",
        sa.Column("embedding_dimensions", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_memory_records_embedding_model_id",
        "memory_records",
        ["embedding_model_id"],
        unique=False,
    )
    op.execute(sa.text("ALTER TABLE memory_records ADD COLUMN embedding vector"))

    op.create_table(
        "profile_snapshots",
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("scope_type", sa.String(length=50), nullable=False),
        sa.Column("scope_key", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("profile_json", sa.JSON(), nullable=True),
        sa.Column("record_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_updated_at", sa.DateTime(), nullable=True),
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
    op.create_index(
        "ix_profile_snapshots_tenant_id",
        "profile_snapshots",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_profile_snapshots_agent_id",
        "profile_snapshots",
        ["agent_id"],
        unique=False,
    )
    op.create_index(
        "ix_profile_snapshots_user_id",
        "profile_snapshots",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_profile_snapshots_scope_type",
        "profile_snapshots",
        ["scope_type"],
        unique=False,
    )
    op.create_index(
        "ix_profile_snapshots_scope_key",
        "profile_snapshots",
        ["scope_key"],
        unique=False,
    )
    op.create_index(
        "idx_profile_snapshots_scope_unique",
        "profile_snapshots",
        ["tenant_id", "scope_type", "scope_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_profile_snapshots_scope_unique",
        table_name="profile_snapshots",
    )
    op.drop_index("ix_profile_snapshots_scope_key", table_name="profile_snapshots")
    op.drop_index("ix_profile_snapshots_scope_type", table_name="profile_snapshots")
    op.drop_index("ix_profile_snapshots_user_id", table_name="profile_snapshots")
    op.drop_index("ix_profile_snapshots_agent_id", table_name="profile_snapshots")
    op.drop_index("ix_profile_snapshots_tenant_id", table_name="profile_snapshots")
    op.drop_table("profile_snapshots")

    op.execute(sa.text("ALTER TABLE memory_records DROP COLUMN embedding"))
    op.drop_index("ix_memory_records_embedding_model_id", table_name="memory_records")
    op.drop_column("memory_records", "embedding_dimensions")
    op.drop_column("memory_records", "embedding_model_id")
