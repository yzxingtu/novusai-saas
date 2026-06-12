"""seed system context tools skill package

Creates a DB-visible system skill package for agent-bound knowledge-base search
and long-term memory tools. Tool schemas remain code-defined and are expanded by
the builtin skill resolver.

Revision ID: 20260612_0051_context_tools
Revises: 20260612_0050_multi_dim_embed
Create Date: 2026-06-12 22:10:00.000000+08:00

"""

from __future__ import annotations

import json
from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "20260612_0051_context_tools"
down_revision: str | Sequence[str] | None = "20260612_0050_multi_dim_embed"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SKILL_PACKAGE_NAME = "智能体上下文技能包（内置）"
KB_SKILL_KEY = "agent_context_knowledge_search"
KB_SKILL_NAME = "知识库检索工具"
MEMORY_SKILL_KEY = "agent_context_memory_tools"
MEMORY_SKILL_NAME = "长期记忆读写工具"


def _ensure_package(conn) -> int:
    row = conn.execute(
        text(
            "SELECT id FROM skill_packages "
            "WHERE name = :name AND tenant_id IS NULL AND is_deleted = false "
            "ORDER BY id LIMIT 1"
        ),
        {"name": SKILL_PACKAGE_NAME},
    ).fetchone()
    if row:
        pkg_id = row[0]
        conn.execute(
            text(
                "UPDATE skill_packages "
                "SET description = :description, is_system = true, "
                "    is_active = true, updated_at = NOW() "
                "WHERE id = :id"
            ),
            {
                "id": pkg_id,
                "description": "内置智能体上下文工具：知识库检索与长期记忆读写。",
            },
        )
        return int(pkg_id)

    return int(
        conn.execute(
            text(
                "INSERT INTO skill_packages "
                "(tenant_id, name, description, is_recommended, is_system, "
                " is_active, sort_order, created_at, updated_at, is_deleted) "
                "VALUES "
                "(NULL, :name, :description, false, true, "
                " true, 10, NOW(), NOW(), false) "
                "RETURNING id"
            ),
            {
                "name": SKILL_PACKAGE_NAME,
                "description": "内置智能体上下文工具：知识库检索与长期记忆读写。",
            },
        ).fetchone()[0]
    )


def _ensure_skill(
    conn,
    *,
    package_id: int,
    key: str,
    name: str,
    description: str,
    tools: list[str],
    timeout: int,
    sort_order: int,
) -> None:
    config = json.dumps({"builtin_type": "context_tools", "tools": tools})
    row = conn.execute(
        text(
            "SELECT id FROM skills "
            "WHERE key = :key AND tenant_id IS NULL AND is_deleted = false "
            "ORDER BY id LIMIT 1"
        ),
        {"key": key},
    ).fetchone()
    if row:
        conn.execute(
            text(
                "UPDATE skills "
                "SET package_id = :package_id, name = :name, "
                "    description = :description, type = 'builtin', "
                "    source_type = 'platform_builtin', version = '1.0.0', "
                "    status = 'active', is_readonly = true, "
                "    config = CAST(:config AS jsonb), is_system = true, "
                "    is_active = true, timeout = :timeout, "
                "    sort_order = :sort_order, updated_at = NOW() "
                "WHERE id = :id"
            ),
            {
                "id": row[0],
                "package_id": package_id,
                "name": name,
                "description": description,
                "config": config,
                "timeout": timeout,
                "sort_order": sort_order,
            },
        )
        return

    conn.execute(
        text(
            "INSERT INTO skills "
            "(tenant_id, package_id, name, key, description, type, source_type, "
            " version, status, is_readonly, config, is_system, is_active, "
            " timeout, sort_order, created_at, updated_at, is_deleted) "
            "VALUES "
            "(NULL, :package_id, :name, :key, :description, 'builtin', "
            " 'platform_builtin', '1.0.0', 'active', true, "
            " CAST(:config AS jsonb), true, true, "
            " :timeout, :sort_order, NOW(), NOW(), false)"
        ),
        {
            "package_id": package_id,
            "name": name,
            "key": key,
            "description": description,
            "config": config,
            "timeout": timeout,
            "sort_order": sort_order,
        },
    )


def upgrade() -> None:
    conn = op.get_bind()
    package_id = _ensure_package(conn)
    _ensure_skill(
        conn,
        package_id=package_id,
        key=KB_SKILL_KEY,
        name=KB_SKILL_NAME,
        description=(
            "检索当前智能体绑定的知识库，返回片段、来源与引用线索。"
            "工具 schema 由代码定义。"
        ),
        tools=["search_agent_knowledge_base"],
        timeout=45,
        sort_order=0,
    )
    _ensure_skill(
        conn,
        package_id=package_id,
        key=MEMORY_SKILL_KEY,
        name=MEMORY_SKILL_NAME,
        description=(
            "保存与召回当前用户在当前智能体下的长期记忆。"
            "工具 schema 由代码定义。"
        ),
        tools=["save_long_term_memory", "recall_long_term_memory"],
        timeout=30,
        sort_order=1,
    )
    print("[SEED] System context tools skill package seeded.")


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        text(
            "DELETE FROM skills "
            "WHERE key IN (:kb_key, :memory_key) "
            "  AND tenant_id IS NULL AND is_system = true"
        ),
        {"kb_key": KB_SKILL_KEY, "memory_key": MEMORY_SKILL_KEY},
    )
    conn.execute(
        text(
            "DELETE FROM skill_packages "
            "WHERE name = :name AND tenant_id IS NULL AND is_system = true"
        ),
        {"name": SKILL_PACKAGE_NAME},
    )
    print("[SEED] System context tools skill package removed.")
