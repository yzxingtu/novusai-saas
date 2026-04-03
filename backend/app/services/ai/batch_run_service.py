"""
批量运行 Service / Batch Run Service
"""

from app.core.base_service import TenantService
from app.core.logging import LogManager
from app.models.ai.batch_run import BatchRun
from app.repositories.ai.batch_run_repository import BatchRunRepository

logger = LogManager.get_logger("ai")


class BatchRunService(TenantService[BatchRun, BatchRunRepository]):
    """
    企业端批量运行 Service / Tenant batch run service.

    提供批量运行查询、取消等操作
    """

    model = BatchRun
    repository_class = BatchRunRepository

    async def get_agent_batch_run(self, agent_id: int, run_id: int) -> BatchRun | None:
        """
        获取指定智能体的批量运行记录 / Get batch run for agent.

        Args:
            agent_id: 智能体 ID
            run_id: 批量运行 ID

        Returns:
            BatchRun 实例（归属 agent_id 时），否则 None
        """
        batch_run = await self.repo.get_by_id(run_id)
        if not batch_run or batch_run.agent_id != agent_id:
            return None
        return batch_run

    async def cancel_batch_run(self, agent_id: int, run_id: int) -> BatchRun:
        """
        取消批量运行 / Cancel batch run.

        Args:
            agent_id: 智能体 ID
            run_id: 批量运行 ID

        Returns:
            更新后的 BatchRun

        Raises:
            NotFoundException: 批量运行不存在或不属于该智能体
            BusinessException: 当前状态不可取消
        """
        from app.core.i18n import _
        from app.enums.agent import BatchRunStatusEnum
        from app.exceptions import BusinessException, NotFoundException

        batch_run = await self.get_agent_batch_run(agent_id, run_id)
        if not batch_run:
            raise NotFoundException(
                message=_("agent.error.batch_run_not_found"),
            )

        if batch_run.status not in (
            BatchRunStatusEnum.PENDING.value,
            BatchRunStatusEnum.RUNNING.value,
        ):
            raise BusinessException(
                message=_("agent.error.batch_not_cancellable"),
            )

        batch_run.status = BatchRunStatusEnum.CANCELLED.value

        # 尝试撤销 Celery 任务
        if batch_run.celery_task_id:
            try:
                from app.celery_app import celery_app

                celery_app.control.revoke(
                    batch_run.celery_task_id,
                    terminate=False,
                )
                logger.info(
                    "Celery task {} revoked for batch_run {}",
                    batch_run.celery_task_id,
                    run_id,
                )
            except Exception as e:
                logger.warning(
                    "Failed to revoke celery task {}: {}",
                    batch_run.celery_task_id,
                    str(e),
                )

        return batch_run


__all__ = ["BatchRunService"]
