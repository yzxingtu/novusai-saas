"""add codegen_config_versions table

CRUD 代码生成配置版本历史表。每次保存配置时创建快照，用于版本历史与恢复。
CRUD codegen config version history. Snapshot on each save for history and restore.

Revision ID: 20260317_001_versions
Revises: 20260317_codegen
Create Date: 2026-03-17

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "20260317_001_versions"
down_revision: str | Sequence[str] | None = "20260317_codegen"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "codegen_config_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("delete_level", sa.String(20), nullable=True),
        sa.Column("config_id", sa.Integer(), nullable=False, comment="配置 ID"),
        sa.Column("config_json", JSONB, nullable=False, comment="配置快照 JSON"),
        sa.Column("note", sa.String(200), nullable=True, comment="版本备注"),
        sa.ForeignKeyConstraint(["config_id"], ["codegen_configs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_codegen_config_versions_config_id", "codegen_config_versions", ["config_id"])
    op.create_index("ix_codegen_config_versions_id", "codegen_config_versions", ["id"])
    op.create_index("ix_codegen_config_versions_is_deleted", "codegen_config_versions", ["is_deleted"])


def downgrade() -> None:
    op.drop_index("ix_codegen_config_versions_is_deleted", "codegen_config_versions")
    op.drop_index("ix_codegen_config_versions_id", "codegen_config_versions")
    op.drop_index("ix_codegen_config_versions_config_id", "codegen_config_versions")
    op.drop_table("codegen_config_versions")
