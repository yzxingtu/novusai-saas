"""add attachments table

Revision ID: 20260124_0007
Revises: 20260123_0006
Create Date: 2026-01-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260124_0007"
down_revision: Union[str, None] = "20260123_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "attachments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False, index=True, comment="租户ID"),
        sa.Column("name", sa.String(length=255), nullable=False, comment="文件名"),
        sa.Column("original_name", sa.String(length=255), nullable=True, comment="原始文件名"),
        sa.Column("path", sa.String(length=500), nullable=False, comment="存储路径"),
        sa.Column("size", sa.Integer(), nullable=False, comment="文件大小(字节)"),
        sa.Column("hash", sa.String(length=64), nullable=True, comment="文件哈希"),
        sa.Column("mime_type", sa.String(length=100), nullable=True, comment="MIME 类型"),
        sa.Column("extension", sa.String(length=20), nullable=True, comment="文件扩展名"),
        sa.Column("visibility", sa.String(length=20), nullable=False, server_default="private", comment="可见性"),
        sa.Column("driver", sa.String(length=50), nullable=False, comment="存储驱动"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active", comment="状态"),
        sa.Column("source", sa.String(length=20), nullable=True, comment="上传来源"),
        sa.Column("uploader_id", sa.Integer(), nullable=True, comment="上传者 ID"),
        sa.Column("business_type", sa.String(length=50), nullable=True, comment="业务类型"),
        sa.Column("business_id", sa.Integer(), nullable=True, comment="业务 ID"),
        sa.Column("metadata", sa.JSON(), nullable=True, comment="扩展元数据"),
        sa.Column("created_at", sa.DateTime(), nullable=False, comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, comment="更新时间"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false"), comment="软删除标记"),
    )
    op.create_index(
        "ix_attachments_tenant_path",
        "attachments",
        ["tenant_id", "path"],
        unique=True,
    )
    op.create_index(
        "ix_attachments_tenant_hash",
        "attachments",
        ["tenant_id", "hash"],
        unique=False,
    )
    op.create_index(
        "ix_attachments_is_deleted",
        "attachments",
        ["is_deleted"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_attachments_is_deleted", table_name="attachments")
    op.drop_index("ix_attachments_tenant_hash", table_name="attachments")
    op.drop_index("ix_attachments_tenant_path", table_name="attachments")
    op.drop_table("attachments")
