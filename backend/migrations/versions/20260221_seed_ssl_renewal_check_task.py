"""seed SSL renewal check periodic task

Revision ID: 20260221_seed_ssl
Revises: 27044bf9d269
Create Date: 2026-02-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '20260221_seed_ssl'
down_revision: Union[str, None] = '27044bf9d269'
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
                'SSL Certificate Renewal Check',
                'app.tasks.ssl_tasks.task_check_ssl_renewals',
                'cron',
                '0 3 * * *',
                NULL,
                NULL,
                NULL,
                true,
                '每天凌晨 3:00 检查即将过期的 SSL 证书，自动触发平台证书续期，通知自定义证书即将过期',
                'platform',
                true,
                false,
                1,
                60,
                1800,
                true,
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
            WHERE task_path = 'app.tasks.ssl_tasks.task_check_ssl_renewals'
        """)
    )
