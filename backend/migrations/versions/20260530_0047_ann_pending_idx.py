"""中文: 加固公告待办查询索引。

EN: Add bounded pending-announcement lookup index.

Revision ID: 20260530_0047_ann_pending_idx
Revises: 20260514_0046_oplog_surface
Create Date: 2026-05-30
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260530_0047_ann_pending_idx"
down_revision: str | Sequence[str] | None = "20260514_0046_oplog_surface"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_NAME = "announcement_deliveries"
INDEX_NAME = "idx_announcement_deliveries_pending_lookup"


def _has_table(bind: sa.Connection, table_name: str) -> bool:
    return sa.inspect(bind).has_table(table_name)


def _index_names(bind: sa.Connection, table_name: str) -> set[str]:
    if not _has_table(bind, table_name):
        return set()
    return {index["name"] for index in sa.inspect(bind).get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    if INDEX_NAME in _index_names(bind, TABLE_NAME):
        return
    op.create_index(
        INDEX_NAME,
        TABLE_NAME,
        ["tenant_id", "recipient_type", "recipient_id", "status"],
        unique=False,
        postgresql_where=sa.text("is_deleted = false"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    if INDEX_NAME in _index_names(bind, TABLE_NAME):
        op.drop_index(INDEX_NAME, table_name=TABLE_NAME)
