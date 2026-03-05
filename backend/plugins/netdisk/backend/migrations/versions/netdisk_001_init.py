"""创建网盘插件三张表

Revision ID: netdisk_001
Revises:
Create Date: 2026-03-01
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# ── revision 链 ────────────────────────────────────────────────────────────────
revision      = "netdisk_001"
down_revision = None
branch_labels = ("plugin_netdisk",)   # 必须声明插件分支，格式 plugin_{name}
depends_on    = None


def upgrade() -> None:
    # ── 1. px_netdisk_quotas（无外键，先建）──────────────────────────────────
    op.create_table(
        "px_netdisk_quotas",
        sa.Column("id",          sa.Integer(),    primary_key=True),
        sa.Column("tenant_id",   sa.Integer(),    sa.ForeignKey("tenants.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("quota_bytes", sa.BigInteger(), nullable=False, server_default="10737418240"),  # 10 GB
        sa.Column("used_bytes",  sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("updated_at",  sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", name="uq_netdisk_quotas_tenant"),
    )

    # ── 2. px_netdisk_nodes（自引用，先建表再加 FK）───────────────────────────
    op.create_table(
        "px_netdisk_nodes",
        sa.Column("id",         sa.Integer(),    primary_key=True),
        sa.Column("tenant_id",  sa.Integer(),    sa.ForeignKey("tenants.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("parent_id",  sa.Integer(),    nullable=True, index=True),
        sa.Column("name",       sa.String(255),  nullable=False),
        sa.Column("node_type",  sa.String(10),   nullable=False),         # 'file' | 'folder'
        sa.Column("storage_key", sa.String(500), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("mime_type",  sa.String(128),  nullable=True),
        sa.Column("is_deleted", sa.Boolean(),    nullable=False, server_default="false", index=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Integer(),    nullable=True),
        sa.Column("updated_by", sa.Integer(),    nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    # 自引用 FK — 必须显式命名，downgrade 时依赖此名
    op.create_foreign_key(
        "fk_netdisk_nodes_parent",
        "px_netdisk_nodes", "px_netdisk_nodes",
        ["parent_id"], ["id"],
        ondelete="SET NULL",
    )
    # 全文搜索索引（需 pg_trgm 扩展）
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_netdisk_nodes_name_trgm "
        "ON px_netdisk_nodes USING gin(name gin_trgm_ops)"
    )

    # ── 3. px_netdisk_shares（依赖 nodes）────────────────────────────────────
    op.create_table(
        "px_netdisk_shares",
        sa.Column("id",            sa.Integer(),   primary_key=True),
        sa.Column("tenant_id",     sa.Integer(),   sa.ForeignKey("tenants.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("node_id",       sa.Integer(),   nullable=False, index=True),
        sa.Column("share_token",   sa.String(64),  nullable=False, unique=True),
        sa.Column("password_hash", sa.String(128), nullable=True),
        sa.Column("permission",    sa.String(20),  nullable=False, server_default="download"),
        sa.Column("expires_at",    sa.DateTime(timezone=True), nullable=True),
        sa.Column("access_count",  sa.Integer(),   nullable=False, server_default="0"),
        sa.Column("is_active",     sa.Boolean(),   nullable=False, server_default="true", index=True),
        sa.Column("created_by",    sa.Integer(),   nullable=True),
        sa.Column("created_at",    sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    # 显式 FK 命名 — downgrade 必须依赖此名
    op.create_foreign_key(
        "fk_netdisk_shares_node",
        "px_netdisk_shares", "px_netdisk_nodes",
        ["node_id"], ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    # 反向：先删依赖表
    op.drop_constraint("fk_netdisk_shares_node", "px_netdisk_shares", type_="foreignkey")
    op.drop_table("px_netdisk_shares")

    op.drop_index("idx_netdisk_nodes_name_trgm", table_name="px_netdisk_nodes")
    op.drop_constraint("fk_netdisk_nodes_parent", "px_netdisk_nodes", type_="foreignkey")
    op.drop_table("px_netdisk_nodes")

    op.drop_table("px_netdisk_quotas")
