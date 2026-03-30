"""Clean up residual columns and legacy index names

Revision ID: 20260327_1930_residual_schema
Revises: 20260327_1500_cleanup_legacy
Create Date: 2026-03-27 19:30:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision: str = "20260327_1930_residual_schema"
down_revision: str | Sequence[str] | None = "20260327_1500_cleanup_legacy"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(table_name: str) -> bool:
    return inspect(op.get_bind()).has_table(table_name)


def _column_names(table_name: str) -> set[str]:
    return {col["name"] for col in inspect(op.get_bind()).get_columns(table_name)}


def _index_names(table_name: str) -> set[str]:
    return {idx["name"] for idx in inspect(op.get_bind()).get_indexes(table_name)}


def _rename_index(table_name: str, old_name: str, new_name: str) -> None:
    if not _has_table(table_name):
        return
    indexes = _index_names(table_name)
    if old_name not in indexes or new_name in indexes:
        return
    sql = 'ALTER INDEX "' + old_name + '" RENAME TO "' + new_name + '"'
    op.execute(sa.text(sql))


def _ensure_agent_access_legacy_columns_are_empty() -> None:
    if not _has_table("agent_access"):
        return

    legacy_payload_count = op.get_bind().execute(
        sa.text(
            """
            SELECT COUNT(*)
            FROM agent_access
            WHERE (
                org_node_ids IS NOT NULL
                AND org_node_ids::text NOT IN ('null', '[]')
            ) OR (
                user_ids IS NOT NULL
                AND user_ids::text NOT IN ('null', '[]')
            ) OR (
                user_role_ids IS NOT NULL
                AND user_role_ids::text NOT IN ('null', '[]')
            )
            """
        )
    ).scalar_one()

    if legacy_payload_count:
        raise RuntimeError(
            "agent_access legacy user/org columns still contain effective data; "
            "cleanup migration aborted to avoid silent data loss."
        )


def _ensure_agent_context_config_is_object_safe() -> None:
    if not (_has_table("agents") and "target_audience" in _column_names("agents")):
        return

    non_object_count = op.get_bind().execute(
        sa.text(
            """
            SELECT COUNT(*)
            FROM agents
            WHERE target_audience IS NOT NULL
              AND context_config IS NOT NULL
              AND jsonb_typeof(context_config::jsonb) <> 'object'
            """
        )
    ).scalar_one()

    if non_object_count:
        raise RuntimeError(
            "Found agents.target_audience rows whose context_config is not a JSON object; "
            "cleanup migration aborted to avoid overwriting non-object payloads."
        )


def _archive_legacy_target_audience() -> None:
    if not (_has_table("agents") and "target_audience" in _column_names("agents")):
        return

    _ensure_agent_context_config_is_object_safe()

    op.execute(
        sa.text(
            """
            UPDATE agents
            SET context_config = jsonb_set(
                COALESCE(context_config::jsonb, '{}'::jsonb),
                '{legacy_target_audience}',
                to_jsonb(target_audience::text),
                true
            )::json
            WHERE target_audience IS NOT NULL
              AND NOT (COALESCE(context_config::jsonb, '{}'::jsonb) ? 'legacy_target_audience')
            """
        )
    )


def upgrade() -> None:
    _rename_index("agents", "ix_agents_tenant_id", "ix_agents_owner_tenant_id")
    _rename_index("agents", "ix_agents_tenant_status", "ix_agents_owner_tenant_status")
    _rename_index("ai_api_keys", "ix_ai_api_keys_tenant_id", "ix_ai_api_keys_owner_tenant_id")
    _rename_index("knowledge_bases", "ix_kb_tenant_status", "ix_kb_owner_status")
    _rename_index(
        "knowledge_bases",
        "ix_knowledge_bases_tenant_id",
        "ix_knowledge_bases_owner_tenant_id",
    )
    _rename_index(
        "tenant_agent_platform_kb_suppressions",
        "ix_tapks_tenant_id",
        "ix_tenant_agent_platform_kb_suppressions_tenant_id",
    )

    if _has_table("agent_access"):
        _ensure_agent_access_legacy_columns_are_empty()
        columns = _column_names("agent_access")
        for column_name in ("org_node_ids", "user_ids", "user_role_ids"):
            if column_name in columns:
                op.drop_column("agent_access", column_name)

    if _has_table("agents"):
        columns = _column_names("agents")
        if "target_audience" in columns:
            _archive_legacy_target_audience()
            indexes = _index_names("agents")
            if "ix_agents_target_audience" in indexes:
                op.drop_index("ix_agents_target_audience", table_name="agents")
            op.drop_column("agents", "target_audience")


def downgrade() -> None:
    """Intentional no-op.

    This cleanup removes legacy columns after archiving the last useful payload to
    surviving fields and aligns stale index names with current resource naming.
    Restoring the retired columns would reintroduce deprecated runtime paths.
    """

    pass
