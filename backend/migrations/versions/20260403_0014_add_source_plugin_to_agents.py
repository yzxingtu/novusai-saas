"""add source_plugin to agents and backfill NovusDoc Writer

Revision ID: 20260403_agent_src
Revises: 20260402_call_type
Create Date: 2026-04-03
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision: str = "20260403_agent_src"
down_revision: str | Sequence[str] | None = "20260402_call_type"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SOURCE_PLUGIN = "novusdoc"
_FEATURE_CODE = "system.ai_writing"
_AGENT_SCOPE_WITH_ASSIGNMENTS = {
    "selected_tenants",
    "admin_and_selected_tenants",
}


def _has_column(bind, table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(bind)
    return any(
        column["name"] == column_name
        for column in inspector.get_columns(table_name)
    )


def _has_index(bind, table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(bind)
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    bind = op.get_bind()

    if not _has_column(bind, "agents", "source_plugin"):
        op.add_column(
            "agents",
            sa.Column(
                "source_plugin",
                sa.String(length=100),
                nullable=True,
                comment="来源插件 slug（插件托管智能体）/ Source plugin slug",
            ),
        )

    if not _has_index(bind, "agents", "ix_agents_source_plugin"):
        op.create_index("ix_agents_source_plugin", "agents", ["source_plugin"])

    plugin_row = bind.execute(
        text(
            """
            SELECT id, scope
            FROM plugins
            WHERE name = :plugin_name
              AND is_deleted = false
            ORDER BY id
            LIMIT 1
            """
        ),
        {"plugin_name": _SOURCE_PLUGIN},
    ).mappings().first()
    if plugin_row is None:
        return

    assignment_row = bind.execute(
        text(
            """
            SELECT agent_id
            FROM system_agent_assignments
            WHERE feature_code = :feature_code
              AND tenant_id IS NULL
              AND is_deleted = false
            ORDER BY id
            LIMIT 1
            """
        ),
        {"feature_code": _FEATURE_CODE},
    ).fetchone()
    if assignment_row is None or assignment_row[0] is None:
        return

    agent_id = int(assignment_row[0])
    agent_exists = bind.execute(
        text(
            """
            SELECT id
            FROM agents
            WHERE id = :agent_id
              AND is_deleted = false
            LIMIT 1
            """
        ),
        {"agent_id": agent_id},
    ).fetchone()
    if agent_exists is None:
        return

    bind.execute(
        text(
            """
            UPDATE agents
            SET source_plugin = :source_plugin,
                scope = :scope,
                updated_at = NOW()
            WHERE id = :agent_id
            """
        ),
        {
            "agent_id": agent_id,
            "source_plugin": _SOURCE_PLUGIN,
            "scope": plugin_row["scope"],
        },
    )

    bind.execute(
        text(
            """
            DELETE FROM resource_tenant_assignments
            WHERE resource_type = 'agent'
              AND resource_id = :agent_id
            """
        ),
        {"agent_id": agent_id},
    )

    if plugin_row["scope"] not in _AGENT_SCOPE_WITH_ASSIGNMENTS:
        return

    tenant_rows = bind.execute(
        text(
            """
            SELECT tenant_id
            FROM resource_tenant_assignments
            WHERE resource_type = 'plugin'
              AND resource_id = :plugin_id
              AND is_deleted = false
              AND is_active = true
            ORDER BY tenant_id
            """
        ),
        {"plugin_id": int(plugin_row["id"])},
    ).fetchall()

    for (tenant_id,) in tenant_rows:
        bind.execute(
            text(
                """
                INSERT INTO resource_tenant_assignments (
                    resource_type,
                    resource_id,
                    tenant_id,
                    is_active,
                    config,
                    created_at,
                    updated_at,
                    is_deleted
                )
                VALUES (
                    'agent',
                    :agent_id,
                    :tenant_id,
                    true,
                    '{}'::jsonb,
                    NOW(),
                    NOW(),
                    false
                )
                """
            ),
            {
                "agent_id": agent_id,
                "tenant_id": int(tenant_id),
            },
        )


def downgrade() -> None:
    bind = op.get_bind()
    if _has_index(bind, "agents", "ix_agents_source_plugin"):
        op.drop_index("ix_agents_source_plugin", table_name="agents")
    if _has_column(bind, "agents", "source_plugin"):
        op.drop_column("agents", "source_plugin")
