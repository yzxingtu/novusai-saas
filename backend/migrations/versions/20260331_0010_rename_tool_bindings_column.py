"""Rename agent_versions.tool_bindings → skill_grant_snapshot

Revision ID: 20260331_0010_sgs
Revises: 20260330_0110_permrename
Create Date: 2026-03-31
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "20260331_0010_sgs"
down_revision: str | Sequence[str] | None = "20260330_0110_permrename"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "agent_versions",
        "tool_bindings",
        new_column_name="skill_grant_snapshot",
    )


def downgrade() -> None:
    op.alter_column(
        "agent_versions",
        "skill_grant_snapshot",
        new_column_name="tool_bindings",
    )
