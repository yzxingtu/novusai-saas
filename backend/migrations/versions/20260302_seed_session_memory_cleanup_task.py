"""seed session memory cleanup periodic task

Revision ID: 20260302_sess_mem_cleanup
Revises: 20260301_plugin_trial
Create Date: 2026-03-02
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260302_sess_mem_cleanup"
down_revision: str | None = "20260301_plugin_trial"
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
            '会话记忆兜底清理',
            'app.tasks.scheduled.clean_expired_session_memories',
            'cron',
            '30 3 * * *',
            NULL,
            NULL,
            NULL,
            true,
            '每天凌晨 3:30 清理无 TTL 的会话记忆 Redis 残留 key（mem:sess:*）',
            'platform',
            true,
            false,
            1,
            60,
            300,
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
        "'app.tasks.scheduled.clean_expired_session_memories'"
    ))
