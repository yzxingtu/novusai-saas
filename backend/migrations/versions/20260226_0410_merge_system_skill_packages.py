"""merge_system_skill_packages

Merge three system skill packages into one unified "系统核心技能包":
  - 系统聊天技能包 (llm_chat)
  - 系统向量化技能包 (llm_embedding)
  - 系统数据智能技能包 (平台数据管理)

Also adds new builtin skills:
  - web_search: Internet search + URL fetch (multi-tool builtin)

Revision ID: 20260226_0410
Revises: ffa4ebdf6d2e
Create Date: 2026-02-26 04:10:00.000000+08:00

"""
from typing import Sequence, Union

import json

from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = "20260226_0410"
down_revision: Union[str, None] = "ffa4ebdf6d2e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_NEW_PKG_NAME = "系统核心技能包"
_NEW_PKG_DESC = (
    "系统内置的核心能力包。包含 LLM 聊天、文本向量化、数据智能、联网搜索等"
    "基础能力。系统 Agent 默认绑定此技能包。不可删除或禁用。"
)

_OLD_PKG_NAMES = [
    "系统聊天技能包",
    "系统向量化技能包",
    "系统数据智能技能包",
]

_NEW_SKILLS = [
    {
        "name": "web_search",
        "description": "联网搜索。通过搜索引擎查询互联网上的最新信息和网页内容。",
        "type": "builtin",
        "config": {
            "builtin_type": "web_search",
            "tools": [
                {
                    "name": "web_search",
                    "description": (
                        "联网搜索/Search the internet for up-to-date information. "
                        "搜索互联网获取最新信息，返回搜索结果列表（标题、链接、摘要）。"
                        "当需要查询实时信息、最新新闻、人物资料等训练数据之外的内容时使用。"
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The search query string",
                            },
                            "max_results": {
                                "type": "integer",
                                "description": "Maximum number of results to return (1-10, default: 5)",
                            },
                        },
                        "required": ["query"],
                    },
                },
                {
                    "name": "fetch_url",
                    "description": (
                        "抓取网页内容/Fetch and extract text from a web page URL. "
                        "获取指定网址的文本内容，用于阅读搜索结果中的具体网页。"
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {
                                "type": "string",
                                "description": "The URL of the web page to fetch",
                            },
                            "max_length": {
                                "type": "integer",
                                "description": "Maximum characters to return (500-20000, default: 5000)",
                            },
                        },
                        "required": ["url"],
                    },
                },
            ],
        },
        "timeout": 30,
        "sort_order": 10,
    },
]


