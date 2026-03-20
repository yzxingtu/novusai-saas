"""seed page awareness builtin skill

Revision ID: 20260306_page_awareness_skill
Revises: 20260305_router_seed
Create Date: 2026-03-06 11:55:00.000000+00:00

"""

from __future__ import annotations

import json
from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "20260306_page_awareness_skill"
down_revision: str | Sequence[str] | None = "20260305_router_seed"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PACKAGE_NAME = "页面感知"
PACKAGE_DESCRIPTION = (
    "系统内置的页面感知能力包。提供 get_page_context（读取页面上下文）"
    "和 invoke_page_operation（执行页面操作）工具，"
    "供智能体在 function calling 阶段感知并操作用户当前页面。"
)
SKILL_NAME = "get_page_context"
SKILL_DESCRIPTION = "获取当前页面上下文"
SKILL_CONFIG = {
    "builtin_type": "page_context",
    "tools": [
        {
            "name": "get_page_context",
            "description": (
                "Get the current page context, including page identifier, title, and structured "
                "page data. Use this tool when you need deeper understanding of what page the "
                "user is currently viewing."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        }
    ],
}


def _find_skill(conn) -> tuple[int, int] | None:
    row = conn.execute(
        text(
            "SELECT id, package_id FROM skills "
            "WHERE name = :name AND type = 'builtin' AND tenant_id IS NULL "
            "AND is_system = true AND is_deleted = false "
            "ORDER BY id LIMIT 1"
        ),
        {"name": SKILL_NAME},
    ).fetchone()
    if not row:
        return None
    return row[0], row[1]



def _find_package(conn) -> int | None:
    row = conn.execute(
        text(
            "SELECT id FROM skill_packages "
            "WHERE name = :name AND tenant_id IS NULL AND is_system = true "
            "AND is_deleted = false "
            "ORDER BY id LIMIT 1"
        ),
        {"name": PACKAGE_NAME},
    ).fetchone()
    if not row:
        return None
    return row[0]


def _create_package(conn) -> int:
    row = conn.execute(
        text(
            "INSERT INTO skill_packages "
            "(tenant_id, name, description, scope, bind_mode, is_system, is_active, sort_order, created_at, updated_at, is_deleted) "
            "VALUES "
            "(NULL, :name, :description, 'global_shared', 'auto', true, true, :sort_order, NOW(), NOW(), false) "
            "RETURNING id"
        ),
        {
            "name": PACKAGE_NAME,
            "description": PACKAGE_DESCRIPTION,
            "sort_order": 20,
        },
    ).fetchone()
    return row[0]


def _sync_package(conn, package_id: int) -> None:
    conn.execute(
        text(
            "UPDATE skill_packages SET "
            "tenant_id = NULL, "
            "name = :name, "
            "description = :description, "
            "scope = 'global_shared', "
            "bind_mode = 'auto', "
            "is_system = true, "
            "is_active = true, "
            "is_deleted = false, "
            "sort_order = :sort_order, "
            "updated_at = NOW() "
            "WHERE id = :package_id"
        ),
        {
            "package_id": package_id,
            "name": PACKAGE_NAME,
            "description": PACKAGE_DESCRIPTION,
            "sort_order": 20,
        },
    )


def _sync_skill(conn, package_id: int, skill_id: int | None) -> None:
    payload = {
        "package_id": package_id,
        "name": SKILL_NAME,
        "description": SKILL_DESCRIPTION,
        "type": "builtin",
        "config": json.dumps(SKILL_CONFIG),
        "timeout": 15,
        "sort_order": 10,
    }
    if skill_id is None:
        conn.execute(
            text(
                "INSERT INTO skills "
                "(tenant_id, package_id, name, description, type, config, is_system, is_active, timeout, sort_order, created_at, updated_at, is_deleted) "
                "VALUES "
                "(NULL, :package_id, :name, :description, :type, CAST(:config AS jsonb), true, true, :timeout, :sort_order, NOW(), NOW(), false)"
            ),
            payload,
        )
        return

    conn.execute(
        text(
            "UPDATE skills SET "
            "tenant_id = NULL, "
            "package_id = :package_id, "
            "name = :name, "
            "description = :description, "
            "type = :type, "
            "config = CAST(:config AS jsonb), "
            "is_system = true, "
            "is_active = true, "
            "is_deleted = false, "
            "timeout = :timeout, "
            "sort_order = :sort_order, "
            "updated_at = NOW() "
            "WHERE id = :skill_id"
        ),
        {
            **payload,
            "skill_id": skill_id,
        },
    )



def upgrade() -> None:
    conn = op.get_bind()
    existing_skill = _find_skill(conn)
    skill_id = existing_skill[0] if existing_skill else None
    package_id = existing_skill[1] if existing_skill else None

    if package_id is None:
        package_id = _find_package(conn)

    if package_id is None:
        package_id = _create_package(conn)

    _sync_package(conn, package_id)
    _sync_skill(conn, package_id, skill_id)



def downgrade() -> None:
    print("[SEED] Downgrade: no-op for page awareness builtin skill seed.")
