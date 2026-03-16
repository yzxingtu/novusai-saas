"""remove_crud_generator_seed_data

Remove CRUD Generator / CRUD Form Toolkit seed data from the database.
The builtin CRUD Generator was removed; any replacement is via plugins.

This migration soft-deletes:
1. "CRUD 表单工具包" SkillPackage + "crud_form_toolkit" Skill
2. "CRUD 表单助手" Agent + AgentSkillBinding
3. Any remaining old "CRUD Generator 技能包" / "crud_generator" data
4. CRUD Generator menu/permission entries (menu:admin.dev_tools, menu:admin.crud_generator)

Revision ID: 20260216_rmcg
Revises: 20260216_awm
Create Date: 2026-02-16
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision = "20260216_rmcg"
down_revision = "20260216_awm"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Soft-delete agent bindings for CRUD agents
    conn.execute(text(
        "UPDATE agent_skill_bindings SET is_deleted = true, deleted_at = NOW() "
        "WHERE agent_id IN ("
        "  SELECT id FROM agents "
        "  WHERE name IN ('CRUD 表单助手', 'crud_generator_assistant', 'CRUD 生成助手') "
        "  AND tenant_id IS NULL"
        ") AND is_deleted = false"
    ))

    # 2. Soft-delete CRUD agents
    conn.execute(text(
        "UPDATE agents SET is_deleted = true, deleted_at = NOW() "
        "WHERE name IN ('CRUD 表单助手', 'crud_generator_assistant', 'CRUD 生成助手') "
        "AND tenant_id IS NULL AND is_system = true AND is_deleted = false"
    ))

    # 3. Soft-delete CRUD skills
    conn.execute(text(
        "UPDATE skills SET is_deleted = true, deleted_at = NOW() "
        "WHERE name IN ('crud_form_toolkit', 'crud_generator') "
        "AND tenant_id IS NULL AND is_deleted = false"
    ))

    # 4. Soft-delete CRUD skill packages
    conn.execute(text(
        "UPDATE skill_packages SET is_deleted = true, deleted_at = NOW() "
        "WHERE name IN ('CRUD 表单工具包', 'CRUD Generator 技能包') "
        "AND tenant_id IS NULL AND is_deleted = false"
    ))

    # 5. Disable CRUD Generator menus/permissions
    result = conn.execute(text(
        "UPDATE permissions SET is_enabled = false "
        "WHERE code IN ('menu:admin.dev_tools', 'menu:admin.crud_generator') "
        "AND scope = 'admin' AND is_enabled = true"
    ))
    disabled = result.rowcount if result.rowcount else 0

    # Also disable operation permissions under crud_generator resource
    result2 = conn.execute(text(
        "UPDATE permissions SET is_enabled = false "
        "WHERE parent_id IN ("
        "  SELECT id FROM permissions "
        "  WHERE code IN ('menu:admin.dev_tools', 'menu:admin.crud_generator') "
        "  AND scope = 'admin'"
        ") AND is_enabled = true"
    ))
    disabled += result2.rowcount if result2.rowcount else 0

    print(f"[MIGRATION] CRUD Generator seed data soft-deleted, {disabled} menu/permission entries disabled")


def downgrade() -> None:
    conn = op.get_bind()

    # Restore CRUD 表单工具包 data
    conn.execute(text(
        "UPDATE skill_packages SET is_deleted = false, deleted_at = NULL "
        "WHERE name = 'CRUD 表单工具包' AND tenant_id IS NULL AND is_deleted = true"
    ))
    conn.execute(text(
        "UPDATE skills SET is_deleted = false, deleted_at = NULL "
        "WHERE name = 'crud_form_toolkit' AND tenant_id IS NULL AND is_deleted = true"
    ))
    conn.execute(text(
        "UPDATE agents SET is_deleted = false, deleted_at = NULL "
        "WHERE name = 'CRUD 表单助手' AND tenant_id IS NULL "
        "AND is_system = true AND is_deleted = true"
    ))
    conn.execute(text(
        "UPDATE agent_skill_bindings SET is_deleted = false, deleted_at = NULL "
        "WHERE agent_id IN ("
        "  SELECT id FROM agents "
        "  WHERE name = 'CRUD 表单助手' AND tenant_id IS NULL"
        ") AND is_deleted = true"
    ))

    # Restore CRUD Generator menus/permissions
    conn.execute(text(
        "UPDATE permissions SET is_enabled = true "
        "WHERE code IN ('menu:admin.dev_tools', 'menu:admin.crud_generator') "
        "AND scope = 'admin' AND is_enabled = false"
    ))
    conn.execute(text(
        "UPDATE permissions SET is_enabled = true "
        "WHERE parent_id IN ("
        "  SELECT id FROM permissions "
        "  WHERE code IN ('menu:admin.dev_tools', 'menu:admin.crud_generator') "
        "  AND scope = 'admin'"
        ") AND is_enabled = false"
    ))

    print("[MIGRATION] CRUD Generator seed data + menus restored")
