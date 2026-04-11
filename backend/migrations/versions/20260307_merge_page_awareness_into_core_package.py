"""retired: merge page awareness package into core package (no-op)

Revision ID: 20260307_merge_page_pkg
Revises: 20260307_fix_op_timeout
Create Date: 2026-03-07 11:00:00.000000+00:00

Retired by UI Runtime migration. Kept only to preserve revision chain.
"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "20260307_merge_page_pkg"
down_revision: str | Sequence[str] | None = "20260307_fix_op_timeout"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    # Retired migration: intentionally no-op.
    pass


def downgrade() -> None:
    # Retired migration: intentionally no-op.
    pass
