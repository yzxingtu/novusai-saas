"""add target_audience, is_recommended to skill_packages/agents and role_ids to agent_access

Revision ID: 20260308_target_audience
Revises: 20260307_router_zh
Create Date: 2026-03-08 22:00:00.000000+00:00

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260308_target_audience"
down_revision: str | Sequence[str] | None = "20260307_router_zh"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add target_audience + is_recommended to skill_packages,
    target_audience to agents,
    and admin/tenant/user_role_ids to agent_access."""

    # ── skill_packages ──────────────────────────────────────────────────────
    op.add_column(
        "skill_packages",
        sa.Column(
            "target_audience",
            sa.String(20),
            nullable=False,
            server_default="all",
            comment="目标受众：all / admin_only / admin_tenant",
        ),
    )
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
    op.create_index(
        "ix_skill_packages_target_audience",
        "skill_packages",
        ["target_audience"],
    )

    # ── agents ──────────────────────────────────────────────────────────────
    op.add_column(
        "agents",
        sa.Column(
            "target_audience",
            sa.String(20),
            nullable=False,
            server_default="admin_tenant",
            comment="目标受众：all / admin_only / admin_tenant",
        ),
    )
    op.create_index(
        "ix_agents_target_audience",
        "agents",
        ["target_audience"],
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
    op.add_column(
        "agent_access",
        sa.Column(
            "user_role_ids",
            sa.JSON(),
            nullable=True,
            comment="用户端角色 ID 列表",
        ),
    )


def downgrade() -> None:
    """Remove added columns and indexes."""

    # agent_access
    op.drop_column("agent_access", "user_role_ids")
    op.drop_column("agent_access", "tenant_role_ids")
    op.drop_column("agent_access", "admin_role_ids")

    # agents
    op.drop_index("ix_agents_target_audience", table_name="agents")
    op.drop_column("agents", "target_audience")

    # skill_packages
    op.drop_index("ix_skill_packages_target_audience", table_name="skill_packages")
    op.drop_column("skill_packages", "is_recommended")
    op.drop_column("skill_packages", "target_audience")
