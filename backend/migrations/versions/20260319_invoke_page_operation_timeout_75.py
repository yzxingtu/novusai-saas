"""invoke_page_operation skill timeout 45 -> 75s

PAGE_OPERATION_TIMEOUT 已调整为 60s，技能 timeout 需留 15s 缓冲。
PAGE_OPERATION_TIMEOUT is now 60s; skill timeout needs 15s buffer.

Revision ID: 20260319_page_op_75
Revises: 20260318_0004_data_scope
Create Date: 2026-03-19 00:00:00.000000+00:00

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "20260319_page_op_75"
down_revision: str | Sequence[str] | None = "20260318_0004_data_scope"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SKILL_NAME = "invoke_page_operation"
NEW_TIMEOUT = 75
OLD_TIMEOUT = 45


def upgrade() -> None:
    conn = op.get_bind()
    result = conn.execute(
        text(
            "UPDATE skills SET timeout = :new_timeout, updated_at = NOW() "
            "WHERE name = :name AND type = 'builtin' "
            "AND tenant_id IS NULL AND is_system = true AND is_deleted = false "
            "AND timeout = :old_timeout"
        ),
        {"name": SKILL_NAME, "new_timeout": NEW_TIMEOUT, "old_timeout": OLD_TIMEOUT},
    )
    print(f"[FIX] Updated {result.rowcount} skill(s) timeout: {OLD_TIMEOUT} → {NEW_TIMEOUT}s")


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        text(
            "UPDATE skills SET timeout = :old_timeout, updated_at = NOW() "
            "WHERE name = :name AND type = 'builtin' "
            "AND tenant_id IS NULL AND is_system = true AND is_deleted = false "
            "AND timeout = :new_timeout"
        ),
        {"name": SKILL_NAME, "new_timeout": NEW_TIMEOUT, "old_timeout": OLD_TIMEOUT},
    )
