"""Retired historical migration (no-op).

Revision ID: 20260323_acl_ars
Revises: 20260321_akso
Create Date: 2026-03-23
"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "20260323_acl_ars"
down_revision: str | Sequence[str] | None = "20260321_akso"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
