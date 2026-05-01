"""Retired historical migration (no-op)."""

from collections.abc import Sequence

revision: str = "20260329_0020"
down_revision: str | None = "20260329_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
