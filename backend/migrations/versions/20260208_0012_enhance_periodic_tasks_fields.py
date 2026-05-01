"""Retired historical migration (no-op)."""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "20260208_0012"
down_revision: str | Sequence[str] | None = "20260208_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
