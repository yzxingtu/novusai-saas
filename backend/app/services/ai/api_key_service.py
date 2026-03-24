"""
AI 供应商密钥 Service / AI API Key Service

处理 AI API Key 业务逻辑
Handles AI API key business logic.
"""

from app.core.base_service import BaseService
from app.core.i18n import _
from app.enums.common import ResourceScopeEnum
from app.exceptions import NotFoundException, ValidationException
from app.models.ai import ProviderApiKey
from app.repositories.ai import ProviderApiKeyRepository
from app.repositories.system.resource_tenant_assignment_repository import (
    ResourceTenantAssignmentRepository,
)
from app.schemas.ai.api_key import (
    ProviderApiKeyCreate,
    ProviderApiKeyUpdate,
)


class ProviderApiKeyService(BaseService[ProviderApiKey, ProviderApiKeyRepository]):
    """
    AI API Key Service / AI API key service.

    提供 AI API Key 的业务逻辑操作
    """

    model = ProviderApiKey
    repository_class = ProviderApiKeyRepository

    async def create_key(self, data: ProviderApiKeyCreate) -> ProviderApiKey:
        """
        创建 API Key / Create API key.

        Args:
            data: 创建请求

        Returns:
            ProviderApiKey 实例
        """
        # 从 schema 中提取数据，排除 api_key 字段（模型中用 encrypted_key 存储）
        create_data = data.model_dump(exclude={"api_key"})
        owner_tid = create_data.pop("tenant_id", None)
        scope = str(create_data.get("scope") or "")

        if scope == ResourceScopeEnum.ALL_TENANTS.value:
            if owner_tid is None:
                create_data["scope"] = ResourceScopeEnum.GLOBAL_SHARED.value
            else:
                create_data["scope"] = ResourceScopeEnum.SELECTED_TENANTS.value
            scope = create_data["scope"]

        if scope == ResourceScopeEnum.SELECTED_TENANTS.value and owner_tid is None:
            raise ValidationException(
                message=_("ai.error.api_key_owner_required"),
            )

        if scope in (
            ResourceScopeEnum.ADMIN_ONLY.value,
            ResourceScopeEnum.GLOBAL_SHARED.value,
        ) and owner_tid is not None:
            raise ValidationException(
                message=_("ai.error.api_key_owner_forbidden"),
            )

        create_data["owner_tenant_id"] = owner_tid

        key = ProviderApiKey(**create_data)
        key.encrypt_key(data.api_key)

        self.db.add(key)
        await self.db.flush()

        if (
            key.scope == ResourceScopeEnum.SELECTED_TENANTS.value
            and key.owner_tenant_id is not None
        ):
            rta_repo = ResourceTenantAssignmentRepository(self.db)
            await rta_repo.sync_assignments(
                "ai_api_key",
                key.id,
                [key.owner_tenant_id],
            )

        return key

    async def update_key(self, id: int, data: ProviderApiKeyUpdate) -> ProviderApiKey:
        """
        更新 API Key / Update API key.

        Args:
            id: API Key ID
            data: 更新请求

        Returns:
            ProviderApiKey 实例

        Raises:
            NotFoundException: API Key 不存在
        """
        key = await self.get_by_id(id)
        if not key:
            raise NotFoundException(message=_("ai.error.api_key_not_found"))

        # 如果提供了新的 key，需要重新加密
        if data.key is not None:
            key.encrypt_key(data.key)

        # 更新其他字段 / Update other fields
        update_data = data.model_dump(exclude_unset=True, exclude={"key"})
        key.update_from_dict(update_data)
        await self.db.flush()
        return key

    async def toggle_status(self, id: int) -> ProviderApiKey:
        """
        切换 API Key 启用状态 / Toggle API Key active status.

        Args:
            id: API Key ID

        Returns:
            ProviderApiKey 实例

        Raises:
            NotFoundException: API Key 不存在
        """
        key = await self.get_by_id(id)
        if not key:
            raise NotFoundException(message=_("ai.error.api_key_not_found"))

        key.is_active = not key.is_active
        await self.db.flush()
        return key

    async def increment_usage(self, key_id: int, increment: int = 1) -> None:
        """
        增加 API Key 使用次数 / Increment API Key usage count.

        Args:
            key_id: API Key ID
            increment: 增量
        """
        await self.repo.update_usage_count(key_id, increment)

    async def get_keys_by_provider(
        self,
        provider_id: int | None = None,
        tenant_id: int | None = None,
    ) -> list[ProviderApiKey]:
        """
        获取供应商的 API Key 列表 / Get API keys by provider.

        Args:
            provider_id: 供应商 ID（None 则不限）
            tenant_id: 企业 ID（None 则不限）

        Returns:
            ProviderApiKey 列表
        """
        return await self.repo.get_keys_by_provider(
            provider_id=provider_id,
            tenant_id=tenant_id,
        )

    async def get_available_key(
        self,
        provider_id: int,
        tenant_id: int | None = None,
    ) -> ProviderApiKey | None:
        """
        获取可用的 API Key / Get available API Key.

        Args:
            provider_id: 供应商 ID
            tenant_id: 企业 ID

        Returns:
            ProviderApiKey 或 None
        """
        return await self.repo.get_available_key(
            provider_id=provider_id,
            tenant_id=tenant_id,
        )


__all__ = [
    "ProviderApiKeyService",
]
