"""中文: 为企业任务绑定添加禁用原因。

EN: Add disabled reason to tenant task bindings.

Revision ID: 20260507_0030_binding_disable
Revises: 20260507_0029_task_run_key
Create Date: 2026-05-07

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260507_0030_binding_disable"
down_revision: str | Sequence[str] | None = "20260507_0029_task_run_key"
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


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "tenant_task_bindings"):
        return
    if not _has_column(bind, "tenant_task_bindings", "disabled_reason"):
        op.add_column(
            "tenant_task_bindings",
            sa.Column(
                "disabled_reason",
                sa.Text(),
                nullable=True,
                comment="禁用原因",
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if _has_column(bind, "tenant_task_bindings", "disabled_reason"):
        op.drop_column("tenant_task_bindings", "disabled_reason")
