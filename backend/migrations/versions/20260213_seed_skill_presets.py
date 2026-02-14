"""seed_skill_presets

Insert preset Skill seed data for out-of-the-box usage.

Seed skills (scope=admin, globally available):
1. 平台数据管理 (data_intelligence) - full CRUD for platform admins
2. 租户数据查询 (data_intelligence) - read-only for tenants

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-13 19:50:00.000000+08:00

"""
from typing import Sequence, Union

import json

from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SEED_SKILLS = [
    {
        "name": "平台数据管理",
        "description": "平台管理员的数据操作技能，支持查询、创建、更新、删除操作",
        "type": "data_intelligence",
        "scope": "admin",
        "config": {
            "allowed_operations": ["read", "create", "update", "delete"],
            "scope": "platform",
        },
        "timeout": 60,
        "sort_order": 1,
    },
    {
        "name": "租户数据查询",
        "description": "租户的只读数据查询技能，仅支持查询操作",
        "type": "data_intelligence",
        "scope": "admin",
        "config": {
            "allowed_operations": ["read"],
            "scope": "tenant",
        },
        "timeout": 60,
        "sort_order": 2,
    },
]


def upgrade() -> None:
    """Insert seed skills (each wrapped in its own package)."""
    conn = op.get_bind()

    for seed in SEED_SKILLS:
        # Idempotent: skip if already exists
        existing = conn.execute(text(
            "SELECT id FROM skills "
            "WHERE name = :name AND scope = :scope AND tenant_id IS NULL "
            "AND is_deleted = false"
        ), {"name": seed["name"], "scope": seed["scope"]}).fetchone()

        if existing:
            print(f"[SEED] Skill '{seed['name']}' already exists (id={existing.id}), skipping")
            continue

        # Create a package for this seed skill (if skill_packages table exists)
        pkg_id = None
        try:
            pkg_result = conn.execute(text(
                "INSERT INTO skill_packages "
                "(tenant_id, name, description, scope, is_active, sort_order, "
                " created_at, updated_at, is_deleted) "
                "VALUES "
                "(NULL, :name, :description, :scope, true, :sort_order, "
                " NOW(), NOW(), false) "
                "RETURNING id"
            ), {
                "name": seed["name"],
                "description": seed["description"],
                "scope": seed["scope"],
                "sort_order": seed["sort_order"],
            })
            pkg_id = pkg_result.fetchone()[0]
        except Exception:
            pass

        # Build INSERT with or without package_id
        if pkg_id is not None:
            result = conn.execute(text(
                "INSERT INTO skills "
                "(tenant_id, package_id, name, description, type, scope, config, "
                " timeout, is_active, sort_order, "
                " created_at, updated_at, is_deleted) "
                "VALUES "
                "(NULL, :package_id, :name, :description, :type, :scope, CAST(:config AS jsonb), "
                " :timeout, true, :sort_order, "
                " NOW(), NOW(), false) "
                "RETURNING id"
            ), {
                "package_id": pkg_id,
                "name": seed["name"],
                "description": seed["description"],
                "type": seed["type"],
                "scope": seed["scope"],
                "config": json.dumps(seed["config"]),
                "timeout": seed["timeout"],
                "sort_order": seed["sort_order"],
            })
        else:
            result = conn.execute(text(
                "INSERT INTO skills "
                "(tenant_id, name, description, type, scope, config, "
                " timeout, is_active, sort_order, "
                " created_at, updated_at, is_deleted) "
                "VALUES "
                "(NULL, :name, :description, :type, :scope, CAST(:config AS jsonb), "
                " :timeout, true, :sort_order, "
                " NOW(), NOW(), false) "
                "RETURNING id"
            ), {
                "name": seed["name"],
                "description": seed["description"],
                "type": seed["type"],
                "scope": seed["scope"],
                "config": json.dumps(seed["config"]),
                "timeout": seed["timeout"],
                "sort_order": seed["sort_order"],
            })

        new_id = result.fetchone()[0]
        print(f"[SEED] Created skill '{seed['name']}' (id={new_id}, package_id={pkg_id})")

    print("[SEED] Skill presets done.")


def downgrade() -> None:
    """Remove seed skills."""
    conn = op.get_bind()
    for seed in SEED_SKILLS:
        conn.execute(text(
            "DELETE FROM skills WHERE name = :name AND scope = :scope AND tenant_id IS NULL"
        ), {"name": seed["name"], "scope": seed["scope"]})
    print("[SEED] Seed skills removed.")
