"""seed_system_agents_skills

NOTE: SkillPackages partially superseded by 20260226_0410_merge_system_skill_packages:
  - 系统聊天技能包 → renamed to 系统核心技能包 (unified package)
  - 系统向量化技能包 → soft-deleted, skill moved to unified package
  Agents (system_chat_agent, system_embedding_agent) and skills (llm_chat, llm_embedding)
  remain valid and are now under the unified package.

Original: Create system-level Agents, Skills, and SkillPackages with is_system=True.
These records serve as the unified AI dispatch layer (Agent→Skill architecture).

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-02-14 00:10:00.000000+08:00

"""
from typing import Sequence, Union

import json

from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# Seed data definitions
# ---------------------------------------------------------------------------

SYSTEM_SKILL_PACKAGES = [
    {
        "name": "系统聊天技能包",
        "description": "系统内置的 LLM 聊天能力，供系统聊天 Agent 使用",
        "scope": "admin",
        "sort_order": 0,
    },
    {
        "name": "系统向量化技能包",
        "description": "系统内置的文本向量化能力，供系统 Embedding Agent 使用",
        "scope": "admin",
        "sort_order": 1,
    },
]

SYSTEM_SKILLS = [
    {
        "package_name": "系统聊天技能包",
        "name": "llm_chat",
        "description": "直接调用 LLM 进行多轮聊天对话",
        "type": "builtin",
        "scope": "admin",
        "config": {"builtin_type": "llm_chat"},
        "timeout": 120,
        "sort_order": 0,
    },
    {
        "package_name": "系统向量化技能包",
        "name": "llm_embedding",
        "description": "调用 Embedding 模型将文本转换为向量",
        "type": "builtin",
        "scope": "admin",
        "config": {"builtin_type": "llm_embedding"},
        "timeout": 60,
        "sort_order": 0,
    },
]

SYSTEM_AGENTS = [
    {
        "name": "system_chat_agent",
        "description": "系统聊天 Agent，提供统一的 LLM 聊天能力入口",
        "system_prompt": "You are a helpful AI assistant.",
        "model_type": "chat",
        "skill_name": "llm_chat",
        "scope": "admin",
        "execution_mode": "conversation",
        "temperature": 0.7,
        "status": "published",
        "visibility": "public",
    },
    {
        "name": "system_embedding_agent",
        "description": "系统向量化 Agent，提供统一的文本 Embedding 能力入口",
        "system_prompt": "Embedding agent.",
        "model_type": "embedding",
        "skill_name": "llm_embedding",
        "scope": "admin",
        "execution_mode": "task",
        "temperature": 0.0,
        "status": "published",
        "visibility": "public",
    },
]


def _find_model(conn, model_type: str) -> int | None:
    """Find the first active AI model of the given type."""
    row = conn.execute(text(
        "SELECT id FROM ai_models "
        "WHERE type = :type AND is_active = true AND is_deleted = false "
        "ORDER BY id LIMIT 1"
    ), {"type": model_type}).fetchone()
    return row[0] if row else None


