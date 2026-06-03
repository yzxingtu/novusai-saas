"""update system.ai_writing assignment description

Revision ID: 20260315_ai_desc
Revises: 20260314_ai_wr
Create Date: 2026-03-15
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "20260315_ai_desc"
down_revision: str | Sequence[str] | None = "20260314_ai_wr"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FEATURE_CODE = "system.ai_writing"
NEW_FEATURE_NAME = "NovusDoc 文档写作助手"
NEW_DESCRIPTION = (
    "NovusDoc 文档写作助手 — 嵌入在富文本编辑器中的 AI 写作智能体。"
    "支持续写、优化、校对、翻译、摘要、扩写、重写等文档操作。"
    "自动匹配用户文档的风格、语气和语言。"
    "通过功能分配页面绑定具体智能体后生效。"
    "Supports: continue, optimize, proofread, translate, summarize, expand, rewrite, custom."
)
OLD_FEATURE_NAME = "AI Writing Assistant"
OLD_DESCRIPTION = (
    "Platform-level AI writing agent for rich text editors. "
    "Supports: continue, optimize, proofread, translate, summarize, expand, rewrite, custom, chat."
)


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(text(
        "UPDATE system_agent_assignments "
        "SET feature_name = :name, description = :desc, updated_at = NOW() "
        "WHERE feature_code = :code AND tenant_id IS NULL AND is_deleted = false"
    ), {"code": FEATURE_CODE, "name": NEW_FEATURE_NAME, "desc": NEW_DESCRIPTION})
    print(f"[SEED] Updated {FEATURE_CODE} description")


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text(
        "UPDATE system_agent_assignments "
        "SET feature_name = :name, description = :desc, updated_at = NOW() "
        "WHERE feature_code = :code AND tenant_id IS NULL AND is_deleted = false"
    ), {"code": FEATURE_CODE, "name": OLD_FEATURE_NAME, "desc": OLD_DESCRIPTION})
    print(f"[SEED] Reverted {FEATURE_CODE} description")
