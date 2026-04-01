# -*- coding: utf-8 -*-
"""Add task_logs table

Revision ID: 20260208_0009
Revises: 20260126_0008
Create Date: 2026-02-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260208_0009"
down_revision: Union[str, None] = "20260126_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "task_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("task_id", sa.String(length=64), nullable=False, index=True, comment="Celery Task ID"),
        sa.Column("task_name", sa.String(length=255), nullable=False, comment="任务名称"),
        sa.Column("queue", sa.String(length=50), nullable=False, server_default="default", comment="队列名称"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending", comment="任务状态"),
        sa.Column("args", postgresql.JSON(), nullable=True, comment="位置参数"),
        sa.Column("kwargs", postgresql.JSON(), nullable=True, comment="关键字参数"),
        sa.Column("result", postgresql.JSON(), nullable=True, comment="执行结果"),
        sa.Column("error_message", sa.Text(), nullable=True, comment="错误信息"),
        sa.Column("traceback", sa.Text(), nullable=True, comment="异常堆栈"),
        sa.Column("started_at", sa.DateTime(), nullable=True, comment="开始时间"),
        sa.Column("finished_at", sa.DateTime(), nullable=True, comment="完成时间"),
        sa.Column("duration_ms", sa.Integer(), nullable=True, comment="耗时(毫秒)"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0", comment="重试次数"),
        sa.Column("tenant_id", sa.Integer(), nullable=True, comment="企业ID(可选)"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now(), comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now(), comment="更新时间"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false", index=True, comment="软删除标记"),
    )

    op.create_index("ix_task_logs_name_status", "task_logs", ["task_name", "status"])
    op.create_index("ix_task_logs_tenant_id", "task_logs", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_task_logs_tenant_id", table_name="task_logs")
    op.drop_index("ix_task_logs_name_status", table_name="task_logs")
    op.drop_table("task_logs")
