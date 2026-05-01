"""Create current plugin registry table.

Revision ID: 20260213_plugins
Revises: 20260213_seed_rb
Create Date: 2026-02-13 05:36:00.000000+08:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260213_plugins"
down_revision: str | Sequence[str] | None = "20260213_seed_rb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "plugins",
        sa.Column("name", sa.String(length=100), nullable=False, comment="插件唯一标识"),
        sa.Column("display_name", sa.String(length=200), nullable=False, comment="显示名称"),
        sa.Column("version", sa.String(length=50), nullable=False, comment="当前版本"),
        sa.Column("description", sa.Text(), nullable=True, comment="描述"),
        sa.Column("author", sa.String(length=200), nullable=True, comment="作者"),
        sa.Column("status", sa.String(length=20), nullable=False, comment="状态"),
        sa.Column("manifest", sa.JSON(), nullable=False, comment="清单内容"),
        sa.Column("icon", sa.String(length=200), nullable=True, comment="图标"),
        sa.Column("homepage", sa.String(length=500), nullable=True, comment="主页URL"),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False, comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False, comment="更新时间"),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False, comment="软删除标记"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True, comment="删除时间"),
        sa.Column("delete_level", sa.String(length=20), nullable=True, comment="删除层级"),
        sa.Column("recycle_stage", sa.String(length=20), nullable=True, comment="回收站阶段"),
        sa.Column("promoted_to_global_at", sa.DateTime(), nullable=True, comment="进入总回收站时间"),
        sa.Column("tags", sa.JSON(), nullable=True, comment="标签"),
        sa.Column("scope", sa.String(length=40), nullable=False, comment="作用域"),
        sa.Column("install_source", sa.String(length=20), nullable=False, comment="安装来源"),
        sa.Column("marketplace_slug", sa.String(length=200), nullable=True, comment="市场标识"),
        sa.Column("icon_color", sa.String(length=20), nullable=True, comment="图标颜色"),
        sa.Column("repository_url", sa.String(length=500), nullable=True, comment="仓库URL"),
        sa.Column("license_text", sa.String(length=50), nullable=True, comment="许可证"),
        sa.Column("tier", sa.String(length=20), nullable=False, comment="信任等级"),
        sa.Column("config", sa.JSON(), nullable=False, comment="全局配置"),
        sa.Column("ai_requirements", sa.JSON(), nullable=True, comment="AI需求"),
        sa.Column("pricing_type", sa.String(length=20), nullable=False, comment="定价类型"),
        sa.Column("pricing_info", sa.JSON(), nullable=True, comment="定价详情"),
        sa.Column("error_message", sa.Text(), nullable=True, comment="最近错误"),
        sa.Column("error_count", sa.Integer(), nullable=False, comment="连续错误次数"),
        sa.Column("installed_packages", sa.JSON(), nullable=False, comment="已安装的Python依赖"),
        sa.Column("granted_capabilities", sa.JSON(), nullable=False, comment="管理员授权的能力列表"),
        sa.Column("installed_at", sa.DateTime(), nullable=True, comment="安装时间"),
        sa.Column("enabled_at", sa.DateTime(), nullable=True, comment="启用时间"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_plugins_id", "plugins", ["id"], unique=False)
    op.create_index("ix_plugins_is_deleted", "plugins", ["is_deleted"], unique=False)
    op.create_index("ix_plugins_recycle_stage", "plugins", ["recycle_stage"], unique=False)
    op.create_index(
        "ix_plugins_name",
        "plugins",
        ["name"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index("ix_plugins_scope", "plugins", ["scope"], unique=False)
    op.create_index("ix_plugins_status", "plugins", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_plugins_status", table_name="plugins")
    op.drop_index("ix_plugins_scope", table_name="plugins")
    op.drop_index("ix_plugins_name", table_name="plugins")
    op.drop_index("ix_plugins_recycle_stage", table_name="plugins")
    op.drop_index("ix_plugins_is_deleted", table_name="plugins")
    op.drop_index("ix_plugins_id", table_name="plugins")
    op.drop_table("plugins")
