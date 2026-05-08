"""中文: 清理当前库中未纳入工作树的 AI ledger 残留表。

EN: Drop AI ledger tables that are not part of the current working tree.

Revision ID: 20260509_0040_drop_ledgers
Revises: 20260509_0039_skill_status
Create Date: 2026-05-09

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260509_0040_drop_ledgers"
down_revision: str | Sequence[str] | None = "20260509_0039_skill_status"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DIRTY_LEDGER_TABLES = (
    "ai_recovery_events",
    "ai_tool_execution_ledgers",
    "ai_turn_ledgers",
)


def _drop_table_if_exists(bind: sa.Connection, table_name: str) -> None:
    if sa.inspect(bind).has_table(table_name):
        op.drop_table(table_name)


def upgrade() -> None:
    bind = op.get_bind()
    for table_name in DIRTY_LEDGER_TABLES:
        _drop_table_if_exists(bind, table_name)


def downgrade() -> None:
    # 中文: 这是本地残留表清理迁移；恢复旧 ledger 数据请使用执行前的数据库备份。
    # EN: This cleanup removes local residual tables; restore old ledger data from the pre-migration database backup.
    pass
