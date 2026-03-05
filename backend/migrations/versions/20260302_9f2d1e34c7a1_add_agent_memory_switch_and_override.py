"""add_agent_memory_switch_and_override

Revision ID: 9f2d1e34c7a1
Revises: 075fdfee8a70
Create Date: 2026-03-02 11:20:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9f2d1e34c7a1"
down_revision: str | None = "075fdfee8a70"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add admin/tenant memory switch persistence."""
    # 1) Agent 管理端开关（默认开启）
    op.add_column(
        "agents",
        sa.Column(
            "memory_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="会话记忆开关（管理端 Agent 级）",
        ),
    )

    # 移除 server_default，保持应用层默认
    op.alter_column("agents", "memory_enabled", server_default=None)

    # 2) 租户覆盖表（仅 disabled=true 的覆盖语义）
    op.create_table(
        "agent_memory_overrides",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("delete_level", sa.String(length=20), nullable=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("disabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        op.f("ix_agent_memory_overrides_agent_id"),
        "agent_memory_overrides",
        ["agent_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_memory_overrides_tenant_id"),
        "agent_memory_overrides",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "uq_agent_memory_overrides_tenant_agent",
        "agent_memory_overrides",
        ["tenant_id", "agent_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_agent_memory_overrides_is_deleted"),
        "agent_memory_overrides",
        ["is_deleted"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_memory_overrides_id"),
        "agent_memory_overrides",
        ["id"],
        unique=False,
    )

    # 3) 平台配置项：platform_default_memory_enabled
    op.execute(
        """
        INSERT INTO system_configs (
            key, group_id, name_key, description_key, scope, value_type,
            default_value, validation_rules, options,
            is_required, is_visible, is_encrypted, sort_order,
            created_at, updated_at, is_deleted
        )
        SELECT
            'platform_default_memory_enabled',
            g.id,
            'config.platform.platform_default_memory_enabled.name',
            'config.platform.platform_default_memory_enabled.desc',
            'admin_only',
            'boolean',
            'true',
            NULL,
            NULL,
            false,
            true,
            false,
            10,
            NOW(),
            NOW(),
            false
        FROM system_config_groups g
        WHERE g.code = 'platform_ai_memory'
          AND NOT EXISTS (
              SELECT 1 FROM system_configs c
              WHERE c.key = 'platform_default_memory_enabled'
                AND c.is_deleted = false
          );
        """
    )


def downgrade() -> None:
    """Remove admin/tenant memory switch persistence."""
    # 删除平台配置项（仅当前 key）
    op.execute(
        """
        DELETE FROM system_configs
        WHERE key = 'platform_default_memory_enabled';
        """
    )

    # 删除租户覆盖表
    op.drop_index(op.f("ix_agent_memory_overrides_id"), table_name="agent_memory_overrides")
    op.drop_index(op.f("ix_agent_memory_overrides_is_deleted"), table_name="agent_memory_overrides")
    op.drop_index("uq_agent_memory_overrides_tenant_agent", table_name="agent_memory_overrides")
    op.drop_index(op.f("ix_agent_memory_overrides_tenant_id"), table_name="agent_memory_overrides")
    op.drop_index(op.f("ix_agent_memory_overrides_agent_id"), table_name="agent_memory_overrides")
    op.drop_table("agent_memory_overrides")

    # 删除 agents.memory_enabled
    op.drop_column("agents", "memory_enabled")
