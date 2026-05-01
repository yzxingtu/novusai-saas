"""Retired historical migration (no-op)."""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "63eadfe34156"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
