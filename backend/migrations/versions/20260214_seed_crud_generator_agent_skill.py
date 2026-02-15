"""seed_crud_generator_agent_skill

Create system-level CRUD Generator SkillPackage, Skill, and Agent.
  - SkillPackage: CRUD Generator 技能包 (is_system=true)
  - Skill: crud_generator (type=builtin, is_system=true, builtin_type=crud_generator)
    input_schema: multi_tool 格式，8 个 Tool
  - Agent: crud_generator_assistant (is_system=true, bound to crud_generator skill)

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-02-14 19:00:00.000000+08:00

"""
from typing import Sequence, Union

import json

from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = "f2a3b4c5d6e7"
down_revision: Union[str, None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# Skill config + input_schema (multi_tool format, 8 tools)
# ---------------------------------------------------------------------------

_SKILL_CONFIG = {
    "builtin_type": "crud_generator",
    "dev_only": True,
}

_SKILL_INPUT_SCHEMA: dict | None = None


def _get_input_schema() -> dict:
    """Lazy build input_schema from skill_definitions (avoids import at module level)."""
    global _SKILL_INPUT_SCHEMA
    if _SKILL_INPUT_SCHEMA is None:
        from app.codegen.skill_definitions import build_skill_input_schema
        _SKILL_INPUT_SCHEMA = build_skill_input_schema()
    return _SKILL_INPUT_SCHEMA


def _get_system_prompt() -> str:
    """Lazy import CRUD_AGENT_SYSTEM_PROMPT."""
    from app.codegen.ai_prompts import CRUD_AGENT_SYSTEM_PROMPT
    return CRUD_AGENT_SYSTEM_PROMPT


def _find_chat_model(conn) -> int | None:
    """Find the first active chat AI model."""
    row = conn.execute(text(
        "SELECT id FROM ai_models "
        "WHERE type = 'chat' AND is_active = true AND is_deleted = false "
        "ORDER BY id LIMIT 1"
    )).fetchone()
    return row[0] if row else None


def upgrade() -> None:
    conn = op.get_bind()

    # ---------- 1. Create SkillPackage ----------
    existing_pkg = conn.execute(text(
        "SELECT id FROM skill_packages "
        "WHERE name = 'CRUD Generator 技能包' AND tenant_id IS NULL AND is_deleted = false"
    )).fetchone()

    if existing_pkg:
        pkg_id = existing_pkg[0]
        print(f"[SEED] SkillPackage 'CRUD Generator 技能包' already exists (id={pkg_id})")
    else:
        result = conn.execute(text(
            "INSERT INTO skill_packages "
            "(tenant_id, name, description, scope, is_system, is_active, sort_order, "
            " created_at, updated_at, is_deleted) "
            "VALUES "
            "(NULL, 'CRUD Generator 技能包', 'CRUD 代码生成 AI 辅助工具集', 'admin', "
            " true, true, 10, NOW(), NOW(), false) "
            "RETURNING id"
        ))
        pkg_id = result.fetchone()[0]
        print(f"[SEED] Created SkillPackage 'CRUD Generator 技能包' (id={pkg_id})")

    # ---------- 2. Create Skill ----------
    existing_skill = conn.execute(text(
        "SELECT id FROM skills "
        "WHERE name = 'crud_generator' AND tenant_id IS NULL AND is_deleted = false"
    )).fetchone()

    input_schema = _get_input_schema()

    if existing_skill:
        skill_id = existing_skill[0]
        # 更新已有 Skill 的 config 和 input_schema
        conn.execute(text(
            "UPDATE skills SET "
            "config = CAST(:config AS jsonb), "
            "input_schema = CAST(:input_schema AS jsonb), "
            "updated_at = NOW() "
            "WHERE id = :id"
        ), {
            "id": skill_id,
            "config": json.dumps(_SKILL_CONFIG),
            "input_schema": json.dumps(input_schema),
        })
        print(f"[SEED] Skill 'crud_generator' already exists (id={skill_id}), updated config/input_schema")
    else:
        result = conn.execute(text(
            "INSERT INTO skills "
            "(tenant_id, package_id, name, description, type, scope, config, input_schema, "
            " is_system, is_active, timeout, sort_order, "
            " created_at, updated_at, is_deleted) "
            "VALUES "
            "(NULL, :package_id, 'crud_generator', "
            " 'CRUD 代码生成 AI 辅助工具集 — 8 个 Tool：配置生成、预览、写入、翻译、字段推荐、Slot、样式、意图分析', "
            " 'builtin', 'admin', CAST(:config AS jsonb), CAST(:input_schema AS jsonb), "
            " true, true, 120, 0, NOW(), NOW(), false) "
            "RETURNING id"
        ), {
            "package_id": pkg_id,
            "config": json.dumps(_SKILL_CONFIG),
            "input_schema": json.dumps(input_schema),
        })
        skill_id = result.fetchone()[0]
        print(f"[SEED] Created Skill 'crud_generator' (id={skill_id})")

    # ---------- 3. Create Agent ----------
    existing_agent = conn.execute(text(
        "SELECT id FROM agents "
        "WHERE name = 'crud_generator_assistant' AND tenant_id IS NULL AND is_deleted = false"
    )).fetchone()

    system_prompt = _get_system_prompt()

    if existing_agent:
        agent_id = existing_agent[0]
        # 更新系统提示词
        conn.execute(text(
            "UPDATE agents SET system_prompt = :system_prompt, updated_at = NOW() "
            "WHERE id = :id"
        ), {"id": agent_id, "system_prompt": system_prompt})
        print(f"[SEED] Agent 'crud_generator_assistant' already exists (id={agent_id}), updated system_prompt")
    else:
        model_id = _find_chat_model(conn)
        if not model_id:
            print(
                "[SEED] WARNING: No active chat model found, skipping crud_generator_assistant agent. "
                "Create an AI model first, then re-run migration."
            )
            return

        result = conn.execute(text(
            "INSERT INTO agents "
            "(tenant_id, name, description, scope, system_prompt, model_id, "
            " temperature, execution_mode, status, visibility, is_system, "
            " created_at, updated_at, is_deleted) "
            "VALUES "
            "(NULL, 'crud_generator_assistant', "
            " 'CRUD 代码生成助手 — 自然语言驱动全栈 CRUD 代码生成、字段推荐、i18n 翻译、布局推荐', "
            " 'admin', :system_prompt, :model_id, "
            " 0.3, 'conversation', 'published', 'public', true, "
            " NOW(), NOW(), false) "
            "RETURNING id"
        ), {
            "system_prompt": system_prompt,
            "model_id": model_id,
        })
        agent_id = result.fetchone()[0]
        print(f"[SEED] Created Agent 'crud_generator_assistant' (id={agent_id}, model_id={model_id})")

    # ---------- 4. Bind skill package to agent (idempotent) ----------
    existing_binding = conn.execute(text(
        "SELECT id FROM agent_skill_bindings "
        "WHERE agent_id = :agent_id AND package_id = :package_id AND is_deleted = false"
    ), {"agent_id": agent_id, "package_id": pkg_id}).fetchone()

    if not existing_binding:
        conn.execute(text(
            "INSERT INTO agent_skill_bindings "
            "(tenant_id, agent_id, package_id, enabled, sort_order, "
            " created_at, updated_at, is_deleted) "
            "VALUES "
            "(NULL, :agent_id, :package_id, true, 0, NOW(), NOW(), false)"
        ), {"agent_id": agent_id, "package_id": pkg_id})
        print(f"[SEED] Bound package (id={pkg_id}) to agent 'crud_generator_assistant'")
    else:
        print(f"[SEED] Binding already exists")

    print("[SEED] CRUD Generator seed done.")


def downgrade() -> None:
    """Remove CRUD Generator seed data."""
    conn = op.get_bind()

    # Remove binding
    conn.execute(text(
        "DELETE FROM agent_skill_bindings "
        "WHERE agent_id IN ("
        "  SELECT id FROM agents WHERE name = 'crud_generator_assistant' AND tenant_id IS NULL"
        ")"
    ))

    # Remove agent
    conn.execute(text(
        "DELETE FROM agents "
        "WHERE name = 'crud_generator_assistant' AND tenant_id IS NULL AND is_system = true"
    ))

    # Remove skill
    conn.execute(text(
        "DELETE FROM skills "
        "WHERE name = 'crud_generator' AND tenant_id IS NULL AND is_system = true"
    ))

    # Remove package
    conn.execute(text(
        "DELETE FROM skill_packages "
        "WHERE name = 'CRUD Generator 技能包' AND tenant_id IS NULL AND is_system = true"
    ))

    print("[SEED] CRUD Generator seed data removed.")
