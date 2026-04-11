"""retired: builtin skill seed migration (no-op)

Revision ID: 20260306_invoke_page_op
Revises: 20260306_page_awareness_skill
Create Date: 2026-03-06 13:20:00.000000+00:00

Retired by UI Runtime migration. Kept only to preserve revision chain.
"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "20260306_invoke_page_op"
down_revision: str | Sequence[str] | None = "20260306_page_awareness_skill"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    # Retired migration: intentionally no-op.
    pass


def downgrade() -> None:
    # Retired migration: intentionally no-op.
    pass
