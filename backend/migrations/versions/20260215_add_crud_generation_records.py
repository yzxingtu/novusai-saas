"""add crud_generation_records table

Revision ID: dd0215006000
Revises: cc0215005000
Create Date: 2026-02-15 05:30:00.000000+08:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "dd0215006000"
down_revision: Union[str, None] = "cc0215005000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "crud_generation_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("delete_level", sa.String(20), nullable=True),
        # 操作人
        sa.Column(
            "operator_id",
            sa.Integer(),
            sa.ForeignKey("admins.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("operator_name", sa.String(100), nullable=True),
        # 操作信息
        sa.Column("operation_type", sa.String(20), nullable=False),
        sa.Column("module_name", sa.String(100), nullable=True),
        sa.Column("table_name", sa.String(100), nullable=True),
        # 配置快照
        sa.Column("config_snapshot", sa.JSON(), nullable=True),
        sa.Column("batch_project_snapshot", sa.JSON(), nullable=True),
        # 文件清单
        sa.Column("file_manifest", sa.JSON(), nullable=True),
        sa.Column("file_count", sa.Integer(), nullable=False, server_default="0"),
        # 执行结果
        sa.Column(
            "status", sa.String(20), nullable=False, server_default="success"
        ),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        # 关联与元数据
        sa.Column(
            "parent_record_id",
            sa.Integer(),
            sa.ForeignKey("crud_generation_records.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("metadata", sa.JSON(), nullable=True),
    )

    # 索引
    op.create_index(
        "ix_cgr_operator_created",
        "crud_generation_records",
        ["operator_id", "created_at"],
    )
    op.create_index(
        "ix_cgr_operation_type",
        "crud_generation_records",
        ["operation_type"],
    )
    op.create_index(
        "ix_cgr_status",
        "crud_generation_records",
        ["status"],
    )
    op.create_index(
        "ix_cgr_module_name",
        "crud_generation_records",
        ["module_name"],
    )
    op.create_index(
        "ix_cgr_table_name",
        "crud_generation_records",
        ["table_name"],
    )
    op.create_index(
        "ix_crud_generation_records_is_deleted",
        "crud_generation_records",
        ["is_deleted"],
    )


def downgrade() -> None:
    op.drop_index("ix_crud_generation_records_is_deleted", "crud_generation_records")
    op.drop_index("ix_cgr_table_name", "crud_generation_records")
    op.drop_index("ix_cgr_module_name", "crud_generation_records")
    op.drop_index("ix_cgr_status", "crud_generation_records")
    op.drop_index("ix_cgr_operation_type", "crud_generation_records")
    op.drop_index("ix_cgr_operator_created", "crud_generation_records")
    op.drop_table("crud_generation_records")
