"""Normalize ai_api_keys: all_tenants -> global_shared / selected_tenants + RTA

Revision ID: 20260321_akso
Revises: 20260320_urps

含 _repair_20260320_urps_skipped：对「仅 stamp 未执行 20260320」的坏库幂等补结构/数据。
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


# Match 20260320_urps legacy → canonical ResourceScopeEnum (whitelist SQL only)
_TABLE_LEGACY_SCOPE_SQL: dict[str, str] = {
    "knowledge_bases": (
        "UPDATE knowledge_bases SET scope = :new_scope WHERE scope = :old_scope"
    ),
    "plugins": "UPDATE plugins SET scope = :new_scope WHERE scope = :old_scope",
    "ai_api_keys": "UPDATE ai_api_keys SET scope = :new_scope WHERE scope = :old_scope",
    "system_config_groups": (
        "UPDATE system_config_groups SET scope = :new_scope WHERE scope = :old_scope"
    ),
    "system_configs": "UPDATE system_configs SET scope = :new_scope WHERE scope = :old_scope",
    "agents": "UPDATE agents SET scope = :new_scope WHERE scope = :old_scope",
}
_LEGACY_SCOPE_PAIRS: tuple[tuple[str, str], ...] = (
    ("platform", "admin_only"),
    ("tenant", "all_tenants"),
    ("global", "global_shared"),
    ("admin", "admin_only"),
    ("all", "global_shared"),
    ("admin_and_assigned", "admin_and_selected_tenants"),
    ("both", "global_shared"),
)

_ALTER_SCOPE_TO_VARCHAR_40: dict[str, str] = {
    "agents": "ALTER TABLE agents ALTER COLUMN scope TYPE VARCHAR(40)",
    "knowledge_bases": "ALTER TABLE knowledge_bases ALTER COLUMN scope TYPE VARCHAR(40)",
    "plugins": "ALTER TABLE plugins ALTER COLUMN scope TYPE VARCHAR(40)",
    "ai_api_keys": "ALTER TABLE ai_api_keys ALTER COLUMN scope TYPE VARCHAR(40)",
    "system_config_groups": (
        "ALTER TABLE system_config_groups ALTER COLUMN scope TYPE VARCHAR(40)"
    ),
    "system_configs": "ALTER TABLE system_configs ALTER COLUMN scope TYPE VARCHAR(40)",
}


def _remap_legacy_resource_scopes_repair(table: str) -> None:
    if not _table_exists(table) or "scope" not in _cols(table):
        return
    sql = _TABLE_LEGACY_SCOPE_SQL.get(table)
    if not sql:
        return
    stmt = sa.text(sql)
    bind = op.get_bind()
    for old_scope, new_scope in _LEGACY_SCOPE_PAIRS:
        bind.execute(stmt, {"old_scope": old_scope, "new_scope": new_scope})


def _cols(table: str) -> set[str]:
    bind = op.get_bind()
    return {c["name"] for c in inspect(bind).get_columns(table)}


def _table_exists(table: str) -> bool:
    bind = op.get_bind()
    return table in inspect(bind).get_table_names()


def _ensure_owner_tenant_id(table: str) -> None:
    """If 20260320_urps was stamped but not executed, tenant_id still exists; rename it now."""
    cols = _cols(table)
    if "owner_tenant_id" in cols:
        return
    if "tenant_id" not in cols:
        return
    op.alter_column(
        table,
        "tenant_id",
        new_column_name="owner_tenant_id",
        existing_type=sa.Integer(),
        existing_nullable=True,
    )


def _tid(table: str) -> str:
    """Return the tenant-id column name currently present in *table*."""
    cols = _cols(table)
    if "owner_tenant_id" in cols:
        return "owner_tenant_id"
    return "tenant_id"


def _ensure_ai_api_keys_scope_min_length(min_len: int = 32) -> None:
    """Widen ai_api_keys.scope if still narrow (repair step may already set VARCHAR(40))."""
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


def _repair_20260320_urps_skipped() -> None:
    """Idempotent catch-up for 20260320_urps that was stamped but never executed.

    Order: data migration -> structural drops -> column renames -> constraints.
    """
    rta_exists = _table_exists("resource_tenant_assignments")

    # ── 0. Widen scope columns so new canonical values fit (e.g. 'admin_and_selected_tenants' = 26 chars) ──
    for tbl, sql in _ALTER_SCOPE_TO_VARCHAR_40.items():
        if _table_exists(tbl) and "scope" in _cols(tbl):
            _exec(sql)

    for tbl in (
        "knowledge_bases",
        "plugins",
        "ai_api_keys",
        "system_config_groups",
        "system_configs",
    ):
        _remap_legacy_resource_scopes_repair(tbl)

    # ── 1. Permission scope normalization ──
    if _table_exists("permissions"):
        # The app may have already seeded new-scope equivalents while old-scope rows
        # still exist, so we must handle duplicates carefully:
        #   a) Re-parent children of old-scope permissions to new-scope equivalents
        #   b) DELETE old-scope rows whose (code, new_scope) already exists
        #      (role_permission FKs use ondelete=CASCADE, so they auto-clean)
        #   c) UPDATE remaining old-scope rows (no conflict now)
        scope_map = [
            ("admin_only", "admin"),
            ("all_tenants", "tenant"),
            ("tenant_user", "user"),
            ("global_shared", "both"),
            ("admin_and_selected_tenants", "tenant"),
            ("selected_tenants", "tenant"),
        ]
        bind = op.get_bind()
        parent_rebind = sa.text(
            """
            UPDATE permissions SET parent_id = m.new_id
            FROM (
              SELECT p_old.id AS old_id, p_new.id AS new_id
              FROM permissions p_old
              JOIN permissions p_new ON p_old.code = p_new.code
              WHERE p_old.scope = :old_scope AND p_new.scope = :new_scope
            ) m
            WHERE permissions.parent_id = m.old_id
            """
        )
        delete_dup = sa.text(
            """
            DELETE FROM permissions
            WHERE scope = :old_scope
              AND code IN (SELECT code FROM permissions WHERE scope = :new_scope)
            """
        )
        update_scope = sa.text(
            "UPDATE permissions SET scope = :new_scope WHERE scope = :old_scope"
        )
        for old_scope, new_scope in scope_map:
            params = {"old_scope": old_scope, "new_scope": new_scope}
            bind.execute(parent_rebind, params)
            bind.execute(delete_dup, params)
            bind.execute(update_scope, params)

    # ── 2. Agent scope derivation + RTA (data before drop) ──
    agent_cols = _cols("agents") if _table_exists("agents") else set()

    if "distribution_mode" in agent_cols:
        _exec("UPDATE agents SET scope = 'admin_only'       WHERE distribution_mode = 'internal'")
        _exec("UPDATE agents SET scope = 'all_tenants'      WHERE distribution_mode = 'all_tenants'")
        _exec(
            "UPDATE agents SET scope = 'selected_tenants' "
            "WHERE distribution_mode IN ('assigned_tenants', 'owner_only')"
        )
        _remap_legacy_resource_scopes_repair("agents")

        if rta_exists:
            tid = _tid("agents")
            if tid == "owner_tenant_id":
                _exec(
                    """
                    INSERT INTO resource_tenant_assignments
                      (resource_type, resource_id, tenant_id, is_active, is_deleted, created_at, updated_at)
                    SELECT 'agent', a.id, a.owner_tenant_id, true, false, NOW(), NOW()
                    FROM agents a
                    WHERE a.distribution_mode = 'owner_only'
                      AND a.owner_tenant_id IS NOT NULL
                      AND NOT EXISTS (
                        SELECT 1 FROM resource_tenant_assignments r
                        WHERE r.resource_type = 'agent' AND r.resource_id = a.id
                          AND r.tenant_id = a.owner_tenant_id AND r.is_deleted = false
                      )
                    """
                )
            elif tid == "tenant_id":
                _exec(
                    """
                    INSERT INTO resource_tenant_assignments
                      (resource_type, resource_id, tenant_id, is_active, is_deleted, created_at, updated_at)
                    SELECT 'agent', a.id, a.tenant_id, true, false, NOW(), NOW()
                    FROM agents a
                    WHERE a.distribution_mode = 'owner_only'
                      AND a.tenant_id IS NOT NULL
                      AND NOT EXISTS (
                        SELECT 1 FROM resource_tenant_assignments r
                        WHERE r.resource_type = 'agent' AND r.resource_id = a.id
                          AND r.tenant_id = a.tenant_id AND r.is_deleted = false
                      )
                    """
                )
            else:
                raise ValueError(f"unexpected agents tenant column: {tid!r}")

        op.drop_column("agents", "distribution_mode")

    elif _table_exists("agents") and "scope" in _cols("agents"):
        _remap_legacy_resource_scopes_repair("agents")

    if _table_exists("agents") and "owner_type" in _cols("agents"):
        op.drop_column("agents", "owner_type")

    if "visibility" in _cols("knowledge_bases"):
        op.drop_column("knowledge_bases", "visibility")

    # ── 4. Rename tenant_id → owner_tenant_id on all affected tables ──
    _ensure_owner_tenant_id("agents")
    _ensure_owner_tenant_id("knowledge_bases")
    _ensure_owner_tenant_id("ai_api_keys")


def upgrade() -> None:
    # Idempotent catch-up for stamped-but-not-executed 20260320_urps
    _repair_20260320_urps_skipped()

    # 再保险：主迁移 DML 依赖 owner_tenant_id；若库曾被错误 stamp 而 repair 未改到该表，此处幂等补齐
    if _table_exists("ai_api_keys"):
        _ensure_owner_tenant_id("ai_api_keys")

    # Widen scope column for 5-class ResourceScopeEnum strings (idempotent vs repair VARCHAR(40))
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
