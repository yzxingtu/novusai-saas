"""Normalize ai_api_keys: all_tenants -> global_shared / selected_tenants + RTA

Revision ID: 20260321_akso
Revises: 20260320_urps

无 downgrade。
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260321_akso"
down_revision = "20260320_urps"
branch_labels = None
depends_on = None


def _exec(sql: str) -> None:
    op.execute(sa.text(sql))


def _cols(table: str) -> set[str]:
    bind = op.get_bind()
    return {c["name"] for c in inspect(bind).get_columns(table)}


def _table_exists(table: str) -> bool:
    bind = op.get_bind()
    return table in inspect(bind).get_table_names()


def _ensure_ai_api_keys_scope_min_length(min_len: int = 32) -> None:
    """Widen ai_api_keys.scope so five-class ResourceScopeEnum values fit."""
    if not _table_exists("ai_api_keys") or "scope" not in _cols("ai_api_keys"):
        return
    bind = op.get_bind()
    row = bind.execute(
        sa.text(
            """
            SELECT character_maximum_length, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'ai_api_keys' AND column_name = 'scope'
            """
        )
    ).fetchone()
    if not row:
        return
    max_len, data_type = row[0], (row[1] or "")
    if data_type == "text":
        return
    if max_len is not None and int(max_len) >= min_len:
        return
    ml = int(min_len)
    widen_sql = {
        32: "ALTER TABLE ai_api_keys ALTER COLUMN scope TYPE VARCHAR(32)",
        40: "ALTER TABLE ai_api_keys ALTER COLUMN scope TYPE VARCHAR(40)",
    }.get(ml)
    if not widen_sql:
        raise ValueError(f"unsupported ai_api_keys scope width: {ml}")
    _exec(widen_sql)


def upgrade() -> None:
    # Widen scope column for 5-class ResourceScopeEnum strings.
    _ensure_ai_api_keys_scope_min_length(32)

    # Tenant-owned keys: all_tenants + owner -> selected_tenants
    op.execute(
        sa.text(
            """
            UPDATE ai_api_keys
            SET scope = 'selected_tenants'
            WHERE scope = 'all_tenants' AND owner_tenant_id IS NOT NULL
            """
        )
    )

    # Platform-shared keys: all_tenants + no owner -> global_shared
    op.execute(
        sa.text(
            """
            UPDATE ai_api_keys
            SET scope = 'global_shared'
            WHERE scope = 'all_tenants' AND owner_tenant_id IS NULL
            """
        )
    )

    # Self-assignment rows for tenant-scoped keys
    if _table_exists("resource_tenant_assignments"):
        op.execute(
            sa.text(
                """
                INSERT INTO resource_tenant_assignments
                  (resource_type, resource_id, tenant_id, is_active, is_deleted, created_at, updated_at)
                SELECT 'ai_api_key', k.id, k.owner_tenant_id, true, false, NOW(), NOW()
                FROM ai_api_keys k
                WHERE k.scope = 'selected_tenants'
                  AND k.owner_tenant_id IS NOT NULL
                  AND k.is_deleted = false
                  AND NOT EXISTS (
                    SELECT 1 FROM resource_tenant_assignments r
                    WHERE r.resource_type = 'ai_api_key'
                      AND r.resource_id = k.id
                      AND r.tenant_id = k.owner_tenant_id
                      AND r.is_deleted = false
                  )
                """
            )
        )


def downgrade() -> None:
    raise NotImplementedError("Downgrade not supported for ai_api_keys scope normalize")
