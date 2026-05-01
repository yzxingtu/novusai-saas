"""Retired historical migration (no-op)."""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "20260401_drop_ephem_docs"
down_revision: str | Sequence[str] | None = "20260331_0010_sgs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
