"""retired by UI Runtime migration

This revision previously adjusted legacy page-tool runtime metadata.
It is intentionally retained as an explicit no-op to preserve migration graph integrity.

Revision ID: 20260319_page_op_75
Revises: 20260318_0004_data_scope
Create Date: 2026-03-19 00:00:00.000000+00:00

"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "20260319_page_op_75"
down_revision: str | Sequence[str] | None = "20260318_0004_data_scope"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    print("[MIGRATION] retired by UI Runtime migration; no-op.")


def downgrade() -> None:
    print("[MIGRATION] retired by UI Runtime migration; no-op.")
