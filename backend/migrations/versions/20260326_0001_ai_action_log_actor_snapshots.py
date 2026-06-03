"""Add actor snapshot columns to ai_action_logs

Revision ID: 20260326_0001_ai_log_snap
Revises: 20260325_drop_legacy_task_tables, 20260325_org_node_perm
Create Date: 2026-03-26
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260326_0001_ai_log_snap"
down_revision: str | Sequence[str] | None = (
    "20260325_drop_legacy_task_tables",
    "20260325_org_node_perm",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ai_action_logs",
        sa.Column("operator_type", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "ai_action_logs",
        sa.Column("agent_name_snapshot", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "ai_action_logs",
        sa.Column("agent_avatar_snapshot", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "ai_action_logs",
        sa.Column("operator_name_snapshot", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "ai_action_logs",
        sa.Column(
            "operator_nickname_snapshot",
            sa.String(length=255),
            nullable=True,
        ),
    )
    op.add_column(
        "ai_action_logs",
        sa.Column("operator_avatar_snapshot", sa.String(length=500), nullable=True),
    )

    # Backfill agent snapshots for rows that already reference a valid agent.
    op.execute(
        sa.text(
            """
            UPDATE ai_action_logs AS log
            SET
              agent_name_snapshot = agent.name,
              agent_avatar_snapshot = agent.avatar
            FROM agents AS agent
            WHERE
              log.agent_id > 0
              AND log.agent_id = agent.id
              AND agent.is_deleted IS FALSE
            """
        )
    )

    # Platform-side actor backfill is deterministic because tenant_id=0 only maps to admins.
    op.execute(
        sa.text(
            """
            UPDATE ai_action_logs AS log
            SET
              operator_type = 'platform_admin',
              operator_name_snapshot = admin.username,
              operator_nickname_snapshot = admin.nickname,
              operator_avatar_snapshot = admin.avatar
            FROM admins AS admin
            WHERE
              log.tenant_id = 0
              AND log.operator_id = admin.id
              AND admin.is_deleted IS FALSE
            """
        )
    )

    # Tenant-side historical rows do not store actor type, so we backfill with best-effort priority:
    # tenant_admin first, then tenant_user for still-unresolved rows.
    op.execute(
        sa.text(
            """
            UPDATE ai_action_logs AS log
            SET
              operator_type = 'tenant_admin',
              operator_name_snapshot = admin.username,
              operator_nickname_snapshot = admin.nickname,
              operator_avatar_snapshot = admin.avatar
            FROM tenant_admins AS admin
            WHERE
              log.tenant_id > 0
              AND log.tenant_id = admin.tenant_id
              AND log.operator_id = admin.id
              AND admin.is_deleted IS FALSE
            """
        )
    )

    op.execute(
        sa.text(
            """
            UPDATE ai_action_logs AS log
            SET
              operator_type = 'tenant_user',
              operator_name_snapshot = user_row.username,
              operator_nickname_snapshot = user_row.nickname,
              operator_avatar_snapshot = user_row.avatar
            FROM tenant_users AS user_row
            WHERE
              log.operator_type IS NULL
              AND log.tenant_id > 0
              AND log.tenant_id = user_row.tenant_id
              AND log.operator_id = user_row.id
              AND user_row.is_deleted IS FALSE
            """
        )
    )


def downgrade() -> None:
    op.drop_column("ai_action_logs", "operator_avatar_snapshot")
    op.drop_column("ai_action_logs", "operator_nickname_snapshot")
    op.drop_column("ai_action_logs", "operator_name_snapshot")
    op.drop_column("ai_action_logs", "agent_avatar_snapshot")
    op.drop_column("ai_action_logs", "agent_name_snapshot")
    op.drop_column("ai_action_logs", "operator_type")
