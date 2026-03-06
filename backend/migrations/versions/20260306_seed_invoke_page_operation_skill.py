"""seed invoke_page_operation builtin skill

Revision ID: 20260306_invoke_page_op
Revises: 20260306_page_awareness_skill
Create Date: 2026-03-06 13:20:00.000000+00:00

"""

from __future__ import annotations

import json
from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "20260306_invoke_page_op"
down_revision: str | Sequence[str] | None = "20260306_page_awareness_skill"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PACKAGE_NAME = "页面感知"
SKILL_NAME = "invoke_page_operation"
SKILL_DESCRIPTION = "在用户当前页面执行操作"
SKILL_CONFIG = {
    "builtin_type": "page_operation",
    "tools": [
        {
            "name": "invoke_page_operation",
            "description": (
                "Execute a page operation on the user's current page via WebSocket. "
                "Use this tool to perform actions like refreshing data, navigating, "
                "exporting, or triggering UI operations on the page the user is viewing. "
                "You must first call get_page_context to know the current page_key and "
                "available operations before invoking this tool."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "page_key": {
                        "type": "string",
                        "description": "The page identifier (pageContextKey) where the operation should be executed.",
                    },
                    "operation_name": {
                        "type": "string",
                        "description": "The name of the operation to execute (must be a registered operation on the target page).",
                    },
                    "params": {
                        "type": "object",
                        "description": "Optional parameters to pass to the operation.",
                        "default": {},
                    },
                },
                "required": ["page_key", "operation_name"],
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


def _sync_skill(conn, package_id: int, skill_id: int | None) -> None:
    payload = {
        "package_id": package_id,
        "name": SKILL_NAME,
        "description": SKILL_DESCRIPTION,
        "type": "builtin",
        "config": json.dumps(SKILL_CONFIG),
        "timeout": 45,
        "sort_order": 20,
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
        print("[SEED] WARNING: 页面感知 package not found. Run page_awareness_skill migration first.")
        return

    _sync_skill(conn, package_id, skill_id)


def downgrade() -> None:
    print("[SEED] Downgrade: no-op for invoke_page_operation builtin skill seed.")