def upgrade() -> None:
    conn = op.get_bind()

    # ---------- 1. Create system skill packages ----------
    pkg_ids: dict[str, int] = {}
    for pkg in SYSTEM_SKILL_PACKAGES:
        existing = conn.execute(text(
            "SELECT id FROM skill_packages "
            "WHERE name = :name AND tenant_id IS NULL AND is_deleted = false"
        ), {"name": pkg["name"]}).fetchone()

        if existing:
            pkg_ids[pkg["name"]] = existing[0]
            print(f"[SEED] SkillPackage '{pkg['name']}' already exists (id={existing[0]})")
            continue

        result = conn.execute(text(
            "INSERT INTO skill_packages "
            "(tenant_id, name, description, scope, is_system, is_active, sort_order, "
            " created_at, updated_at, is_deleted) "
            "VALUES "
            "(NULL, :name, :description, :scope, true, true, :sort_order, "
            " NOW(), NOW(), false) "
            "RETURNING id"
        ), {
            "name": pkg["name"],
            "description": pkg["description"],
            "scope": pkg["scope"],
            "sort_order": pkg["sort_order"],
        })
        pkg_id = result.fetchone()[0]
        pkg_ids[pkg["name"]] = pkg_id
        print(f"[SEED] Created system SkillPackage '{pkg['name']}' (id={pkg_id})")

    # ---------- 2. Create system skills ----------
    skill_ids: dict[str, int] = {}
    for skill in SYSTEM_SKILLS:
        existing = conn.execute(text(
            "SELECT id FROM skills "
            "WHERE name = :name AND tenant_id IS NULL AND is_deleted = false"
        ), {"name": skill["name"]}).fetchone()

        if existing:
            skill_ids[skill["name"]] = existing[0]
            print(f"[SEED] Skill '{skill['name']}' already exists (id={existing[0]})")
            continue

        pkg_id = pkg_ids.get(skill["package_name"])
        if not pkg_id:
            print(f"[SEED] WARNING: Package '{skill['package_name']}' not found, skipping skill '{skill['name']}'")
            continue

        result = conn.execute(text(
            "INSERT INTO skills "
            "(tenant_id, package_id, name, description, type, scope, config, "
            " is_system, is_active, timeout, sort_order, "
            " created_at, updated_at, is_deleted) "
            "VALUES "
            "(NULL, :package_id, :name, :description, :type, :scope, CAST(:config AS jsonb), "
            " true, true, :timeout, :sort_order, "
            " NOW(), NOW(), false) "
            "RETURNING id"
        ), {
            "package_id": pkg_id,
            "name": skill["name"],
            "description": skill["description"],
            "type": skill["type"],
            "scope": skill["scope"],
            "config": json.dumps(skill["config"]),
            "timeout": skill["timeout"],
            "sort_order": skill["sort_order"],
        })
        skill_id = result.fetchone()[0]
        skill_ids[skill["name"]] = skill_id
        print(f"[SEED] Created system Skill '{skill['name']}' (id={skill_id})")

    # ---------- 3. Create system agents (requires AI models) ----------
    for agent in SYSTEM_AGENTS:
        existing = conn.execute(text(
            "SELECT id FROM agents "
            "WHERE name = :name AND tenant_id IS NULL AND is_deleted = false"
        ), {"name": agent["name"]}).fetchone()

        if existing:
            print(f"[SEED] Agent '{agent['name']}' already exists (id={existing[0]})")
            continue

        model_id = _find_model(conn, agent["model_type"])
        if not model_id:
            print(
                f"[SEED] WARNING: No active {agent['model_type']} model found, "
                f"skipping agent '{agent['name']}'. "
                f"Create an AI model first, then re-run migration."
            )
            continue

        result = conn.execute(text(
            "INSERT INTO agents "
            "(tenant_id, name, description, scope, system_prompt, model_id, "
            " temperature, execution_mode, status, visibility, is_system, "
            " created_at, updated_at, is_deleted) "
            "VALUES "
            "(NULL, :name, :description, :scope, :system_prompt, :model_id, "
            " :temperature, :execution_mode, :status, :visibility, true, "
            " NOW(), NOW(), false) "
            "RETURNING id"
        ), {
            "name": agent["name"],
            "description": agent["description"],
            "scope": agent["scope"],
            "system_prompt": agent["system_prompt"],
            "model_id": model_id,
            "temperature": agent["temperature"],
            "execution_mode": agent["execution_mode"],
            "status": agent["status"],
            "visibility": agent["visibility"],
        })
        agent_id = result.fetchone()[0]
        print(f"[SEED] Created system Agent '{agent['name']}' (id={agent_id}, model_id={model_id})")

        # ---------- 4. Bind skill package to agent ----------
        skill_name = agent["skill_name"]
        # Look up which package contains this skill
        skill_id = skill_ids.get(skill_name)
        if skill_id:
            # Find the package_id for this skill
            pkg_row = conn.execute(text(
                "SELECT package_id FROM skills WHERE id = :skill_id"
            ), {"skill_id": skill_id}).fetchone()
            if pkg_row:
                pkg_id_for_binding = pkg_row[0]
                conn.execute(text(
                    "INSERT INTO agent_skill_bindings "
                    "(tenant_id, agent_id, package_id, enabled, sort_order, "
                    " created_at, updated_at, is_deleted) "
                    "VALUES "
                    "(NULL, :agent_id, :package_id, true, 0, "
                    " NOW(), NOW(), false)"
                ), {"agent_id": agent_id, "package_id": pkg_id_for_binding})
                print(f"[SEED] Bound package (id={pkg_id_for_binding}) to agent '{agent['name']}'")
            else:
                print(f"[SEED] WARNING: Skill '{skill_name}' has no package_id, skipping binding")
        else:
            print(f"[SEED] WARNING: Skill '{skill_name}' not found, skipping binding")

    print("[SEED] System agents and skills seeding done.")


def downgrade() -> None:
    """Remove seed system agents, skills, packages, and bindings."""
    conn = op.get_bind()

    # Remove bindings first (FK cascade would handle it, but be explicit)
    for agent in SYSTEM_AGENTS:
        conn.execute(text(
            "DELETE FROM agent_skill_bindings "
            "WHERE agent_id IN ("
            "  SELECT id FROM agents WHERE name = :name AND tenant_id IS NULL"
            ")"
        ), {"name": agent["name"]})

    # Remove agents
    for agent in SYSTEM_AGENTS:
        conn.execute(text(
            "DELETE FROM agents WHERE name = :name AND tenant_id IS NULL AND is_system = true"
        ), {"name": agent["name"]})

    # Remove skills
    for skill in SYSTEM_SKILLS:
        conn.execute(text(
            "DELETE FROM skills WHERE name = :name AND tenant_id IS NULL AND is_system = true"
        ), {"name": skill["name"]})

    # Remove packages
    for pkg in SYSTEM_SKILL_PACKAGES:
        conn.execute(text(
            "DELETE FROM skill_packages WHERE name = :name AND tenant_id IS NULL AND is_system = true"
        ), {"name": pkg["name"]})

    print("[SEED] System agents and skills removed.")
