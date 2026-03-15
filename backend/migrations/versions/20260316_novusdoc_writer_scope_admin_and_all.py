"""fix NovusDoc Writer scope to admin_and_all (管理端与全部企业共享)

删除旧记录后重新创建，确保作用域为 admin_and_all，以便在管理端和企业端 @ 列表均可见。
幂等：若已是 admin_and_all 则仅重新绑定，否则删除后重建。

Revision ID: 20260316_novusdoc_scope
Revises: 20260315_novusdoc_wr
Create Date: 2026-03-16

"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "20260316_novusdoc_scope"
down_revision: str | Sequence[str] | None = "20260315_novusdoc_wr"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FEATURE_CODE = "system.ai_writing"
AGENT_NAME = "NovusDoc Writer"
SCOPE_TARGET = "admin_and_all"
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


def _find_model_id(conn):
    row = conn.execute(text(
        "SELECT id FROM ai_models "
        "WHERE type = 'chat' AND is_active = true AND is_deleted = false "
        "ORDER BY id LIMIT 1"
    )).fetchone()
    if row:
        return row[0]
    row = conn.execute(text(
        "SELECT model_id FROM agents "
        "WHERE tenant_id IS NULL AND is_deleted = false AND status = 'published' "
        "ORDER BY id LIMIT 1"
    )).fetchone()
    return row[0] if row else None


def upgrade() -> None:
    conn = op.get_bind()

    # 1) 解除 system.ai_writing 绑定
    conn.execute(text(
        "UPDATE system_agent_assignments "
        "SET agent_id = NULL, updated_at = NOW() "
        "WHERE feature_code = :code AND tenant_id IS NULL AND is_deleted = false"
    ), {"code": FEATURE_CODE})

    # 2) 删除作用域不为 admin_and_all 的 NovusDoc Writer（或不存在则跳过）
    conn.execute(text(
        "DELETE FROM agents "
        "WHERE name = :name AND tenant_id IS NULL AND is_system = true "
        "AND (scope IS NULL OR scope != :scope)"
    ), {"name": AGENT_NAME, "scope": SCOPE_TARGET})

    # 3) 若不存在则创建（scope=admin_and_all）
    existing = conn.execute(text(
        "SELECT id FROM agents "
        "WHERE name = :name AND tenant_id IS NULL AND is_deleted = false"
    ), {"name": AGENT_NAME}).fetchone()

    if existing:
        agent_id = existing[0]
        # 确保作用域和 system_prompt 正确
        conn.execute(text(
            "UPDATE agents SET scope = :scope, system_prompt = :prompt, updated_at = NOW() "
            "WHERE id = :id"
        ), {"scope": SCOPE_TARGET, "prompt": AGENT_SYSTEM_PROMPT, "id": agent_id})
        print(f"[SEED] NovusDoc Writer exists (id={agent_id}), scope and prompt updated")
    else:
        model_id = _find_model_id(conn)
        if not model_id:
            print(
                "[SEED] WARNING: No chat model / published agent, skipping NovusDoc Writer. "
                "Create an AI model or publish an agent, then re-run migration."
            )
            return
        result = conn.execute(text(
            "INSERT INTO agents "
            "(tenant_id, name, description, scope, system_prompt, model_id, "
            " temperature, execution_mode, status, visibility, memory_enabled, is_system, "
            " created_at, updated_at, is_deleted) "
            "VALUES "
            "(NULL, :name, :description, :scope, :system_prompt, :model_id, "
            " 0.7, 'conversation', 'published', 'public', true, true, "
            " NOW(), NOW(), false) "
            "RETURNING id"
        ), {
            "name": AGENT_NAME,
            "description": AGENT_DESCRIPTION,
            "scope": SCOPE_TARGET,
            "system_prompt": AGENT_SYSTEM_PROMPT,
            "model_id": model_id,
        })
        agent_id = result.fetchone()[0]
        print(f"[SEED] Created NovusDoc Writer (id={agent_id}, scope={SCOPE_TARGET})")

    # 4) 重新绑定 system.ai_writing
    conn.execute(text(
        "UPDATE system_agent_assignments "
        "SET agent_id = :agent_id, updated_at = NOW() "
        "WHERE feature_code = :code AND tenant_id IS NULL AND is_deleted = false"
    ), {"agent_id": agent_id, "code": FEATURE_CODE})
    print(f"[SEED] Bound {FEATURE_CODE} to agent_id={agent_id}")


def downgrade() -> None:
    # 不回退作用域，避免再次变成仅企业端
    pass
