"""
批量运行 Repository
"""

from typing import List

from sqlalchemy import select, and_, update

from app.core.base_repository import TenantRepository
from app.enums.agent import BatchRunStatusEnum
from app.models.ai.batch_run import BatchRun


class BatchRunRepository(TenantRepository[BatchRun]):
    """
    租户级批量运行 Repository

    提供按智能体查询、更新进度等方法
    """

    model = BatchRun

    async def get_by_agent(
        self,
        agent_id: int,
        skip: int = 0,
        limit: int = 20,
    ) -> List[BatchRun]:
        """
        获取智能体的批量运行记录

        Args:
            agent_id: 智能体 ID
            skip: 跳过数量
            limit: 返回数量

        Returns:
            BatchRun 列表
        """
        stmt = (
            select(BatchRun)
            .where(
                and_(
                    BatchRun.tenant_id == self.tenant_id,
                    BatchRun.agent_id == agent_id,
                    BatchRun.is_deleted == False,
                )
            )
            .order_by(BatchRun.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update_progress(
        self,
        batch_run_id: int,
        completed_items: int,
        failed_items: int,
        status: str | None = None,
    ) -> None:
        """
        更新批量运行进度

        Args:
            batch_run_id: 批量运行 ID
            completed_items: 已完成数量
            failed_items: 失败数量
            status: 状态（可选）
        """
        values = {
            "completed_items": completed_items,
            "failed_items": failed_items,
        }
        if status:
            values["status"] = status

        stmt = (
            update(BatchRun)
            .where(
                and_(
                    BatchRun.id == batch_run_id,
                    BatchRun.tenant_id == self.tenant_id,
                )
            )
            .values(**values)
        )
        await self.db.execute(stmt)
        await self.db.flush()

    async def get_active_runs(self, agent_id: int) -> List[BatchRun]:
        """获取进行中的批量运行"""
        stmt = (
            select(BatchRun)
            .where(
                and_(
                    BatchRun.tenant_id == self.tenant_id,
                    BatchRun.agent_id == agent_id,
                    BatchRun.status.in_([
                        BatchRunStatusEnum.PENDING.value,
                        BatchRunStatusEnum.RUNNING.value,
                    ]),
                    BatchRun.is_deleted == False,
                )
            )
            .order_by(BatchRun.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


__all__ = ["BatchRunRepository"]
