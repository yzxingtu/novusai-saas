"""
Notification auto-cleanup scheduled task / 通知自动清理定时任务

Cleans up expired notifications (physical delete) based on platform config notification_retention_days.
根据平台配置 notification_retention_days 清理过期通知（物理删除）。
Registered to the scheduling system via the periodic_tasks page.
通过 periodic_tasks 页面注册到调度系统。
"""

import contextlib
import time
from datetime import timedelta

from app.core.base_model import utc_now
from app.core.database import sync_session_factory
from app.core.logging import LogManager
from app.tasks.base import BaseTask, register_task

logger = LogManager.get_logger("task")


@register_task(
    queue="scheduled",
    description="Clean up expired notifications (based on notification_retention_days config) / 清理过期通知（根据 notification_retention_days 配置）",
    max_retries=1,
)
def cleanup_expired_notifications(self: BaseTask) -> dict:
    """
    清理超过保留天数的通知记录（物理删除）/ Clean up notification records exceeding retention days (physical delete).

    Reads platform config notification_retention_days,
    deletes notifications with created_at earlier than (now - retention_days).
    读取平台配置 notification_retention_days，
    删除 created_at 早于 (now - retention_days) 的通知。
    """
    start = time.time()

    from sqlalchemy import delete

    from app.models.common.notification import Notification

    session = sync_session_factory()
    try:
        # Read config (sync environment, query DB directly) / 读取配置（同步环境，直接查 DB）
        from sqlalchemy import select

        from app.configs.service import PLATFORM_TENANT_ID
        from app.models.system.config import SystemConfig, SystemConfigValue

        # Query notification_retention_days config value / 查询 notification_retention_days 配置值
        retention_days = 90  # Default value / 默认值
        config_q = (
            select(SystemConfigValue.value)
            .join(SystemConfig, SystemConfig.id == SystemConfigValue.config_id)
            .where(
                SystemConfig.key == "notification_retention_days",
                SystemConfigValue.tenant_id == PLATFORM_TENANT_ID,
            )
        )
        result = session.execute(config_q)
        row = result.scalar_one_or_none()
        if row is not None:
            with contextlib.suppress(ValueError, TypeError):
                retention_days = int(row)

        if retention_days <= 0:
            logger.info("Notification cleanup skipped: retention_days=%d", retention_days)
            return {"deleted": 0, "retention_days": retention_days, "skipped": True}

        # Calculate cutoff time / 计算截止时间
        cutoff = utc_now() - timedelta(days=retention_days)

        # Physically delete expired notifications / 物理删除过期通知
        delete_q = delete(Notification).where(
            Notification.created_at < cutoff,
        )
        result = session.execute(delete_q)
        deleted = result.rowcount
        session.commit()

        elapsed = round(time.time() - start, 2)
        logger.info(
            "Notification cleanup completed: deleted=%d retention_days=%d cutoff=%s elapsed=%ss",
            deleted, retention_days, cutoff.isoformat(), elapsed,
        )
        return {
            "deleted": deleted,
            "retention_days": retention_days,
            "cutoff": cutoff.isoformat(),
            "elapsed": elapsed,
        }
    except Exception as e:
        session.rollback()
        logger.error("Notification cleanup failed: %s", str(e))
        raise
    finally:
        session.close()


__all__ = ["cleanup_expired_notifications"]
