"""[NO-OP] seed_system_data_intelligence

Superseded by 20260226_0410_merge_system_skill_packages.
Package 系统数据智能技能包 soft-deleted, skill 平台数据管理 moved to unified 系统核心技能包.

Original: Add system built-in data intelligence skill package + skill.
- is_system=true so it cannot be deleted
- config={} (no table_policy_ids) → auto-uses ALL active table policies
- scope=admin, globally available

Revision ID: b3c4d5e6f7a8
Revises: a3b4c5d6e7f8
Create Date: 2026-02-14 20:10:00.000000+08:00

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'b3c4d5e6f7a8'
down_revision: Union[str, None] = 'a3b4c5d6e7f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_PKG_NAME = "系统数据智能技能包"
_SKILL_NAME = "平台数据管理"


def upgrade() -> None:
    conn = op.get_bind()

    # Idempotent: skip if already exists
    existing = conn.execute(text(
        "SELECT id FROM skill_packages "
        "WHERE name = :name AND is_system = true AND is_deleted = false"
    ), {"name": _PKG_NAME}).fetchone()

    if existing:
        pkg_id = existing[0]
        print(f"[SEED] Package '{_PKG_NAME}' already exists (id={pkg_id})")
    else:
        result = conn.execute(text(
            "INSERT INTO skill_packages "
            "(tenant_id, name, description, avatar, scope, is_system, "
            " is_active, sort_order, created_at, updated_at, is_deleted) "
            "VALUES "
            "(NULL, :name, :desc, :avatar, 'admin', true, "
            " true, 3, NOW(), NOW(), false) "
            "RETURNING id"
        ), {
            "name": _PKG_NAME,
            "desc": "系统内置的数据智能技能包，提供自然语言查询和操作数据库的能力",
            "avatar": "lucide:database",
        })
        pkg_id = result.fetchone()[0]
        print(f"[SEED] Created package '{_PKG_NAME}' (id={pkg_id})")

    # Check if skill exists
    existing_skill = conn.execute(text(
        "SELECT id FROM skills "
        "WHERE name = :name AND package_id = :pkg_id "
        "AND is_system = true AND is_deleted = false"
    ), {"name": _SKILL_NAME, "pkg_id": pkg_id}).fetchone()

    if existing_skill:
        print(f"[SEED] Skill '{_SKILL_NAME}' already exists (id={existing_skill[0]})")
        return

    result = conn.execute(text(
        "INSERT INTO skills "
        "(tenant_id, package_id, name, description, avatar, type, scope, "
        " is_system, is_active, config, timeout, sort_order, "
        " created_at, updated_at, is_deleted) "
        "VALUES "
        "(NULL, :pkg_id, :name, :desc, :avatar, 'data_intelligence', 'admin', "
        " true, true, '{}'::jsonb, 60, 1, "
        " NOW(), NOW(), false) "
        "RETURNING id"
    ), {
        "pkg_id": pkg_id,
        "name": _SKILL_NAME,
        "desc": "平台管理员的数据操作技能。自动使用所有已配置的表策略，"
                "支持自然语言查询和 CRUD 操作。",
        "avatar": "lucide:database",
    })
    skill_id = result.fetchone()[0]
    print(f"[SEED] Created skill '{_SKILL_NAME}' (id={skill_id})")


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text(
        "DELETE FROM skills WHERE name = :name AND is_system = true"
    ), {"name": _SKILL_NAME})
    conn.execute(text(
        "DELETE FROM skill_packages WHERE name = :name AND is_system = true"
    ), {"name": _PKG_NAME})
    print(f"[SEED] Removed system data intelligence package + skill")
