"""seed all periodic tasks into database

Move all hardcoded beat_schedule entries into periodic_tasks table
so they can be managed via admin UI.

Revision ID: 20260221_seed_all
Revises: 20260221_seed_ssl
Create Date: 2026-02-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '20260221_seed_all'
down_revision: Union[str, None] = '20260221_seed_ssl'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# All tasks that should exist in periodic_tasks table
# (task_path used as idempotency key via ON CONFLICT)
TASKS = [
    {
        "name": "系统健康检查",
        "task_path": "app.tasks.scheduled.system_health_check",
        "schedule_type": "interval",
        "cron_expression": None,
        "interval_seconds": 300,
        "kwargs": None,
        "description": "每 5 分钟检查系统健康状态（数据库、Redis 连接）",
        "is_locked": True,
        "max_retries": 1,
        "timeout": 60,
    },
    {
        "name": "清理过期验证码",
        "task_path": "app.tasks.scheduled.clean_expired_captchas",
        "schedule_type": "interval",
        "cron_expression": None,
        "interval_seconds": 3600,
        "kwargs": None,
        "description": "每小时清理过期的验证码缓存",
        "is_locked": True,
        "max_retries": 1,
        "timeout": 300,
    },
    {
        "name": "清理过期任务日志",
        "task_path": "app.tasks.scheduled.clean_expired_task_logs",
        "schedule_type": "cron",
        "cron_expression": "0 4 * * *",
        "interval_seconds": None,
        "kwargs": None,
        "description": "每天凌晨 4:00 清理超过 30 天的任务日志",
        "is_locked": True,
        "max_retries": 1,
        "timeout": 1800,
    },
    {
        "name": "AI 供应商健康检查",
        "task_path": "app.tasks.ai_health_check.ai_provider_health_check",
        "schedule_type": "interval",
        "cron_expression": None,
        "interval_seconds": 300,
        "kwargs": None,
        "description": "每 5 分钟检查所有启用的 AI 供应商可用性，写入 Redis 供故障转移",
        "is_locked": True,
        "max_retries": 1,
        "timeout": 120,
    },
    {
        "name": "重置智能体每日配额",
        "task_path": "app.tasks.scheduled.reset_agent_daily_quotas",
        "schedule_type": "cron",
        "cron_expression": "0 0 * * *",
        "interval_seconds": None,
        "kwargs": None,
        "description": "每天零点重置智能体每日配额（清理无 TTL 的 Redis key）",
        "is_locked": True,
        "max_retries": 1,
        "timeout": 300,
    },
    {
        "name": "重置智能体每日统计",
        "task_path": "app.tasks.scheduled.reset_agent_daily_stats",
        "schedule_type": "cron",
        "cron_expression": "0 0 * * *",
        "interval_seconds": None,
        "kwargs": None,
        "description": "每天零点重置智能体每日统计（Redis 当日计数归零）",
        "is_locked": True,
        "max_retries": 1,
        "timeout": 300,
    },
    {
        "name": "清理分片上传",
        "task_path": "app.tasks.upload_cleanup.cleanup_chunk_uploads",
        "schedule_type": "interval",
        "cron_expression": None,
        "interval_seconds": 21600,
        "kwargs": '{"retention_hours": 24}',
        "description": "每 6 小时清理超过 24 小时的分片上传临时文件",
        "is_locked": True,
        "max_retries": 1,
        "timeout": 600,
    },
    {
        "name": "清理过期通知",
        "task_path": "app.tasks.notification_cleanup.cleanup_expired_notifications",
        "schedule_type": "cron",
        "cron_expression": "0 3 * * *",
        "interval_seconds": None,
        "kwargs": None,
        "description": "每天凌晨 3:00 根据 notification_retention_days 配置清理过期通知（物理删除）",
        "is_locked": True,
        "max_retries": 1,
        "timeout": 1800,
    },
]


def upgrade() -> None:
    for t in TASKS:
        kwargs_val = f"'{t['kwargs']}'" if t["kwargs"] else "NULL"
        cron_val = f"'{t['cron_expression']}'" if t["cron_expression"] else "NULL"
        interval_val = t["interval_seconds"] if t["interval_seconds"] else "NULL"

        op.execute(
            sa.text(f"""
                INSERT INTO periodic_tasks (
                    name, task_path, schedule_type, cron_expression,
                    interval_seconds, args, kwargs, is_active,
                    description, scope, is_locked, is_editable,
                    max_retries, retry_delay, timeout,
                    notify_on_failure, created_at, updated_at, is_deleted
                ) VALUES (
                    '{t["name"]}',
                    '{t["task_path"]}',
                    '{t["schedule_type"]}',
                    {cron_val},
                    {interval_val},
                    NULL,
                    {kwargs_val},
                    true,
                    '{t["description"]}',
                    'platform',
                    {str(t["is_locked"]).lower()},
                    false,
                    {t["max_retries"]},
                    60,
                    {t["timeout"]},
                    false,
                    NOW(),
                    NOW(),
                    false
                )
                ON CONFLICT DO NOTHING
            """)
        )


def downgrade() -> None:
    task_paths = [t["task_path"] for t in TASKS]
    paths_str = ", ".join(f"'{p}'" for p in task_paths)
    op.execute(
        sa.text(f"""
            DELETE FROM periodic_tasks
            WHERE task_path IN ({paths_str})
        """)
    )
