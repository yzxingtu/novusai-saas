"""localize router agent and default_chat to Chinese

Updates:
1. Router agent: name + description → Chinese
2. default_chat assignment: feature_name + description → Chinese

Revision ID: 20260307_router_zh
Revises: 20260307_retired_runtime_b
Create Date: 2026-03-07 16:30:00.000000+00:00

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "20260307_router_zh"
down_revision: str | Sequence[str] | None = "20260307_retired_runtime_b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# ---------------------------------------------------------------------------
# Old (English) → New (Chinese)
# ---------------------------------------------------------------------------

OLD_ROUTER_NAME = "system_router_agent"
NEW_ROUTER_NAME = "系统路由智能体"
NEW_ROUTER_DESC = "系统路由智能体 — 分析用户消息并自动分配到最合适的智能体"

OLD_CHAT_FEATURE_NAME = "Default Chat Agent"
NEW_CHAT_FEATURE_NAME = "默认聊天智能体"
NEW_CHAT_DESC = "默认对话智能体，当路由器无法确定最佳智能体或未配置路由器时使用的后备智能体。"


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Update Router agent name + description
    result = conn.execute(text(
        "UPDATE agents "
        "SET name = :new_name, description = :new_desc, updated_at = NOW() "
        "WHERE name = :old_name AND owner_tenant_id IS NULL AND is_system = true AND is_deleted = false"
    ), {
        "new_name": NEW_ROUTER_NAME,
        "new_desc": NEW_ROUTER_DESC,
        "old_name": OLD_ROUTER_NAME,
    })
    print(f"[SEED] Updated Router agent name: {OLD_ROUTER_NAME} → {NEW_ROUTER_NAME} ({result.rowcount} rows)")

    # 2. Update default_chat assignment feature_name + description
    result = conn.execute(text(
        "UPDATE system_agent_assignments "
        "SET feature_name = :new_name, description = :new_desc, updated_at = NOW() "
        "WHERE feature_code = 'default_chat' AND tenant_id IS NULL AND is_deleted = false"
    ), {
        "new_name": NEW_CHAT_FEATURE_NAME,
        "new_desc": NEW_CHAT_DESC,
    })
    print(f"[SEED] Updated default_chat feature_name → {NEW_CHAT_FEATURE_NAME} ({result.rowcount} rows)")


def downgrade() -> None:
    conn = op.get_bind()

    # Revert Router agent
    conn.execute(text(
        "UPDATE agents "
        "SET name = :old_name, "
        "    description = 'System router agent — analyzes user messages and routes to the best agent', "
        "    updated_at = NOW() "
        "WHERE name = :new_name AND owner_tenant_id IS NULL AND is_system = true AND is_deleted = false"
    ), {
        "old_name": OLD_ROUTER_NAME,
        "new_name": NEW_ROUTER_NAME,
    })

    # Revert default_chat
    conn.execute(text(
        "UPDATE system_agent_assignments "
        "SET feature_name = :old_name, "
        "    description = 'Default conversational agent used as fallback when Router cannot determine "
        "the best agent or when no Router agent is configured.', "
        "    updated_at = NOW() "
        "WHERE feature_code = 'default_chat' AND tenant_id IS NULL AND is_deleted = false"
    ), {
        "old_name": OLD_CHAT_FEATURE_NAME,
    })

    print("[SEED] Reverted Router agent + default_chat to English.")
