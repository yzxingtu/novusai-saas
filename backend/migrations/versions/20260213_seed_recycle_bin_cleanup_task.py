"""seed recycle bin cleanup periodic task

Revision ID: 20260213_seed_rb
Revises: ef3543e8d16b
Create Date: 2026-02-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

revision: str = '20260213_seed_rb'
down_revision: Union[str, None] = 'ef3543e8d16b'
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
                '回收站自动清理',
                'app.tasks.recycle_bin.cleanup_recycle_bin',
                'cron',
                '0 3 * * *',
                NULL,
                NULL,
                '{"module_retention_days": 30, "global_retention_days": 30}',
                true,
                '每天凌晨 3 点推进模块回收站过期记录到总回收站，并清理总回收站过期记录',
                'admin_only',
                true,
                false,
                1,
                60,
                3600,
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
            WHERE task_path = 'app.tasks.recycle_bin.cleanup_recycle_bin'
        """)
    )
