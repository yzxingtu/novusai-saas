"""seed plugin trial expiration check task

Bug 27 fix: the legacy trial-expiration task was defined but never called.
Add a daily scheduled task to auto-disable expired trial licenses.

Revision ID: 20260301_plugin_trial
Revises: 20260221_seed_all
Create Date: 2026-03-01
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '20260301_plugin_trial'
down_revision: str | None = '20260221_seed_all'
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
            '插件试用期检查',
            'app.tasks.scheduled.check_plugin_trial_expirations',
            'cron',
            '0 2 * * *',
            NULL,
            NULL,
            NULL,
            true,
            '每天凌晨 2:00 检查插件试用期，自动禁用已到期的插件并发出预警提醒',
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
        "'app.tasks.scheduled.check_plugin_trial_expirations'"
    ))
