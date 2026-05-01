"""add current recommendation and role access fields

Revision ID: 20260308_access_fields
Revises: 20260307_router_zh
Create Date: 2026-03-08 22:00:00.000000+00:00

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260308_access_fields"
down_revision: str | Sequence[str] | None = "20260307_router_zh"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add current skill package recommendation and agent access role fields."""

    # ── skill_packages ──────────────────────────────────────────────────────
    op.add_column(
        "skill_packages",
        sa.Column(
            "is_recommended",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="是否推荐技能包",
        ),
    )
    # ── agent_access ────────────────────────────────────────────────────────
    op.add_column(
        "agent_access",
        sa.Column(
            "admin_role_ids",
            sa.JSON(),
            nullable=True,
            comment="管理端角色 ID 列表",
        ),
    )
    op.add_column(
        "agent_access",
        sa.Column(
            "tenant_role_ids",
            sa.JSON(),
            nullable=True,
            comment="企业端角色 ID 列表",
        ),
    )


def downgrade() -> None:
    """Remove added columns and indexes."""

    # agent_access
    op.drop_column("agent_access", "tenant_role_ids")
    op.drop_column("agent_access", "admin_role_ids")

    # skill_packages
    op.drop_column("skill_packages", "is_recommended")
