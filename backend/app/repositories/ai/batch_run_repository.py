"""
批量运行 Repository / Batch Run Repository
"""

from sqlalchemy import and_, select, update

from app.core.base_repository import TenantRepository
from app.enums.agent import BatchRunStatusEnum
from app.models.ai.batch_run import BatchRun


class BatchRunRepository(TenantRepository[BatchRun]):
    """
    企业级批量运行 Repository / Tenant batch run repository.

    提供按智能体查询、更新进度等方法
    """

    model = BatchRun

    @staticmethod
    def _sanitize_create_data(data: dict) -> dict:
        payload = dict(data)
        if payload.get("created_by") is None:
            payload.pop("created_by", None)
        return payload

    async def create(self, data: dict) -> BatchRun:
        return await super().create(self._sanitize_create_data(data))

    async def create_many(self, data_list: list[dict]) -> list[BatchRun]:
        return await super().create_many(
            [self._sanitize_create_data(data) for data in data_list]
        )

    async def get_by_agent(
        self,
        agent_id: int,
        skip: int = 0,
        limit: int = 20,
    ) -> list[BatchRun]:
        """
        获取智能体的批量运行记录 / Get batch run records for agent.

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
                    BatchRun.is_deleted.is_(False),
                )
            )
            .order_by(BatchRun.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        stmt = self._apply_data_permission_if_needed(stmt)
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
        更新批量运行进度 / Update batch run progress.

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
        permission_condition = self._build_data_permission_condition()
        if permission_condition is not None:
            stmt = stmt.where(permission_condition)
        await self.db.execute(stmt)
        await self.db.flush()

    async def get_active_runs(self, agent_id: int) -> list[BatchRun]:
        """获取进行中的批量运行 / Get in-progress batch runs for the agent."""
        stmt = (
            select(BatchRun)
            .where(
                and_(
                    BatchRun.tenant_id == self.tenant_id,
                    BatchRun.agent_id == agent_id,
                    BatchRun.status.in_(
                        [
                            BatchRunStatusEnum.PENDING.value,
                            BatchRunStatusEnum.RUNNING.value,
                        ]
                    ),
                    BatchRun.is_deleted.is_(False),
                )
            )
            .order_by(BatchRun.created_at.desc())
        )
        stmt = self._apply_data_permission_if_needed(stmt)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


__all__ = ["BatchRunRepository"]
