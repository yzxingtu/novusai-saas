"""Add conversation owner_type and normalize session memory task scope

Revision ID: 20260324_conv_owner_scope
Revises: 20260324_bm_recycle_cols
Create Date: 2026-03-24
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "20260324_conv_owner_scope"
down_revision: str | Sequence[str] | None = "20260324_bm_recycle_cols"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PLATFORM_TENANT_ID = 0
_TASK_PATH = "app.tasks.scheduled.clean_expired_session_memories"


def _update_session_memory_task_scope(new_scope: str, old_scope: str) -> None:
    op.execute(
        sa.text(
            """
            UPDATE periodic_tasks
            SET scope = :new_scope, updated_at = NOW()
            WHERE task_path = :task_path AND scope = :old_scope
            """
        ).bindparams(
            new_scope=new_scope,
            old_scope=old_scope,
            task_path=_TASK_PATH,
        )
    )


def _backfill_conversation_owner_type() -> None:
    op.execute(
        sa.text(
            """
            UPDATE agent_conversations
            SET owner_type = :platform_admin
            WHERE owner_type = :unknown
              AND (tenant_id = :platform_tenant_id OR tenant_id IS NULL)
            """
        ).bindparams(
            platform_admin="platform_admin",
            unknown="unknown",
            platform_tenant_id=_PLATFORM_TENANT_ID,
        )
    )

    op.execute(
        sa.text(
            """
            UPDATE agent_conversations AS ac
            SET owner_type = :tenant_admin
            WHERE ac.owner_type = :unknown
              AND ac.tenant_id != :platform_tenant_id
              AND ac.user_id IS NOT NULL
              AND EXISTS (
                  SELECT 1
                  FROM tenant_admins AS ta
                  WHERE ta.tenant_id = ac.tenant_id
                    AND ta.id = ac.user_id
                    AND ta.is_deleted = FALSE
              )
              AND NOT EXISTS (
                  SELECT 1
                  FROM tenant_users AS tu
                  WHERE tu.tenant_id = ac.tenant_id
                    AND tu.id = ac.user_id
                    AND tu.is_deleted = FALSE
              )
            """
        ).bindparams(
            tenant_admin="tenant_admin",
            unknown="unknown",
            platform_tenant_id=_PLATFORM_TENANT_ID,
        )
    )

    op.execute(
        sa.text(
            """
            UPDATE agent_conversations AS ac
            SET owner_type = :tenant_user
            WHERE ac.owner_type = :unknown
              AND ac.tenant_id != :platform_tenant_id
              AND ac.user_id IS NOT NULL
              AND EXISTS (
                  SELECT 1
                  FROM tenant_users AS tu
                  WHERE tu.tenant_id = ac.tenant_id
                    AND tu.id = ac.user_id
                    AND tu.is_deleted = FALSE
              )
              AND NOT EXISTS (
                  SELECT 1
                  FROM tenant_admins AS ta
                  WHERE ta.tenant_id = ac.tenant_id
                    AND ta.id = ac.user_id
                    AND ta.is_deleted = FALSE
              )
            """
        ).bindparams(
            tenant_user="tenant_user",
            unknown="unknown",
            platform_tenant_id=_PLATFORM_TENANT_ID,
        )
    )

    op.execute(
        sa.text(
            """
            UPDATE agent_conversations
            SET owner_type = :unknown
            WHERE owner_type IS NULL
            """
        ).bindparams(unknown="unknown")
    )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("agent_conversations")}

    if "owner_type" not in columns:
        op.add_column(
            "agent_conversations",
            sa.Column(
                "owner_type",
                sa.String(length=32),
                nullable=True,
                server_default="unknown",
                comment="会话归属类型 / Conversation owner type",
            ),
        )

    _backfill_conversation_owner_type()

    op.alter_column(
        "agent_conversations",
        "owner_type",
        existing_type=sa.String(length=32),
        nullable=False,
        server_default="unknown",
    )

    indexes = {
        idx["name"]
        for idx in inspector.get_indexes("agent_conversations")
    }
    if "ix_agent_conv_tenant_owner_user" not in indexes:
        op.create_index(
            "ix_agent_conv_tenant_owner_user",
            "agent_conversations",
            ["tenant_id", "owner_type", "user_id"],
            unique=False,
        )

    _update_session_memory_task_scope(
        new_scope="admin_only",
        old_scope="platform",
    )


def downgrade() -> None:
    _update_session_memory_task_scope(
        new_scope="platform",
        old_scope="admin_only",
    )
    op.drop_index(
        "ix_agent_conv_tenant_owner_user",
        table_name="agent_conversations",
    )
    op.drop_column("agent_conversations", "owner_type")
