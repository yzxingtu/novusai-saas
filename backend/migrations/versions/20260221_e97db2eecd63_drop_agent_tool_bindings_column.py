"""Retired historical migration (no-op)."""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "e97db2eecd63"
down_revision: str | Sequence[str] | None = "a5e1ff4cfca1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
