"""
AI 模型 Service / AI Model Service

处理 AI 模型业务逻辑
Handles AI model business logic.
"""

from app.core.base_service import BaseService
from app.core.i18n import _
from app.exceptions import BusinessException, ConflictException, NotFoundException
from app.models.ai import AIModel
from app.repositories.ai import AIModelRepository
from app.schemas.ai.model import (
    AIModelCreate,
    AIModelUpdate,
)


class AIModelService(BaseService[AIModel, AIModelRepository]):
    """
    AI 模型 Service / AI model service.

    提供 AI 模型的业务逻辑操作
    """

    model = AIModel
    repository_class = AIModelRepository

    async def get_by_code(self, code: str) -> AIModel | None:
        """
        根据代码获取模型 / Get model by code.

        Args:
            code: 模型代码

        Returns:
            AIModel 实例或 None
        """
        return await self.repo.get_by_code(code)

    async def get_by_provider(
        self,
        provider_id: int,
        include_deleted: bool = False,
    ) -> list[AIModel]:
        """
        获取供应商的所有模型 / Get all models for a provider.

        Args:
            provider_id: 供应商 ID
            include_deleted: 是否包含已删除的记录

        Returns:
            AIModel 列表
        """
        return await self.repo.get_by_provider(
            provider_id,
            include_deleted=include_deleted,
        )

    async def create_model(self, data: AIModelCreate) -> AIModel:
        """
        创建模型 / Create model.

        Args:
            data: 创建请求

        Returns:
            AIModel 实例

        Raises:
            ConflictException: 代码已存在
        """
        if await self.repo.code_exists(data.code):
            raise ConflictException(message=_("ai.error.model_code_exists"))

        model_obj = AIModel(**data.model_dump())
        self.db.add(model_obj)
        await self.db.flush()
        return model_obj

    @staticmethod
    def _validate_fallback(model_id: int, update_data: dict) -> None:
        """校验 fallback_model_id 不可自引用 / Ensure fallback_model_id does not self-reference."""
        fallback_id = update_data.get("fallback_model_id")
        if fallback_id is not None and fallback_id == model_id:
            raise BusinessException(message=_("ai.error.fallback_self_reference"))

    async def update_model(self, id: int, data: AIModelUpdate) -> AIModel:
        """
        更新模型 / Update model.

        Args:
            id: 模型 ID
            data: 更新请求

        Returns:
            AIModel 实例

        Raises:
            NotFoundException: 模型不存在
            ConflictException: 代码冲突
        """
        model_obj = await self.get_by_id(id)
        if not model_obj:
            raise NotFoundException(message=_("ai.error.model_not_found"))

        update_data = data.model_dump(exclude_unset=True)

        # 校验 fallback 不可自引用
        self._validate_fallback(id, update_data)

        if (
            "code" in update_data
            and update_data["code"] != model_obj.code
            and await self.repo.code_exists(update_data["code"], exclude_id=id)
        ):
            raise ConflictException(message=_("ai.error.model_code_exists"))

        model_obj.update_from_dict(update_data)
        await self.db.flush()
        return model_obj

    async def delete_model(self, id: int) -> None:
        """
        删除模型（软删除） / Delete model (soft delete)

        通过 BaseService.delete() 统一处理，自动执行 __delete_deps__ 依赖检查：
        Uses BaseService.delete() for unified handling, auto-checks __delete_deps__:
        - BLOCK: Agent/KnowledgeBase 有依赖时拒绝删除 / Blocks when deps exist
        - CASCADE_SOFT: TenantQuota/TenantModelRateLimit 跟随软删除 / Cascades
        - NULLIFY: fallback_model_id/embedding_model_id 置 NULL / Nullifies FKs

        Args:
            id: 模型 ID / Model ID

        Raises:
            NotFoundException: 模型不存在 / Model not found
            DependencyBlockedException: 存在 BLOCK 依赖 / BLOCK deps exist
        """
        result = await self.delete(id, soft=True)
        if not result:
            raise NotFoundException(message=_("ai.error.model_not_found"))


    async def fetch_remote_models(self, provider_id: int) -> list:
        """
        从供应商远程拉取可用模型列表 / Fetch remote model list from provider.

        Args:
            provider_id: 供应商 ID

        Returns:
            远程模型列表

        Raises:
            NotFoundException: 供应商或 API Key 不存在
            ExternalServiceException: 远程调用失败
        """
        from app.ai.adapters import AdapterRegistry
        from app.core.logging import LogManager
        from app.exceptions import ExternalServiceException
        from app.repositories.ai import AIProviderRepository, ProviderApiKeyRepository

        _logger = LogManager.get_logger("ai")

        provider_repo = AIProviderRepository(self.db)
        provider = await provider_repo.get_by_id(provider_id)
        if not provider or not provider.is_active:
            raise NotFoundException(message=_("ai.error.provider_not_found"))

        api_key_repo = ProviderApiKeyRepository(self.db)
        api_key = await api_key_repo.get_available_key(
            provider_id=provider.id,
            tenant_id=None,
        )
        if not api_key or not api_key.is_available():
            raise NotFoundException(message=_("ai.error.no_api_key"))

        try:
            adapter = AdapterRegistry.create_adapter(
                provider_type=provider.type,
                api_key=api_key.decrypt_key(),
                base_url=provider.base_url,
                provider_config=provider.config,
            )
            remote_models = await adapter.list_models()
        except Exception as e:
            _logger.error(
                _("ai.error.fetch_remote_models_failed"),
                provider=provider.code,
                error=str(e),
            )
            raise ExternalServiceException(
                message=_("ai.error.fetch_remote_models_failed") + f": {str(e)}"
            )

        # 合并 provider.config.extra_models（某些供应商的 /v1/models 不返回 embedding 等模型）
        # 格式: {"extra_models": [{"id": "text-embedding-v3", "owned_by": "dashscope"}, ...]}
        if provider.config and isinstance(provider.config, dict):
            extra = provider.config.get("extra_models", [])
            if extra and isinstance(extra, list):
                existing_ids = {m["id"] for m in remote_models}
                for em in extra:
                    if isinstance(em, dict) and em.get("id") and em["id"] not in existing_ids:
                        remote_models.append(em)

        # Enrich with LiteLLM capabilities (graceful degradation)
        # 通过 LiteLLM 注册表附加模型能力（优雅降级）
        try:
            from app.services.ai.model_capability_lookup import enrich_remote_models
            remote_models = await enrich_remote_models(
                remote_models,
                provider_code=provider.code,
            )
        except Exception as e:
            _logger.warning("LiteLLM capability enrichment skipped: {}", str(e))

        return remote_models


__all__ = [
    "AIModelService",
]
