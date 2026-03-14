"""backfill default_user roles for existing tenants

For tenants created before the _create_default_user_role feature was added,
create the missing default_user role and set user_default_role_id config.

Revision ID: 20260307_backfill_roles
Revises: 20260307_merge_page_pkg
Create Date: 2026-03-07 21:00:00.000000+00:00

"""

from __future__ import annotations

import json
from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "20260307_backfill_roles"
down_revision: str | Sequence[str] | None = "20260307_merge_page_pkg"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """为缺少 default_user 角色的现有企业创建角色并设置配置."""
    bind = op.get_bind()

    # 1. 找到所有活跃企业
    tenants = bind.execute(
        text("SELECT id FROM tenants WHERE is_deleted = false")
    ).fetchall()

    if not tenants:
        print("No tenants found, skipping")
        return

    # 2. 找到已有 default_user 角色的企业
    existing = bind.execute(
        text(
            "SELECT tenant_id FROM tenant_user_roles "
            "WHERE code = 'default_user' AND is_deleted = false"
        )
    ).fetchall()
    existing_tenant_ids = {row[0] for row in existing}

    # 3. 找到缺失的企业
    missing_tenant_ids = [t[0] for t in tenants if t[0] not in existing_tenant_ids]

    if not missing_tenant_ids:
        print("All tenants already have default_user role, skipping")
        return

    print(f"Creating default_user role for {len(missing_tenant_ids)} tenant(s): {missing_tenant_ids}")

    # 4. 获取 user_default_role_id 配置项 ID
    config_row = bind.execute(
        text("SELECT id FROM system_configs WHERE key = 'user_default_role_id'")
    ).fetchone()

    for tenant_id in missing_tenant_ids:
        # 创建 default_user 角色
        result = bind.execute(
            text(
                "INSERT INTO tenant_user_roles "
                "(tenant_id, name, code, description, is_system, is_active, "
                "sort_order, is_deleted, created_at, updated_at) "
                "VALUES (:tenant_id, :name, 'default_user', :description, true, true, "
                "0, false, NOW(), NOW()) "
                "RETURNING id"
            ),
            {
                "tenant_id": tenant_id,
                "name": "Default User",
                "description": "Default role for registered users",
            },
        )
        role_id = result.fetchone()[0]
        print(f"  Tenant {tenant_id}: created default_user role (id={role_id})")

        # 更新 user_default_role_id 配置（仅当配置项存在且当前值为 0 时）
        if config_row:
            config_id = config_row[0]
            existing_value = bind.execute(
                text(
                    "SELECT id, value FROM system_config_values "
                    "WHERE config_id = :config_id AND tenant_id = :tenant_id"
                ),
                {"config_id": config_id, "tenant_id": tenant_id},
            ).fetchone()

            value_json = json.dumps(role_id)

            if existing_value:
                # 仅当当前值为 0 或 "0" 时更新
                current = existing_value[1]
                if current in (None, "0", '"0"', "null"):
                    bind.execute(
                        text(
                            "UPDATE system_config_values SET value = :value, "
                            "updated_at = NOW() WHERE id = :id"
                        ),
                        {"value": value_json, "id": existing_value[0]},
                    )
                    print(f"  Tenant {tenant_id}: updated user_default_role_id -> {role_id}")
                else:
                    print(f"  Tenant {tenant_id}: user_default_role_id already set ({current}), skipping")
            else:
                bind.execute(
                    text(
                        "INSERT INTO system_config_values "
                        "(config_id, tenant_id, value, created_at, updated_at, is_deleted) "
                        "VALUES (:config_id, :tenant_id, :value, NOW(), NOW(), false)"
                    ),
                    {"config_id": config_id, "tenant_id": tenant_id, "value": value_json},
                )
                print(f"  Tenant {tenant_id}: inserted user_default_role_id = {role_id}")

    print(f"Done: backfilled {len(missing_tenant_ids)} tenant(s)")


def downgrade() -> None:
    """Downgrade: no-op (data migration)."""
    pass
