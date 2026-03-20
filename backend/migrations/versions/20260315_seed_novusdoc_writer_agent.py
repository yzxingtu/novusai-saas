"""seed NovusDoc Writer agent and bind system.ai_writing

Creates a platform-level agent "NovusDoc Writer" (visible on admin and all tenants via scope=global_shared)
and sets system_agent_assignments.system.ai_writing.agent_id to it so the agent appears
in Ctrl+K @ list as a normal agent without separate feature-agents API.

Revision ID: 20260315_novusdoc_wr
Revises: 20260315_ai_desc
Create Date: 2026-03-15

"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "20260315_novusdoc_wr"
down_revision: str | Sequence[str] | None = "20260315_ai_desc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FEATURE_CODE = "system.ai_writing"
AGENT_NAME = "NovusDoc Writer"
AGENT_DESCRIPTION = (
    "NovusDoc 文档写作助手 — 嵌入在富文本编辑器中的 AI 写作智能体。"
    "支持续写、优化、校对、翻译、摘要、扩写、重写等。"
)
AGENT_SYSTEM_PROMPT = (
    "You are NovusDoc Writer, an AI writing assistant embedded in the rich text editor. "
    "You help users continue, optimize, proofread, translate, summarize, expand, and rewrite content. "
    "Match the document's style, tone, and language. Be concise and accurate.\n\n"
    "When editor tools (pageop_get_editor_html, pageop_replace_section, etc.) are available, "
    "use them to read and modify the document directly — do not use invoke_page_operation. "
    "When in draft mode (no page context), you may output Markdown for the user to adopt. "
    "Do not echo HTML, JSON or raw tool output to the user; respond in natural language only."
)


def _find_chat_model(conn):
    row = conn.execute(text(
        "SELECT id FROM ai_models "
        "WHERE type = 'chat' AND is_active = true AND is_deleted = false "
        "ORDER BY id LIMIT 1"
    )).fetchone()
    if row:
        return row[0]
    # Fallback: use model_id from an existing published agent (e.g. 智能助手)
    row = conn.execute(text(
        "SELECT model_id FROM agents "
        "WHERE tenant_id IS NULL AND is_deleted = false AND status = 'published' "
        "ORDER BY id LIMIT 1"
    )).fetchone()
    return row[0] if row else None


def upgrade() -> None:
    conn = op.get_bind()

    existing = conn.execute(text(
        "SELECT id FROM agents "
        "WHERE name = :name AND tenant_id IS NULL AND is_deleted = false"
    ), {"name": AGENT_NAME}).fetchone()

    if existing:
        agent_id = existing[0]
        print(f"[SEED] NovusDoc Writer agent already exists (id={agent_id})")
    else:
        model_id = _find_chat_model(conn)
        if not model_id:
            print(
                "[SEED] WARNING: No active chat model found, skipping NovusDoc Writer creation. "
                "Create an AI model first, then re-run migration."
            )
            return
        result = conn.execute(text(
            "INSERT INTO agents "
            "(tenant_id, name, description, scope, system_prompt, model_id, "
            " temperature, execution_mode, status, visibility, memory_enabled, is_system, "
            " created_at, updated_at, is_deleted) "
            "VALUES "
            "(NULL, :name, :description, 'global_shared', :system_prompt, :model_id, "
            " 0.7, 'conversation', 'published', 'public', true, true, "
            " NOW(), NOW(), false) "
            "RETURNING id"
        ), {
            "name": AGENT_NAME,
            "description": AGENT_DESCRIPTION,
            "system_prompt": AGENT_SYSTEM_PROMPT,
            "model_id": model_id,
        })
        agent_id = result.fetchone()[0]
        print(f"[SEED] Created NovusDoc Writer agent (id={agent_id}, model_id={model_id})")

    conn.execute(text(
        "UPDATE system_agent_assignments "
        "SET agent_id = :agent_id, updated_at = NOW() "
        "WHERE feature_code = :code AND tenant_id IS NULL AND is_deleted = false"
    ), {"agent_id": agent_id, "code": FEATURE_CODE})
    print(f"[SEED] Bound {FEATURE_CODE} to agent_id={agent_id}")


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text(
        "UPDATE system_agent_assignments "
        "SET agent_id = NULL, updated_at = NOW() "
        "WHERE feature_code = :code AND tenant_id IS NULL"
    ), {"code": FEATURE_CODE})
    conn.execute(text(
        "DELETE FROM agents "
        "WHERE name = :name AND tenant_id IS NULL AND is_system = true"
    ), {"name": AGENT_NAME})
    print("[SEED] Unbound system.ai_writing and removed NovusDoc Writer agent.")
