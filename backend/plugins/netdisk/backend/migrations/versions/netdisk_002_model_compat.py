"""对齐 netdisk ORM 模型与历史表结构

Revision ID: netdisk_002
Revises: netdisk_001
Create Date: 2026-03-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "netdisk_002"
down_revision = "netdisk_001"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def _add_base_model_columns(table_name: str, include_updated_at: bool = False) -> None:
    if not _has_column(table_name, "created_at"):
        op.add_column(
            table_name,
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )

    if include_updated_at and not _has_column(table_name, "updated_at"):
        op.add_column(
            table_name,
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )

    if not _has_column(table_name, "is_deleted"):
        op.add_column(
            table_name,
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )

    if not _has_column(table_name, "deleted_at"):
        op.add_column(table_name, sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))

    if not _has_column(table_name, "delete_level"):
        op.add_column(table_name, sa.Column("delete_level", sa.String(length=20), nullable=True))


def _drop_column_if_exists(table_name: str, column_name: str) -> None:
    if _has_column(table_name, column_name):
        op.drop_column(table_name, column_name)


def upgrade() -> None:
    # TenantModel 字段补齐：quota/share 缺少 BaseModel 字段，node 缺少 delete_level。
    _add_base_model_columns("px_netdisk_quotas", include_updated_at=False)
    _add_base_model_columns("px_netdisk_shares", include_updated_at=True)

    if not _has_column("px_netdisk_nodes", "delete_level"):
        op.add_column("px_netdisk_nodes", sa.Column("delete_level", sa.String(length=20), nullable=True))


def downgrade() -> None:
    _drop_column_if_exists("px_netdisk_nodes", "delete_level")

    _drop_column_if_exists("px_netdisk_shares", "delete_level")
    _drop_column_if_exists("px_netdisk_shares", "deleted_at")
    _drop_column_if_exists("px_netdisk_shares", "is_deleted")
    _drop_column_if_exists("px_netdisk_shares", "updated_at")

    _drop_column_if_exists("px_netdisk_quotas", "delete_level")
    _drop_column_if_exists("px_netdisk_quotas", "deleted_at")
    _drop_column_if_exists("px_netdisk_quotas", "is_deleted")
    _drop_column_if_exists("px_netdisk_quotas", "created_at")
