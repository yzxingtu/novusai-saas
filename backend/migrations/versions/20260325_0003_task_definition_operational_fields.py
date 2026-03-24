"""Add operational fields to task definitions

Revision ID: 20260325_task_definition_ops
Revises: 20260325_task_sched_foundation
Create Date: 2026-03-25
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "20260325_task_definition_ops"
down_revision: str | Sequence[str] | None = "20260325_task_sched_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_names(bind, table: str) -> set[str]:
    inspector = inspect(bind)
    if not inspector.has_table(table):
        return set()
    return {col["name"] for col in inspector.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    columns = _column_names(bind, "task_definitions")
    if not columns:
        return

    additions: list[tuple[str, sa.Column]] = [
        (
            "max_retries",
            sa.Column(
                "max_retries",
                sa.Integer(),
                nullable=False,
                server_default="0",
                comment="最大重试次数",
            ),
        ),
        (
            "retry_delay",
            sa.Column(
                "retry_delay",
                sa.Integer(),
                nullable=False,
                server_default="60",
                comment="重试间隔（秒）",
            ),
        ),
        (
            "timeout",
            sa.Column(
                "timeout",
                sa.Integer(),
                nullable=False,
                server_default="3600",
                comment="执行超时（秒）",
            ),
        ),
        (
            "notify_on_failure",
            sa.Column(
                "notify_on_failure",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
                comment="失败时是否通知",
            ),
        ),
        (
            "notify_emails",
            sa.Column(
                "notify_emails",
                sa.Text(),
                nullable=True,
                comment="通知邮箱列表",
            ),
        ),
        (
            "last_run_at",
            sa.Column(
                "last_run_at",
                sa.DateTime(),
                nullable=True,
                comment="上次执行时间",
            ),
        ),
        (
            "next_run_at",
            sa.Column(
                "next_run_at",
                sa.DateTime(),
                nullable=True,
                comment="下次执行时间",
            ),
        ),
    ]

    for name, column in additions:
        if name not in columns:
            op.add_column("task_definitions", column)


def downgrade() -> None:
    for name in (
        "next_run_at",
        "last_run_at",
        "notify_emails",
        "notify_on_failure",
        "timeout",
        "retry_delay",
        "max_retries",
    ):
        op.drop_column("task_definitions", name)
