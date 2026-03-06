"""fix invoke_page_operation skill timeout (15 → 45s)

The skill timeout (15s) was shorter than PAGE_OPERATION_TIMEOUT (30s),
causing the sandbox to cancel the executor before the WebSocket timeout
could fire with an informative error message.

Revision ID: 20260307_fix_op_timeout
Revises: 20260306_invoke_page_op
Create Date: 2026-03-07 10:00:00.000000+00:00

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "20260307_fix_op_timeout"
down_revision: str | Sequence[str] | None = "20260306_invoke_page_op"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SKILL_NAME = "invoke_page_operation"
NEW_TIMEOUT = 45
OLD_TIMEOUT = 15


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
