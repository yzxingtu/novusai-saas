"""seed notification cleanup periodic task

Revision ID: 20260222_seed_notif
Revises: 6b4fe69b2efc
Create Date: 2026-02-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '20260222_seed_notif'
down_revision: Union[str, None] = '6b4fe69b2efc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text("""
            INSERT INTO periodic_tasks (
                name, task_path, schedule_type, cron_expression,
                interval_seconds, args, kwargs, is_active,
                description, scope, is_locked, is_editable,
                max_retries, retry_delay, timeout,
                notify_on_failure, created_at, updated_at, is_deleted
            ) VALUES (
                '清理过期通知',
                'app.tasks.notification_cleanup.cleanup_expired_notifications',
                'cron',
                '0 3 * * *',
                NULL,
                NULL,
                NULL,
                true,
                '每天凌晨 3:00 根据 notification_retention_days 配置清理过期通知（物理删除）',
                'platform',
                true,
                false,
                1,
                60,
                1800,
                false,
                NOW(),
                NOW(),
                false
            )
            ON CONFLICT DO NOTHING
        """)
    )


def downgrade() -> None:
    op.execute(
        sa.text("""
            DELETE FROM periodic_tasks
            WHERE task_path = 'app.tasks.notification_cleanup.cleanup_expired_notifications'
        """)
    )
