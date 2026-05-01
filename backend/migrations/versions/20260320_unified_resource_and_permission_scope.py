"""Unified resource scope (5 values) + RBAC permission endpoint scope

Revision ID: 20260320_urps
Revises: 20260320_tapks

无 downgrade。若库被错误 stamp 到本 revision 但未实际执行，后续
20260321_akso（upgrade 内 _repair_20260320_urps_skipped）与
20260324_pt_otid_repair 提供幂等补跑；仍建议从备份恢复或空库 replay。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260320_urps"
down_revision = "20260320_tapks"
branch_labels = None
depends_on = None


def _exec(sql: str) -> None:
    op.execute(sa.text(sql))


# Whitelist table names only (no dynamic identifiers) / 仅白名单表名
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

# Historical strings that may still exist before five-class ResourceScopeEnum / 历史库可能残留
_LEGACY_SCOPE_PAIRS: tuple[tuple[str, str], ...] = (
    ("platform", "admin_only"),
    ("tenant", "all_tenants"),
    ("global", "global_shared"),
    ("admin", "admin_only"),
    ("all", "global_shared"),
    ("admin_and_assigned", "admin_and_selected_tenants"),
    ("both", "global_shared"),
)


def _remap_legacy_resource_scopes(table: str) -> None:
    sql = _TABLE_LEGACY_SCOPE_SQL.get(table)
    if not sql:
        raise ValueError(f"legacy scope remap: unknown table {table!r}")
    stmt = sa.text(sql)
    bind = op.get_bind()
    for old_scope, new_scope in _LEGACY_SCOPE_PAIRS:
        bind.execute(stmt, {"old_scope": old_scope, "new_scope": new_scope})


def upgrade() -> None:
    # ── RBAC: permissions.scope ───────────────────────────────────────────
    _exec("UPDATE permissions SET scope = 'admin' WHERE scope = 'admin_only'")
    _exec("UPDATE permissions SET scope = 'tenant' WHERE scope = 'all_tenants'")
    _exec("UPDATE permissions SET scope = 'user' WHERE scope = 'tenant_user'")
    _exec("UPDATE permissions SET scope = 'both' WHERE scope = 'global_shared'")
    _exec(
        "UPDATE permissions SET scope = 'tenant' "
        "WHERE scope IN ('admin_and_selected_tenants', 'selected_tenants')"
    )

    # 历史列多为 VARCHAR(20)，无法写入 admin_and_selected_tenants（26 字符）
    for widen_sql in (
        "ALTER TABLE knowledge_bases ALTER COLUMN scope TYPE VARCHAR(40)",
        "ALTER TABLE plugins ALTER COLUMN scope TYPE VARCHAR(40)",
        "ALTER TABLE ai_api_keys ALTER COLUMN scope TYPE VARCHAR(40)",
        "ALTER TABLE system_config_groups ALTER COLUMN scope TYPE VARCHAR(40)",
        "ALTER TABLE system_configs ALTER COLUMN scope TYPE VARCHAR(40)",
        "ALTER TABLE agents ALTER COLUMN scope TYPE VARCHAR(40)",
    ):
        _exec(widen_sql)

    # ── Resource tables (except agents — handled below) ───────────────────
    for table in (
        "knowledge_bases",
        "plugins",
        "ai_api_keys",
        "system_config_groups",
        "system_configs",
    ):
        _remap_legacy_resource_scopes(table)

    # ── Agents: derive scope from distribution_mode, then remap old strings ─
    _exec(
        "UPDATE agents SET scope = 'admin_only' WHERE distribution_mode = 'internal'"
    )
    _exec(
        "UPDATE agents SET scope = 'all_tenants' WHERE distribution_mode = 'all_tenants'"
    )
    _exec(
        "UPDATE agents SET scope = 'selected_tenants' "
        "WHERE distribution_mode IN ('assigned_tenants', 'owner_only')"
    )
    _remap_legacy_resource_scopes("agents")

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

    op.drop_column("agents", "distribution_mode")
    op.drop_column("agents", "owner_type")

    op.alter_column(
        "agents",
        "tenant_id",
        new_column_name="owner_tenant_id",
        existing_type=sa.Integer(),
        existing_nullable=True,
    )
    op.alter_column(
        "knowledge_bases",
        "tenant_id",
        new_column_name="owner_tenant_id",
        existing_type=sa.Integer(),
        existing_nullable=True,
    )
    op.alter_column(
        "ai_api_keys",
        "tenant_id",
        new_column_name="owner_tenant_id",
        existing_type=sa.Integer(),
        existing_nullable=True,
    )


def downgrade() -> None:
    raise NotImplementedError("Downgrade not supported for unified scope migration")
