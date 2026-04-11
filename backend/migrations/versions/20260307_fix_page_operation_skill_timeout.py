"""retired by UI Runtime migration

This revision previously adjusted legacy page-tool runtime metadata.
It is intentionally retained as an explicit no-op to preserve migration graph integrity.

Revision ID: 20260307_fix_op_timeout
Revises: 20260306_invoke_page_op
Create Date: 2026-03-07 10:00:00.000000+00:00

"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "20260307_fix_op_timeout"
down_revision: str | Sequence[str] | None = "20260306_invoke_page_op"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    print("[MIGRATION] retired by UI Runtime migration; no-op.")


def downgrade() -> None:
    print("[MIGRATION] retired by UI Runtime migration; no-op.")
