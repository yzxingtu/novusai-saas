"""
AI 操作审计日志 Service / AI Action Log Service

提供审计日志的查询和统计功能（只读 Service）
Provides audit log query and statistics functions (read-only service).
"""

from app.core.base_service import TenantService
from app.models.ai.action_log import AIActionLog
from app.repositories.ai.action_log_repository import AIActionLogRepository


class AIActionLogService(TenantService[AIActionLog, AIActionLogRepository]):
    """
    AI 操作审计日志 Service

    只读服务，不提供 create/update/delete
    """

    model = AIActionLog
    repository_class = AIActionLogRepository

    async def get_stats(self) -> dict:
        """获取审计统计信息"""
        return await self.repo.get_stats()

    async def get_type_distribution(self) -> list[dict]:
        """获取操作类型分布"""
        return await self.repo.get_type_distribution()


__all__ = ["AIActionLogService"]