def upgrade() -> None:
    conn = op.get_bind()

    # ── 1. Find the primary package to keep (系统聊天技能包) ──
    primary = conn.execute(text(
        "SELECT id FROM skill_packages "
        "WHERE name = :name AND is_system = true AND is_deleted = false"
    ), {"name": "系统聊天技能包"}).fetchone()

    if not primary:
        print("[MERGE] WARNING: 系统聊天技能包 not found, creating new unified package")
        result = conn.execute(text(
            "INSERT INTO skill_packages "
            "(tenant_id, name, description, scope, is_system, is_active, "
            " sort_order, bind_mode, created_at, updated_at, is_deleted) "
            "VALUES "
            "(NULL, :name, :desc, 'admin_only', true, true, "
            " 0, 'auto', NOW(), NOW(), false) "
            "RETURNING id"
        ), {"name": _NEW_PKG_NAME, "desc": _NEW_PKG_DESC})
        unified_pkg_id = result.fetchone()[0]
        print(f"[MERGE] Created unified package (id={unified_pkg_id})")
    else:
        unified_pkg_id = primary[0]
        conn.execute(text(
            "UPDATE skill_packages SET name = :name, description = :desc, "
            "updated_at = NOW() WHERE id = :id"
        ), {"name": _NEW_PKG_NAME, "desc": _NEW_PKG_DESC, "id": unified_pkg_id})
        print(f"[MERGE] Renamed package id={unified_pkg_id} -> '{_NEW_PKG_NAME}'")

    # ── 2. Find other system packages and move their skills ──
    other_pkg_ids = []
    for old_name in _OLD_PKG_NAMES:
        if old_name == "系统聊天技能包":
            continue
        row = conn.execute(text(
            "SELECT id FROM skill_packages "
            "WHERE name = :name AND is_system = true AND is_deleted = false"
        ), {"name": old_name}).fetchone()
        if row:
            other_pkg_ids.append(row[0])

    for old_id in other_pkg_ids:
        moved = conn.execute(text(
            "UPDATE skills SET package_id = :new_pkg, updated_at = NOW() "
            "WHERE package_id = :old_pkg AND is_deleted = false"
        ), {"new_pkg": unified_pkg_id, "old_pkg": old_id})
        print(f"[MERGE] Moved {moved.rowcount} skills from package {old_id} -> {unified_pkg_id}")

        updated = conn.execute(text(
            "UPDATE agent_skill_bindings SET package_id = :new_pkg, updated_at = NOW() "
            "WHERE package_id = :old_pkg AND is_deleted = false"
        ), {"new_pkg": unified_pkg_id, "old_pkg": old_id})
        if updated.rowcount > 0:
            print(f"[MERGE] Updated {updated.rowcount} bindings from package {old_id} -> {unified_pkg_id}")

        conn.execute(text(
            "UPDATE skill_packages SET is_deleted = true, deleted_at = NOW(), "
            "updated_at = NOW() WHERE id = :id"
        ), {"id": old_id})
        print(f"[MERGE] Soft-deleted old package id={old_id}")

    # ── 3. Deduplicate bindings (same agent may now have duplicate bindings) ──
    conn.execute(text("""
        DELETE FROM agent_skill_bindings
        WHERE id NOT IN (
            SELECT MIN(id) FROM agent_skill_bindings
            WHERE package_id = :pkg_id AND is_deleted = false
            GROUP BY agent_id
        )
        AND package_id = :pkg_id
        AND is_deleted = false
    """), {"pkg_id": unified_pkg_id})

    # ── 4. Add new skills (web_search) ──
    for skill_def in _NEW_SKILLS:
        existing = conn.execute(text(
            "SELECT id FROM skills "
            "WHERE name = :name AND package_id = :pkg_id AND is_deleted = false"
        ), {"name": skill_def["name"], "pkg_id": unified_pkg_id}).fetchone()

        if existing:
            print(f"[MERGE] Skill '{skill_def['name']}' already exists (id={existing[0]})")
            continue

        result = conn.execute(text(
            "INSERT INTO skills "
            "(tenant_id, package_id, name, description, type, config, "
            " is_system, is_active, timeout, sort_order, "
            " created_at, updated_at, is_deleted) "
            "VALUES "
            "(NULL, :pkg_id, :name, :desc, :type, CAST(:config AS jsonb), "
            " true, true, :timeout, :sort_order, "
            " NOW(), NOW(), false) "
            "RETURNING id"
        ), {
            "pkg_id": unified_pkg_id,
            "name": skill_def["name"],
            "desc": skill_def["description"],
            "type": skill_def["type"],
            "config": json.dumps(skill_def["config"]),
            "timeout": skill_def["timeout"],
            "sort_order": skill_def["sort_order"],
        })
        skill_id = result.fetchone()[0]
        print(f"[MERGE] Created skill '{skill_def['name']}' (id={skill_id})")

    # ── 5. Mark internal dispatch skills (not for function calling) ──
    for internal_name in ("llm_chat", "llm_embedding"):
        row = conn.execute(text(
            "SELECT id, config FROM skills "
            "WHERE name = :name AND is_system = true AND is_deleted = false"
        ), {"name": internal_name}).fetchone()
        if row:
            import json as _json
            cfg = row[1] if isinstance(row[1], dict) else _json.loads(row[1])
            if not cfg.get("internal"):
                cfg["internal"] = True
                conn.execute(text(
                    "UPDATE skills SET config = CAST(:c AS jsonb), updated_at = NOW() "
                    "WHERE id = :id"
                ), {"c": _json.dumps(cfg), "id": row[0]})
                print(f"[MERGE] Marked skill '{internal_name}' (id={row[0]}) as internal=true")

    print("[MERGE] System skill packages merge complete.")


def downgrade() -> None:
    # Downgrade is complex for seed data merges.
    # Old packages remain soft-deleted and can be restored manually.
    print("[MERGE] Downgrade: no-op. Old packages remain soft-deleted.")
