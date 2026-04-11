"""retired by UI Runtime migration

This revision previously adjusted legacy page-tool runtime metadata.
It is intentionally retained as an explicit no-op to preserve migration graph integrity.

Revision ID: 20260321_page_op_boundary
Revises: 20260320_data_mgmt_desc
Create Date: 2026-03-21 00:00:00.000000+00:00

"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "20260321_page_op_boundary"
down_revision: str | Sequence[str] | None = "20260320_data_mgmt_desc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    print("[MIGRATION] retired by UI Runtime migration; no-op.")


def downgrade() -> None:
    print("[MIGRATION] retired by UI Runtime migration; no-op.")
