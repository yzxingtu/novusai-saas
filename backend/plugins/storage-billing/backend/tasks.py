"""Scheduled tasks for storage billing plugin. / 对象存储对账计费插件定时任务。"""

from __future__ import annotations

from app.core.database import async_session_factory
from app.core.logging import get_logger
from app.plugins.host_read_facade import HostReadFacade

from .services.reconciliation_service import StorageBillingReconciliationService

logger = get_logger(__name__)


async def run_daily_reconciliation() -> dict:
    """Daily reconciliation task. / 每日对账任务。"""
    async with async_session_factory() as db:
        service = StorageBillingReconciliationService(
            db,
            host_read=HostReadFacade(db),
        )
        result = await service.run_daily_reconciliation()
        await db.commit()
        logger.info("Storage billing daily reconciliation finished: {}", result.get("run", {}))
        return result


async def run_qiniu_monthly_settlement() -> dict:
    """Qiniu monthly settlement task. / 七牛云月结账单拉取任务。"""
    async with async_session_factory() as db:
        service = StorageBillingReconciliationService(
            db,
            host_read=HostReadFacade(db),
        )
        result = await service.run_qiniu_monthly_settlement()
        await db.commit()
        logger.info(
            "Storage billing Qiniu monthly settlement finished: {}",
            result.get("run", {}),
        )
        return result
