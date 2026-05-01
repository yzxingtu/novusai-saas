"""Retired historical migration (no-op)."""

from __future__ import annotations

revision = "20260207_002_add_ai_usage_stats"
down_revision = "20260120_001_add_ai_providers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
