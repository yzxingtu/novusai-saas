"""seed LiteLLM model registry sync periodic task

Revision ID: 20260314_litellm_sync
Revises: 20260314_display_imgs_public
Create Date: 2026-03-14
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260314_litellm_sync"
down_revision: str | None = "20260314_display_imgs_public"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(sa.text("""
        INSERT INTO periodic_tasks (
            name, task_path, schedule_type, cron_expression,
            interval_seconds, args, kwargs, is_active,
            description, scope, is_locked, is_editable,
            max_retries, retry_delay, timeout,
            notify_on_failure, created_at, updated_at, is_deleted
        ) VALUES (
            'LiteLLM 模型能力注册表同步',
            'app.tasks.scheduled.sync_litellm_registry',
            'cron',
            '0 4 * * *',
            NULL,
            NULL,
            NULL,
            true,
            '每天凌晨 4:00 从 LiteLLM GitHub 仓库同步模型能力注册表到 Redis，用于远程模型创建时自动填充能力字段',
            'platform',
            true,
            false,
            2,
            120,
            60,
            false,
            NOW(),
            NOW(),
            false
        )
        ON CONFLICT DO NOTHING
    """))


def downgrade() -> None:
    op.execute(sa.text(
        "DELETE FROM periodic_tasks WHERE task_path = "
        "'app.tasks.scheduled.sync_litellm_registry'"
    ))
