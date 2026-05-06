"""中文: 为任务运行增加业务幂等键。

EN: Add a business idempotency key to task runs.

Revision ID: 20260507_0029_task_run_key
Revises: 20260506_0028_drop_novus_rich
Create Date: 2026-05-07

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260507_0029_task_run_key"
down_revision: str | Sequence[str] | None = "20260506_0028_drop_novus_rich"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(bind, table_name: str) -> bool:
    inspector = sa.inspect(bind)
    return inspector.has_table(table_name)


def _has_column(bind, table_name: str, column_name: str) -> bool:
    if not _has_table(bind, table_name):
        return False
    inspector = sa.inspect(bind)
    return any(
        column.get("name") == column_name
        for column in inspector.get_columns(table_name)
    )


def _has_index(bind, table_name: str, index_name: str) -> bool:
    if not _has_table(bind, table_name):
        return False
    inspector = sa.inspect(bind)
    return any(
        index.get("name") == index_name for index in inspector.get_indexes(table_name)
    )


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "task_runs"):
        return
    if not _has_column(bind, "task_runs", "run_key"):
        op.add_column(
            "task_runs",
            sa.Column(
                "run_key",
                sa.String(length=255),
                nullable=True,
                comment="业务运行幂等键",
            ),
        )
    if not _has_index(bind, "task_runs", "ix_task_runs_run_key"):
        op.create_index(
            "ix_task_runs_run_key",
            "task_runs",
            ["run_key"],
            unique=True,
            postgresql_where=sa.text("run_key IS NOT NULL"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "task_runs"):
        return
    if _has_index(bind, "task_runs", "ix_task_runs_run_key"):
        op.drop_index("ix_task_runs_run_key", table_name="task_runs")
    if _has_column(bind, "task_runs", "run_key"):
        op.drop_column("task_runs", "run_key")
