"""
AI 供应商 Service / AI Provider Service

处理 AI 供应商业务逻辑
Handles AI provider business logic.
"""

import re

from sqlalchemy.exc import IntegrityError

from app.core.base_service import BaseService
from app.core.i18n import _
from app.exceptions import ConflictException, NotFoundException
from app.models.ai import AIProvider
from app.repositories.ai import AIProviderRepository
from app.schemas.ai.provider import (
    AIProviderCreate,
    AIProviderUpdate,
)


class AIProviderService(BaseService[AIProvider, AIProviderRepository]):
    """
    AI 供应商 Service / AI provider service.

    提供 AI 供应商的业务逻辑操作
    """

    model = AIProvider
    repository_class = AIProviderRepository

    async def get_by_code(
        self,
        code: str
    ) -> AIProvider | None:
        """
        根据代码获取供应商 / Get provider by code.

        Args:
            code: 供应商代码

        Returns:
            AIProvider 实例或 None
        """
        return await self.repo.get_by_code(code)

    async def get_active_providers(
        self,
        limit: int | None = None
    ) -> list[AIProvider]:
        """
        获取启用的供应商列表 / Get active providers list.

        Args:
            limit: 限制返回数量

        Returns:
            AIProvider 列表
        """
        return await self.repo.get_active_providers(limit)

    @staticmethod
    def _slugify(name: str) -> str:
        """
        将名称转为 slug 格式的代码 / Convert name to slug code.

        Examples:
            "OpenAI" -> "openai"
            "Azure OpenAI" -> "azure_openai"
            "Anthropic (Claude)" -> "anthropic_claude"
        """
        slug = name.lower().strip()
        slug = re.sub(r"[^a-z0-9]+", "_", slug)
        return slug.strip("_")[:50]

    async def _generate_unique_code(self, name: str) -> str:
        """
        根据名称生成唯一的供应商代码 / Generate unique provider code from name.

        如果 slug 已存在，追加数字后缀
        """
        base = self._slugify(name)
        if not base:
            base = "provider"

        code = base
        suffix = 1
        while await self.repo.get_by_code(code, include_deleted=True):
            code = f"{base}_{suffix}"
            suffix += 1
        return code

    async def create_provider(
        self,
        data: AIProviderCreate
    ) -> AIProvider:
        """
        创建供应商 / Create provider.

        Args:
            data: 创建请求

        Returns:
            AIProvider 实例

        Raises:
            ConflictException: 代码已存在
        """
        dump = data.model_dump()

        # 自动生成代码
        if not dump.get("code"):
            dump["code"] = await self._generate_unique_code(data.name)
        else:
            # 手动指定时仍校验唯一性
            if await self.repo.get_by_code(dump["code"]):
                raise ConflictException(message=_("ai.error.provider_code_exists"))

        # 创建供应商
        provider = AIProvider(**dump)
        self.db.add(provider)
        try:
            await self.db.flush()
        except IntegrityError:
            await self.db.rollback()
            raise ConflictException(message=_("ai.error.provider_code_exists"))
        return provider

    async def update_provider(
        self,
        id: int,
        data: AIProviderUpdate
    ) -> AIProvider:
        """
        更新供应商 / Update provider.

        Args:
            id: 供应商 ID
            data: 更新请求

        Returns:
            AIProvider 实例

        Raises:
            NotFoundException: 供应商不存在
            ConflictException: 代码冲突
        """
        provider = await self.get_by_id(id)
        if not provider:
            raise NotFoundException(message=_("ai.error.provider_not_found"))

        # 检查代码是否与其他供应商冲突
        update_data = data.model_dump(exclude_unset=True)
        if "code" in update_data and update_data["code"] != provider.code:
            existing = await self.repo.get_by_code(update_data["code"])
            if existing and existing.id != id:
                raise ConflictException(message=_("ai.error.provider_code_exists"))

        # 更新字段
        provider.update_from_dict(update_data)
        await self.db.flush()
        return provider

    async def delete_provider(
        self,
        id: int
    ) -> None:
        """
        删除供应商（软删除） / Delete provider (soft delete)

        通过 BaseService.delete() 统一处理，自动执行 __delete_deps__ 依赖检查：
        Uses BaseService.delete() for unified handling, auto-checks __delete_deps__:
        - BLOCK: AIModel 有依赖时拒绝删除 / Blocks when AIModel dependencies exist
        - CASCADE_SOFT: ProviderApiKey 跟随软删除 / Cascades soft-delete to ProviderApiKey

        删除后同步清除 Redis 健康状态键。
        Clears Redis health keys after deletion.

        Args:
            id: 供应商 ID / Provider ID

        Raises:
            NotFoundException: 供应商不存在 / Provider not found
            DependencyBlockedException: 存在 BLOCK 依赖 / BLOCK dependencies exist
        """
        result = await self.delete(id, soft=True)
        if not result:
            raise NotFoundException(message=_("ai.error.provider_not_found"))

    async def _after_delete(self, id: int) -> None:
        """
        删除后清除 Redis 健康状态键 / Clear Redis health keys after deletion
        """
        try:
            from app.ai.failover import HEALTH_HISTORY_PREFIX, HEALTH_KEY_PREFIX
            from app.core.redis import get_redis
            redis = await get_redis()
            health_key = HEALTH_KEY_PREFIX.format(provider_id=id)
            history_key = HEALTH_HISTORY_PREFIX.format(provider_id=id)
            await redis.delete(health_key, history_key)
        except Exception:
            pass

    async def toggle_status(
        self,
        id: int
    ) -> AIProvider:
        """
        切换供应商启用状态 / Toggle provider active status.

        Args:
            id: 供应商 ID

        Returns:
            AIProvider 实例

        Raises:
            NotFoundException: 供应商不存在
        """
        provider = await self.get_by_id(id)
        if not provider:
            raise NotFoundException(message=_("ai.error.provider_not_found"))

        provider.is_active = not provider.is_active
        await self.db.flush()
        return provider


__all__ = [
    "AIProviderService",
]
