"""retired by UI Runtime migration

This revision previously adjusted legacy page-tool runtime metadata.
It is intentionally retained as an explicit no-op to preserve migration graph integrity.

Revision ID: 20260316_page_op_v3
Revises: 20260316_novusdoc_scope
Create Date: 2026-03-16 02:00:00.000000+00:00

"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "20260316_page_op_v3"
down_revision: str | Sequence[str] | None = "20260316_novusdoc_scope"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    print("[MIGRATION] retired by UI Runtime migration; no-op.")


def downgrade() -> None:
    print("[MIGRATION] retired by UI Runtime migration; no-op.")
