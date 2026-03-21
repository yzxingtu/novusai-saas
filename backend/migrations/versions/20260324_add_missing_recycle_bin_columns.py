"""Repair recycle-bin state columns and task seed data

Revision ID: 20260324_bm_recycle_cols
Revises: 20260324_pt_otid_repair

BaseModel now distinguishes delete scope (delete_level) from recycle stage
(recycle_stage / promoted_to_global_at). Some databases only have the older
delete_level semantics and some periodic-task rows still use an invalid
legacy scope value.

This repair migration is idempotent:
- finds tables that match the BaseModel column footprint
- adds recycle_stage/promoted_to_global_at when missing
- creates recycle_stage index when missing
- backfills recycle state for legacy soft-deleted rows
- repairs recycle-bin cleanup periodic-task seed data

No downgrade is provided because these columns are now part of the shared ORM
BaseModel contract.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, or_

revision: str = "20260324_bm_recycle_cols"
down_revision: str | Sequence[str] | None = "20260324_pt_otid_repair"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BASE_MODEL_MARKERS = {
    "id",
    "created_at",
    "updated_at",
    "is_deleted",
    "deleted_at",
    "delete_level",
}
_SKIP_TABLES = {"alembic_version"}


def _column_names(bind, table: str) -> set[str]:
    return {c["name"] for c in inspect(bind).get_columns(table)}


def _index_names(bind, table: str) -> set[str]:
    return {idx["name"] for idx in inspect(bind).get_indexes(table)}


def _iter_base_model_tables(bind):
    insp = inspect(bind)
    for table in insp.get_table_names():
        if table in _SKIP_TABLES:
            continue
        cols = {c["name"] for c in insp.get_columns(table)}
        if _BASE_MODEL_MARKERS.issubset(cols):
            yield table, cols


def _backfill_recycle_state(table_name: str) -> None:
    table = sa.table(
        table_name,
        sa.column("is_deleted"),
        sa.column("delete_level"),
        sa.column("deleted_at"),
        sa.column("recycle_stage"),
        sa.column("promoted_to_global_at"),
    )
    op.execute(
        sa.update(table)
        .where(table.c.is_deleted.is_(False))
        .values(
            recycle_stage=None,
            promoted_to_global_at=None,
        )
    )
    op.execute(
        sa.update(table)
        .where(table.c.is_deleted.is_(True))
        .where(table.c.delete_level == "admin")
        .values(
            recycle_stage="global",
            promoted_to_global_at=sa.func.coalesce(
                table.c.promoted_to_global_at,
                table.c.deleted_at,
            ),
        )
    )
    op.execute(
        sa.update(table)
        .where(table.c.is_deleted.is_(True))
        .where(or_(table.c.delete_level == "tenant", table.c.delete_level.is_(None)))
        .where(table.c.recycle_stage.is_(None))
        .values(
            recycle_stage="module",
            promoted_to_global_at=None,
        )
    )
    op.execute(
        sa.update(table)
        .where(table.c.is_deleted.is_(True))
        .where(table.c.recycle_stage == "global")
        .where(table.c.promoted_to_global_at.is_(None))
        .values(promoted_to_global_at=table.c.deleted_at)
    )


def _repair_recycle_cleanup_periodic_task() -> None:
    op.execute(
        sa.text(
            """
            UPDATE periodic_tasks
            SET
                scope = 'admin_only',
                kwargs = '{"module_retention_days": 30, "global_retention_days": 30}',
                description = '每天凌晨 3 点推进模块回收站过期记录到总回收站，并清理总回收站过期记录',
                updated_at = NOW()
            WHERE task_path = 'app.tasks.recycle_bin.cleanup_recycle_bin'
            """
        )
    )


def upgrade() -> None:
    bind = op.get_bind()

    for table_name, cols in _iter_base_model_tables(bind):
        if "recycle_stage" not in cols:
            op.add_column(
                table_name,
                sa.Column(
                    "recycle_stage",
                    sa.String(length=20),
                    nullable=True,
                    comment="回收站阶段 / Recycle stage: module/global",
                ),
            )

        if "promoted_to_global_at" not in cols:
            op.add_column(
                table_name,
                sa.Column(
                    "promoted_to_global_at",
                    sa.DateTime(),
                    nullable=True,
                    comment="进入总回收站时间 / Promoted to global recycle bin at",
                ),
            )

        index_name = f"ix_{table_name}_recycle_stage"
        if index_name not in _index_names(bind, table_name):
            op.create_index(index_name, table_name, ["recycle_stage"], unique=False)

        _backfill_recycle_state(table_name)

    _repair_recycle_cleanup_periodic_task()


def downgrade() -> None:
    pass
