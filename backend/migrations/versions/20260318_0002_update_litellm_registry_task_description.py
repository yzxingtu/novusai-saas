"""update LiteLLM registry sync task description to multi-source wording

Revision ID: 20260318_0002_litellm_desc
Revises: 20260318_0001_kb_av
Create Date: 2026-03-18

Updates periodic_tasks description to reflect LiteLLM + LLMRing multi-source sync.
将 periodic_tasks 中的任务描述更新为 LiteLLM + LLMRing 多源同步语义。
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260318_0002_litellm_desc"
down_revision: str | Sequence[str] | None = "20260318_0001_kb_av"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text("""
            UPDATE periodic_tasks
            SET description = '每天凌晨 4:00 从 LiteLLM 与 LLMRing 多源同步模型能力注册表到 Redis，用于远程模型创建时自动填充能力字段',
                updated_at = NOW()
            WHERE task_path = 'app.tasks.scheduled.sync_litellm_registry'
        """)
    )


def downgrade() -> None:
    op.execute(
        sa.text("""
            UPDATE periodic_tasks
            SET description = '每天凌晨 4:00 从 LiteLLM GitHub 仓库同步模型能力注册表到 Redis，用于远程模型创建时自动填充能力字段',
                updated_at = NOW()
            WHERE task_path = 'app.tasks.scheduled.sync_litellm_registry'
        """)
    )
