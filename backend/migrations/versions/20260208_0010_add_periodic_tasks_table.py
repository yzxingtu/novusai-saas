# -*- coding: utf-8 -*-
"""Add periodic_tasks table

Revision ID: 20260208_0010
Revises: 20260208_0009
Create Date: 2026-02-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260208_0010"
down_revision: Union[str, None] = "20260208_0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "periodic_tasks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=200), nullable=False, comment="任务名称（唯一）"),
        sa.Column("task_path", sa.String(length=255), nullable=False, comment="任务路径"),
        sa.Column("schedule_type", sa.String(length=20), nullable=False, server_default="interval", comment="调度类型"),
        sa.Column("cron_expression", sa.String(length=100), nullable=True, comment="Cron 表达式"),
        sa.Column("interval_seconds", sa.Integer(), nullable=True, comment="间隔秒数"),
        sa.Column("args", postgresql.JSON(), nullable=True, comment="位置参数"),
        sa.Column("kwargs", postgresql.JSON(), nullable=True, comment="关键字参数"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true", comment="是否启用"),
        sa.Column("last_run_at", sa.DateTime(), nullable=True, comment="上次执行时间"),
        sa.Column("next_run_at", sa.DateTime(), nullable=True, comment="下次执行时间"),
        sa.Column("description", sa.Text(), nullable=True, comment="任务描述"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now(), comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now(), comment="更新时间"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false", index=True, comment="软删除标记"),
        sa.UniqueConstraint("name", name="uq_periodic_tasks_name"),
    )


def downgrade() -> None:
    op.drop_table("periodic_tasks")
