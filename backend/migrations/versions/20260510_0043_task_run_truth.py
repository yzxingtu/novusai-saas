"""中文: 持久化任务分发事实字段。

EN: Persist task dispatch truth fields.

Revision ID: 20260510_0043_task_run_truth
Revises: 20260510_0042_task_entitlements
Create Date: 2026-05-10

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260510_0043_task_run_truth"
down_revision: str | Sequence[str] | None = "20260510_0042_task_entitlements"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FK_RETRY_OF_RUN = "fk_task_runs_retry_of_run_id_task_runs"
IX_DEFINITION_TRIGGER_SLOT = "ix_task_runs_definition_trigger_slot"
IX_RETRY_OF_RUN = "ix_task_runs_retry_of_run_id"


def _has_table(bind: sa.Connection, table_name: str) -> bool:
    return sa.inspect(bind).has_table(table_name)


def _column_names(bind: sa.Connection, table_name: str) -> set[str]:
    if not _has_table(bind, table_name):
        return set()
    return {column["name"] for column in sa.inspect(bind).get_columns(table_name)}


def _index_names(bind: sa.Connection, table_name: str) -> set[str]:
    if not _has_table(bind, table_name):
        return set()
    return {index["name"] for index in sa.inspect(bind).get_indexes(table_name)}


def _foreign_key_names(bind: sa.Connection, table_name: str) -> set[str]:
    if not _has_table(bind, table_name):
        return set()
    return {
        fk["name"]
        for fk in sa.inspect(bind).get_foreign_keys(table_name)
        if fk.get("name")
    }


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "task_runs"):
        return

    columns = _column_names(bind, "task_runs")
    if "priority" not in columns:
        op.add_column(
            "task_runs",
            sa.Column(
                "priority",
                sa.Integer(),
                nullable=True,
                comment="Broker 优先级 / Broker priority",
            ),
        )
    if "trigger_slot" not in columns:
        op.add_column(
            "task_runs",
            sa.Column(
                "trigger_slot",
                sa.String(length=255),
                nullable=True,
                comment="调度槽位 / Scheduler trigger slot",
            ),
        )
    if "trigger_id" not in columns:
        op.add_column(
            "task_runs",
            sa.Column(
                "trigger_id",
                sa.String(length=255),
                nullable=True,
                comment="触发请求 ID / Trigger request id",
            ),
        )
    if "retry_of_run_id" not in columns:
        op.add_column(
            "task_runs",
            sa.Column(
                "retry_of_run_id",
                sa.Integer(),
                nullable=True,
                comment="重试来源运行 ID / Source run id for retry",
            ),
        )
    if "retry_of_task_id" not in columns:
        op.add_column(
            "task_runs",
            sa.Column(
                "retry_of_task_id",
                sa.String(length=100),
                nullable=True,
                comment="重试来源 Celery 任务 ID / Source Celery task id for retry",
            ),
        )

    columns = _column_names(bind, "task_runs")
    foreign_keys = _foreign_key_names(bind, "task_runs")
    if "retry_of_run_id" in columns and FK_RETRY_OF_RUN not in foreign_keys:
        op.create_foreign_key(
            FK_RETRY_OF_RUN,
            "task_runs",
            "task_runs",
            ["retry_of_run_id"],
            ["id"],
            ondelete="SET NULL",
        )

    indexes = _index_names(bind, "task_runs")
    if IX_DEFINITION_TRIGGER_SLOT not in indexes:
        op.create_index(
            IX_DEFINITION_TRIGGER_SLOT,
            "task_runs",
            ["task_definition_id", "trigger_slot"],
        )
    if IX_RETRY_OF_RUN not in indexes:
        op.create_index(IX_RETRY_OF_RUN, "task_runs", ["retry_of_run_id"])


def downgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "task_runs"):
        return

    indexes = _index_names(bind, "task_runs")
    if IX_RETRY_OF_RUN in indexes:
        op.drop_index(IX_RETRY_OF_RUN, table_name="task_runs")
    if IX_DEFINITION_TRIGGER_SLOT in indexes:
        op.drop_index(IX_DEFINITION_TRIGGER_SLOT, table_name="task_runs")

    foreign_keys = _foreign_key_names(bind, "task_runs")
    if FK_RETRY_OF_RUN in foreign_keys:
        op.drop_constraint(FK_RETRY_OF_RUN, "task_runs", type_="foreignkey")

    columns = _column_names(bind, "task_runs")
    for column_name in (
        "retry_of_task_id",
        "retry_of_run_id",
        "trigger_id",
        "trigger_slot",
        "priority",
    ):
        if column_name in columns:
            op.drop_column("task_runs", column_name)
