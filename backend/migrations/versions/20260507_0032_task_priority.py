"""中文: 为任务定义增加 Celery broker 优先级。

EN: Add Celery broker priority to task definitions.

Revision ID: 20260507_0032_task_priority
Revises: 20260507_0031_notif_gov
Create Date: 2026-05-07

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260507_0032_task_priority"
down_revision: str | Sequence[str] | None = "20260507_0031_notif_gov"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(bind, table_name: str) -> bool:
    return table_name in sa.inspect(bind).get_table_names()


def _column_names(bind, table_name: str) -> set[str]:
    if not _has_table(bind, table_name):
        return set()
    return {column["name"] for column in sa.inspect(bind).get_columns(table_name)}


def _index_names(bind, table_name: str) -> set[str]:
    if not _has_table(bind, table_name):
        return set()
    return {index["name"] for index in sa.inspect(bind).get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "task_definitions"):
        return

    columns = _column_names(bind, "task_definitions")
    if "default_priority" not in columns:
        op.add_column(
            "task_definitions",
            sa.Column(
                "default_priority",
                sa.Integer(),
                nullable=True,
                comment="默认队列优先级 / Default broker priority",
            ),
        )

    constraints = {
        constraint["name"]
        for constraint in sa.inspect(bind).get_check_constraints("task_definitions")
    }
    if "ck_task_definitions_default_priority_range" not in constraints:
        op.create_check_constraint(
            "ck_task_definitions_default_priority_range",
            "task_definitions",
            "default_priority IS NULL OR (default_priority >= 0 AND default_priority <= 9)",
        )

    if "ix_task_definitions_default_priority" not in _index_names(
        bind, "task_definitions"
    ):
        op.create_index(
            "ix_task_definitions_default_priority",
            "task_definitions",
            ["default_priority"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "task_definitions"):
        return

    if "ix_task_definitions_default_priority" in _index_names(bind, "task_definitions"):
        op.drop_index(
            "ix_task_definitions_default_priority",
            table_name="task_definitions",
        )

    constraints = {
        constraint["name"]
        for constraint in sa.inspect(bind).get_check_constraints("task_definitions")
    }
    if "ck_task_definitions_default_priority_range" in constraints:
        op.drop_constraint(
            "ck_task_definitions_default_priority_range",
            "task_definitions",
            type_="check",
        )

    if "default_priority" in _column_names(bind, "task_definitions"):
        op.drop_column("task_definitions", "default_priority")
