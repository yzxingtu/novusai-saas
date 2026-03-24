"""Drop legacy periodic_tasks and task_logs tables

Revision ID: 20260325_drop_legacy_task_tables
Revises: 20260325_backfill_task_defs
Create Date: 2026-03-25
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import inspect

revision: str = "20260325_drop_legacy_task_tables"
down_revision: str | Sequence[str] | None = "20260325_backfill_task_defs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(table_name: str) -> bool:
    return inspect(op.get_bind()).has_table(table_name)


def upgrade() -> None:
    if _has_table("task_logs"):
        op.drop_table("task_logs")
    if _has_table("periodic_tasks"):
        op.drop_table("periodic_tasks")


def downgrade() -> None:
    """Intentional no-op.

    Legacy task tables are removed as part of the migration to task_definitions /
    task_runs. Recreating them would reintroduce retired runtime paths.
    """
    pass
