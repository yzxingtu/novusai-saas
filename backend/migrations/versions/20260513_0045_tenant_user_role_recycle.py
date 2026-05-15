"""中文: 修复企业用户角色回收站字段。

EN: Repair recycle-bin columns for tenant user roles.

Revision ID: 20260513_0045_tur_recycle
Revises: 20260513_0044_retire_llm_builtin
Create Date: 2026-05-13

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import or_

revision: str = "20260513_0045_tur_recycle"
down_revision: str | Sequence[str] | None = "20260513_0044_retire_llm_builtin"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_NAME = "tenant_user_roles"
INDEX_NAME = "ix_tenant_user_roles_recycle_stage"


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


def _repair_columns() -> tuple[sa.Column, ...]:
    return (
        sa.Column(
            "deleted_at", sa.DateTime(), nullable=True, comment="删除时间 / Deleted at"
        ),
        sa.Column(
            "delete_level",
            sa.String(length=20),
            nullable=True,
            comment="删除侧别 / Delete scope: tenant/admin",
        ),
        sa.Column(
            "recycle_stage",
            sa.String(length=20),
            nullable=True,
            comment="回收站阶段 / Recycle stage: module/global",
        ),
        sa.Column(
            "promoted_to_global_at",
            sa.DateTime(),
            nullable=True,
            comment="进入总回收站时间 / Promoted to global recycle bin at",
        ),
    )


def _add_missing_columns(bind: sa.Connection) -> None:
    columns = _column_names(bind, TABLE_NAME)
    for column in _repair_columns():
        if column.name not in columns:
            op.add_column(TABLE_NAME, column)


def _create_missing_index(bind: sa.Connection) -> None:
    if INDEX_NAME not in _index_names(bind, TABLE_NAME):
        op.create_index(INDEX_NAME, TABLE_NAME, ["recycle_stage"], unique=False)


def _backfill_recycle_state() -> None:
    table = sa.table(
        TABLE_NAME,
        sa.column("is_deleted"),
        sa.column("deleted_at"),
        sa.column("delete_level"),
        sa.column("recycle_stage"),
        sa.column("promoted_to_global_at"),
    )
    op.execute(
        sa.update(table)
        .where(table.c.is_deleted.is_(False))
        .values(recycle_stage=None, promoted_to_global_at=None)
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
        .values(recycle_stage="module", promoted_to_global_at=None)
    )
    op.execute(
        sa.update(table)
        .where(table.c.is_deleted.is_(True))
        .where(table.c.recycle_stage == "global")
        .where(table.c.promoted_to_global_at.is_(None))
        .values(promoted_to_global_at=table.c.deleted_at)
    )


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, TABLE_NAME):
        return
    _add_missing_columns(bind)
    _create_missing_index(bind)
    _backfill_recycle_state()


def downgrade() -> None:
    pass
