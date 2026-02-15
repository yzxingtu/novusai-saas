"""fix_crud_generator_agent

Create or update the crud_generator_assistant Agent and bind it
to the crud_generator skill package.

Problem:
  - Agent 'crud_generator_assistant' doesn't exist in DB
  - No agent_skill_binding exists

Fix:
  - Create agent with full CRUD_AGENT_SYSTEM_PROMPT
  - Create agent_skill_binding to the CRUD Generator skill package

Revision ID: aa0215020000
Revises: aa0215010000
Create Date: 2026-02-15 05:55:00.000000+08:00

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = "aa0215020000"
down_revision: Union[str, None] = "aa0215010000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _get_system_prompt() -> str:
    """Lazy import CRUD_AGENT_SYSTEM_PROMPT."""
    from app.codegen.ai_prompts import CRUD_AGENT_SYSTEM_PROMPT
    return CRUD_AGENT_SYSTEM_PROMPT


def upgrade() -> None:
    conn = op.get_bind()

    system_prompt = _get_system_prompt()

    # ---------- 1. Find skill package ----------
    pkg_row = conn.execute(text(
        "SELECT id FROM skill_packages "
        "WHERE name = 'CRUD Generator 技能包' AND tenant_id IS NULL AND is_deleted = false "
        "LIMIT 1"
    )).fetchone()

    if not pkg_row:
        print("[FIX] No 'CRUD Generator 技能包' skill package found, skipping agent creation.")
        return

    pkg_id = pkg_row[0]

    # ---------- 2. Create or update Agent ----------
    existing_agent = conn.execute(text(
        "SELECT id FROM agents "
        "WHERE name = 'crud_generator_assistant' AND tenant_id IS NULL AND is_deleted = false "
        "LIMIT 1"
    )).fetchone()

    if existing_agent:
        agent_id = existing_agent[0]
        conn.execute(text(
            "UPDATE agents SET "
            "system_prompt = :system_prompt, "
            "updated_at = NOW() "
            "WHERE id = :id"
        ), {"id": agent_id, "system_prompt": system_prompt})
        print(f"[FIX] Updated agent system_prompt (id={agent_id}, len={len(system_prompt)})")
    else:
        # Find a chat model
        model_row = conn.execute(text(
            "SELECT id FROM ai_models "
            "WHERE type = 'chat' AND is_active = true AND is_deleted = false "
            "ORDER BY id LIMIT 1"
        )).fetchone()

        if not model_row:
            print("[FIX] WARNING: No active chat model found. Creating agent with model_id=NULL.")
            model_id_val = "NULL"
            model_param = {}
        else:
            model_id_val = ":model_id"
            model_param = {"model_id": model_row[0]}

        result = conn.execute(text(
            "INSERT INTO agents "
            "(tenant_id, name, description, scope, system_prompt, model_id, "
            " temperature, execution_mode, status, visibility, is_system, "
            " created_at, updated_at, is_deleted) "
            "VALUES "
            f"(NULL, 'crud_generator_assistant', "
            f"'CRUD 代码生成助手 — 自然语言驱动全栈 CRUD 代码生成、字段推荐、i18n 翻译、布局推荐', "
            f"'admin', :system_prompt, {model_id_val}, "
            f"0.3, 'conversation', 'published', 'public', true, "
            f"NOW(), NOW(), false) "
            "RETURNING id"
        ), {"system_prompt": system_prompt, **model_param})

        agent_id = result.fetchone()[0]
        model_info = f"model_id={model_row[0]}" if model_row else "model_id=NULL"
        print(f"[FIX] Created agent 'crud_generator_assistant' (id={agent_id}, {model_info}, prompt_len={len(system_prompt)})")

    # ---------- 3. Create binding (idempotent) ----------
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
        print(f"[FIX] Created binding: agent={agent_id} → package={pkg_id}")
    else:
        print(f"[FIX] Binding already exists (id={existing_binding[0]})")


def downgrade() -> None:
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
