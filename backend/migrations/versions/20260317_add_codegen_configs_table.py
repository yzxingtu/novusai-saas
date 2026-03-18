"""add codegen_configs table

CRUD 代码生成器配置表。平台级资源，无企业隔离。
CRUD codegen config table. Platform-level resource, no tenant isolation.

Revision ID: 20260317_codegen
Revises: 20260319_page_op_75
Create Date: 2026-03-17

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "20260317_codegen"
down_revision: str | Sequence[str] | None = "20260319_page_op_75"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "codegen_configs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("delete_level", sa.String(20), nullable=True),
        sa.Column("name", sa.String(100), nullable=False, comment="配置名称"),
        sa.Column("resource", sa.String(100), nullable=False, comment="资源名 (snake_case)"),
        sa.Column("module", sa.String(50), nullable=False, comment="模块归属"),
        sa.Column("display_name", sa.String(100), nullable=False, comment="中文显示名"),
        sa.Column("display_name_en", sa.String(100), nullable=False, comment="英文显示名"),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="draft",
            comment="状态: draft/generated/applied/rolled_back",
        ),
        sa.Column("config_json", JSONB, nullable=False, comment="完整配置 JSON"),
        sa.Column("last_generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("generation_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("generated_files", JSONB, nullable=True),
        sa.Column("config_hash", sa.String(64), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_codegen_configs_resource", "codegen_configs", ["resource"])
    op.create_index("ix_codegen_configs_id", "codegen_configs", ["id"])
    op.create_index("ix_codegen_configs_is_deleted", "codegen_configs", ["is_deleted"])


def downgrade() -> None:
    op.drop_index("ix_codegen_configs_is_deleted", "codegen_configs")
    op.drop_index("ix_codegen_configs_id", "codegen_configs")
    op.drop_index("ix_codegen_configs_resource", "codegen_configs")
    op.drop_table("codegen_configs")
