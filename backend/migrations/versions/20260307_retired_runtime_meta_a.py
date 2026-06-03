"""Retired historical migration (no-op)."""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "20260307_retired_runtime_a"
down_revision: str | Sequence[str] | None = "20260306_retired_runtime_b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
