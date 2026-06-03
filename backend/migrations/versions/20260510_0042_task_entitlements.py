"""中文: 为任务定义增加企业权益要求。

EN: Add tenant entitlement requirements to task definitions.

Revision ID: 20260510_0042_task_entitlements
Revises: 20260509_0041_log_pages
Create Date: 2026-05-10

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260510_0042_task_entitlements"
down_revision: str | Sequence[str] | None = "20260509_0041_log_pages"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(bind: sa.Connection, table_name: str) -> bool:
    return sa.inspect(bind).has_table(table_name)


def _column_names(bind: sa.Connection, table_name: str) -> set[str]:
    if not _has_table(bind, table_name):
        return set()
    return {column["name"] for column in sa.inspect(bind).get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "task_definitions"):
        return

    columns = _column_names(bind, "task_definitions")
    if "required_feature_codes" not in columns:
        op.add_column(
            "task_definitions",
            sa.Column(
                "required_feature_codes",
                sa.JSON(),
                nullable=True,
                comment="要求的企业套餐特性代码 / Required tenant plan feature codes",
            ),
        )
    if "required_plugin_names" not in columns:
        op.add_column(
            "task_definitions",
            sa.Column(
                "required_plugin_names",
                sa.JSON(),
                nullable=True,
                comment="要求的企业可用插件名称 / Required tenant-visible plugin names",
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "task_definitions"):
        return

    columns = _column_names(bind, "task_definitions")
    if "required_plugin_names" in columns:
        op.drop_column("task_definitions", "required_plugin_names")
    if "required_feature_codes" in columns:
        op.drop_column("task_definitions", "required_feature_codes")
