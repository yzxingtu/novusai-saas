"""Create current plugin version and license tables.

Revision ID: d11f0b4fec39
Revises: c084bc659728
Create Date: 2026-02-23 02:43:36.879039+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d11f0b4fec39"
down_revision: str | Sequence[str] | None = "c084bc659728"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "plugin_licenses",
        sa.Column("plugin_id", sa.Integer(), nullable=False, comment="插件ID"),
        sa.Column("license_key", sa.String(length=500), nullable=True, comment="License Key"),
        sa.Column("license_type", sa.String(length=20), nullable=False, comment="许可类型"),
        sa.Column("version_scope", sa.String(length=50), nullable=True, comment="版本范围"),
        sa.Column("buyer_email", sa.String(length=200), nullable=True, comment="购买者邮箱"),
        sa.Column("issued_at", sa.DateTime(), nullable=True, comment="签发时间"),
        sa.Column("trial_expires_at", sa.DateTime(), nullable=True, comment="试用到期时间"),
        sa.Column("expires_at", sa.DateTime(), nullable=True, comment="正式 License 到期时间"),
        sa.Column("activated_at", sa.DateTime(), nullable=True, comment="激活时间"),
        sa.Column("is_valid", sa.Boolean(), nullable=False, comment="是否有效"),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False, comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False, comment="更新时间"),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False, comment="软删除标记"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True, comment="删除时间"),
        sa.Column("delete_level", sa.String(length=20), nullable=True, comment="删除层级"),
        sa.Column("recycle_stage", sa.String(length=20), nullable=True, comment="回收站阶段"),
        sa.Column("promoted_to_global_at", sa.DateTime(), nullable=True, comment="进入总回收站时间"),
        sa.ForeignKeyConstraint(["plugin_id"], ["plugins.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_plugin_licenses_id", "plugin_licenses", ["id"], unique=False)
    op.create_index("ix_plugin_licenses_is_deleted", "plugin_licenses", ["is_deleted"], unique=False)
    op.create_index("ix_plugin_licenses_recycle_stage", "plugin_licenses", ["recycle_stage"], unique=False)
    op.create_index("ix_plugin_licenses_plugin_id", "plugin_licenses", ["plugin_id"], unique=False)

    op.create_table(
        "plugin_versions",
        sa.Column("plugin_id", sa.Integer(), nullable=False, comment="插件ID"),
        sa.Column("version", sa.String(length=50), nullable=False, comment="版本号"),
        sa.Column("manifest", sa.JSON(), nullable=False, comment="该版本清单"),
        sa.Column("changelog", sa.Text(), nullable=True, comment="变更日志"),
        sa.Column("status", sa.String(length=20), nullable=False, comment="版本状态"),
        sa.Column("installed_at", sa.DateTime(), nullable=True, comment="安装时间"),
        sa.Column("rolled_back_at", sa.DateTime(), nullable=True, comment="回退时间"),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False, comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False, comment="更新时间"),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False, comment="软删除标记"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True, comment="删除时间"),
        sa.Column("delete_level", sa.String(length=20), nullable=True, comment="删除层级"),
        sa.Column("recycle_stage", sa.String(length=20), nullable=True, comment="回收站阶段"),
        sa.Column("promoted_to_global_at", sa.DateTime(), nullable=True, comment="进入总回收站时间"),
        sa.ForeignKeyConstraint(["plugin_id"], ["plugins.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_plugin_versions_id", "plugin_versions", ["id"], unique=False)
    op.create_index("ix_plugin_versions_is_deleted", "plugin_versions", ["is_deleted"], unique=False)
    op.create_index("ix_plugin_versions_recycle_stage", "plugin_versions", ["recycle_stage"], unique=False)
    op.create_index("ix_plugin_versions_plugin_id", "plugin_versions", ["plugin_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_plugin_versions_plugin_id", table_name="plugin_versions")
    op.drop_index("ix_plugin_versions_recycle_stage", table_name="plugin_versions")
    op.drop_index("ix_plugin_versions_is_deleted", table_name="plugin_versions")
    op.drop_index("ix_plugin_versions_id", table_name="plugin_versions")
    op.drop_table("plugin_versions")

    op.drop_index("ix_plugin_licenses_plugin_id", table_name="plugin_licenses")
    op.drop_index("ix_plugin_licenses_recycle_stage", table_name="plugin_licenses")
    op.drop_index("ix_plugin_licenses_is_deleted", table_name="plugin_licenses")
    op.drop_index("ix_plugin_licenses_id", table_name="plugin_licenses")
    op.drop_table("plugin_licenses")
