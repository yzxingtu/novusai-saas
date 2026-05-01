"""Retired historical migration (no-op)."""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "20260324_drop_skill_pkg_aud"
down_revision: str | Sequence[str] | None = "20260324_plugin_license_sem"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
