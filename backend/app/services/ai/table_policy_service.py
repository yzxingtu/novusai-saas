"""
AI 表策略 Service / AI Table Policy Service

提供 AI 表策略的业务逻辑（平台级管理）
Provides AI table policy business logic (platform-level management).
"""

from app.core.base_service import BaseService
from app.core.i18n import _
from app.exceptions import NotFoundException
from app.models.ai.table_policy import AITablePolicy
from app.repositories.ai.table_policy_repository import AITablePolicyRepository


class AITablePolicyService(BaseService[AITablePolicy, AITablePolicyRepository]):
    """
    AI 表策略 Service

    提供策略的查询、更新功能。
    策略由 sync 服务自动创建，管理员只做编辑。
    """

    model = AITablePolicy
    repository_class = AITablePolicyRepository

    async def get_or_raise(self, policy_id: int) -> AITablePolicy:
        """获取策略或抛出 404"""
        policy = await self.get_by_id(policy_id)
        if not policy:
            raise NotFoundException(message=_("ai_table_policy.not_found"))
        return policy

    async def get_table_columns(self, policy_id: int) -> list[dict]:
        """获取策略对应表的列信息"""
        policy = await self.get_or_raise(policy_id)
        return await self.repo.get_table_columns(policy.table_name)


__all__ = ["AITablePolicyService"]
