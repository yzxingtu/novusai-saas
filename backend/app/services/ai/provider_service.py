"""
AI 供应商 Service

处理 AI 供应商业务逻辑
"""

import re

from app.core.base_service import BaseService
from app.core.i18n import _
from app.exceptions import NotFoundException, ConflictException
from app.repositories.ai import AIProviderRepository
from app.schemas.ai.provider import (
    AIProviderCreate,
    AIProviderUpdate,
)
from app.models.ai import AIProvider


class AIProviderService(BaseService[AIProvider, AIProviderRepository]):
    """
    AI 供应商 Service

    提供 AI 供应商的业务逻辑操作
    """

    model = AIProvider
    repository_class = AIProviderRepository

    async def get_by_code(
        self,
        code: str
    ) -> AIProvider | None:
        """
        根据代码获取供应商

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
        获取启用的供应商列表

        Args:
            limit: 限制返回数量

        Returns:
            AIProvider 列表
        """
        return await self.repo.get_active_providers(limit)

    @staticmethod
    def _slugify(name: str) -> str:
        """
        将名称转为 slug 格式的代码

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
        根据名称生成唯一的供应商代码

        如果 slug 已存在，追加数字后缀
        """
        base = self._slugify(name)
        if not base:
            base = "provider"

        code = base
        suffix = 1
        while await self.repo.get_by_code(code):
            code = f"{base}_{suffix}"
            suffix += 1
        return code

    async def create_provider(
        self,
        data: AIProviderCreate
    ) -> AIProvider:
        """
        创建供应商

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
        await self.db.flush()
        return provider

    async def update_provider(
        self,
        id: int,
        data: AIProviderUpdate
    ) -> AIProvider:
        """
        更新供应商

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
        删除供应商（软删除）

        Args:
            id: 供应商 ID

        Raises:
            NotFoundException: 供应商不存在
        """
        provider = await self.get_by_id(id)
        if not provider:
            raise NotFoundException(message=_("ai.error.provider_not_found"))

        provider.soft_delete()
        await self.db.flush()

    async def toggle_status(
        self,
        id: int
    ) -> AIProvider:
        """
        切换供应商启用状态

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
