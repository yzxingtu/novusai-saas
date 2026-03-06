"""seed Router agent and default_chat assignment

Creates:
1. Router system agent (execution_mode=router, scope=admin_and_all, is_system=True)
2. default_chat SystemAgentAssignment (feature_code='default_chat', agent_id=NULL)

Both operations are idempotent — safe to re-run.

Revision ID: 20260305_router_seed
Revises: 20260305_msg_agent
Create Date: 2026-03-05 19:00:00.000000+00:00

"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "20260305_router_seed"
down_revision: str | Sequence[str] | None = "20260305_msg_agent"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# ---------------------------------------------------------------------------
# Router agent definition
# ---------------------------------------------------------------------------

ROUTER_AGENT_NAME = "系统路由智能体"

ROUTER_SYSTEM_PROMPT = """\
You are an intelligent routing agent. Your task is to analyze the user's message \
and optional page context, then select the most appropriate agent from the \
available candidates.

Rules:
1. Analyze the user's intent from the message content.
2. Consider the page context (if provided) to understand the user's current workflow.
3. Match the intent against each candidate agent's name and description.
4. Return your decision as a JSON object with exactly two fields:
   - agent_id: the integer ID of the selected agent
   - confidence: a float between 0.0 and 1.0 indicating your confidence

Response format (ONLY output this JSON, nothing else):
{"agent_id": <id>, "confidence": <0.0-1.0>}

If none of the candidates clearly match, select the most general-purpose one \
and set confidence below 0.5.\
"""

DEFAULT_CHAT_FEATURE_CODE = "default_chat"
DEFAULT_CHAT_FEATURE_NAME = "默认聊天智能体"
DEFAULT_CHAT_DESCRIPTION = "默认对话智能体，当路由器无法确定最佳智能体或未配置路由器时使用的后备智能体。"


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

    # ---------- 1. Create Router system agent ----------
    existing = conn.execute(text(
        "SELECT id FROM agents "
        "WHERE name = :name AND tenant_id IS NULL AND is_deleted = false"
    ), {"name": ROUTER_AGENT_NAME}).fetchone()

    if existing:
        print(f"[SEED] Router agent '{ROUTER_AGENT_NAME}' already exists (id={existing[0]})")
    else:
        model_id = _find_chat_model(conn)
        if not model_id:
            print(
                f"[SEED] WARNING: No active chat model found, "
                f"skipping Router agent creation. "
                f"Create an AI model first, then re-run migration."
            )
        else:
            result = conn.execute(text(
                "INSERT INTO agents "
                "(tenant_id, name, description, scope, system_prompt, model_id, "
                " temperature, execution_mode, status, visibility, memory_enabled, is_system, "
                " created_at, updated_at, is_deleted) "
                "VALUES "
                "(NULL, :name, :description, :scope, :system_prompt, :model_id, "
                " :temperature, :execution_mode, :status, :visibility, true, true, "
                " NOW(), NOW(), false) "
                "RETURNING id"
            ), {
                "name": ROUTER_AGENT_NAME,
                "description": "系统路由智能体 — 分析用户消息并自动分配到最合适的智能体",
                "scope": "admin_and_all",
                "system_prompt": ROUTER_SYSTEM_PROMPT,
                "model_id": model_id,
                "temperature": 0.1,
                "execution_mode": "router",
                "status": "published",
                "visibility": "public",
            })
            agent_id = result.fetchone()[0]
            print(f"[SEED] Created Router agent '{ROUTER_AGENT_NAME}' (id={agent_id}, model_id={model_id})")

    # ---------- 2. Create default_chat SystemAgentAssignment ----------
    existing_assign = conn.execute(text(
        "SELECT id FROM system_agent_assignments "
        "WHERE feature_code = :code AND tenant_id IS NULL AND is_deleted = false"
    ), {"code": DEFAULT_CHAT_FEATURE_CODE}).fetchone()

    if existing_assign:
        print(f"[SEED] default_chat assignment already exists (id={existing_assign[0]})")
    else:
        result = conn.execute(text(
            "INSERT INTO system_agent_assignments "
            "(feature_code, feature_name, description, tenant_id, agent_id, "
            " is_active, created_at, updated_at, is_deleted) "
            "VALUES "
            "(:code, :name, :desc, NULL, NULL, "
            " true, NOW(), NOW(), false) "
            "RETURNING id"
        ), {
            "code": DEFAULT_CHAT_FEATURE_CODE,
            "name": DEFAULT_CHAT_FEATURE_NAME,
            "desc": DEFAULT_CHAT_DESCRIPTION,
        })
        assign_id = result.fetchone()[0]
        print(f"[SEED] Created default_chat assignment (id={assign_id}, agent_id=NULL — configure via admin UI)")

    print("[SEED] Router agent + default_chat assignment seeding done.")


def downgrade() -> None:
    """Remove seed Router agent and default_chat assignment."""
    conn = op.get_bind()

    # Remove default_chat assignment
    conn.execute(text(
        "DELETE FROM system_agent_assignments "
        "WHERE feature_code = :code AND tenant_id IS NULL"
    ), {"code": DEFAULT_CHAT_FEATURE_CODE})

    # Remove Router agent (match by execution_mode, not name, since name may vary)
    conn.execute(text(
        "DELETE FROM agents "
        "WHERE execution_mode = 'router' AND tenant_id IS NULL AND is_system = true"
    ))

    print("[SEED] Router agent + default_chat assignment removed.")
