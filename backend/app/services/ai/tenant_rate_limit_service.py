"""
租户 AI 模型速率限制配置 Service
"""

from typing import Optional

from app.repositories.ai.tenant_rate_limit_repository import TenantModelRateLimitRepository
from app.models.ai import TenantModelRateLimit, AIModel
from app.core.base_service import TenantService
from app.core.i18n import _
from app.core.logging import LogManager


logger = LogManager.get_logger("ai.rate_limit_service")


class TenantRateLimitService(TenantService[TenantModelRateLimit, TenantModelRateLimitRepository]):
    """
    租户 AI 模型速率限制配置 Service
    """

    model = TenantModelRateLimit
    repository_class = TenantModelRateLimitRepository

    async def get_rate_limit(
        self,
        model_id: int
    ) -> Optional[TenantModelRateLimit]:
        """
        获取租户对指定模型的速率限制配置

        Args:
            model_id: 模型 ID

        Returns:
            TenantModelRateLimit 实例
        """
        return await self.repo.get_by_tenant_and_model(self.tenant_id, model_id)

    async def get_effective_rate_limits(
        self,
        model_id: int
    ) -> dict:
        """
        获取有效的速率限制（优先使用租户配置，否则使用模型默认值）

        Args:
            model_id: 模型 ID

        Returns:
            包含 rpm_limit 和 tpm_limit 的字典
        """
        # 先查租户配置
        tenant_limit = await self.get_rate_limit(model_id)

        if tenant_limit and tenant_limit.is_active:
            return {
                "rpm_limit": tenant_limit.rpm_limit,
                "tpm_limit": tenant_limit.tpm_limit,
                "source": "tenant",
            }

        # 如果租户没配置，查模型默认值
        from app.repositories.ai.model_repository import AIModelRepository
        model_repo = AIModelRepository(self.db)
        model = await model_repo.get_by_id(model_id)

        if model:
            return {
                "rpm_limit": model.rpm_limit,
                "tpm_limit": model.tpm_limit,
                "source": "model",
            }

        # 都没有配置
        return {
            "rpm_limit": None,
            "tpm_limit": None,
            "source": "none",
        }

    async def get_active_limits(
        self,
        model_id: Optional[int] = None,
    ) -> list[TenantModelRateLimit]:
        """
        获取租户活跃速率限制列表

        Args:
            model_id: 模型 ID（可选）

        Returns:
            TenantModelRateLimit 列表
        """
        return await self.repo.get_active_limits(
            tenant_id=self.tenant_id,
            model_id=model_id,
        )

    async def create_rate_limit(
        self,
        model_id: int,
        rpm_limit: Optional[int] = None,
        tpm_limit: Optional[int] = None,
        description: Optional[str] = None
    ) -> TenantModelRateLimit:
        """
        创建速率限制配置

        Args:
            model_id: 模型 ID
            rpm_limit: RPM 限制
            tpm_limit: TPM 限制
            description: 描述

        Returns:
            创建的 TenantModelRateLimit 实例
        """
        data = {
            "model_id": model_id,
            "rpm_limit": rpm_limit,
            "tpm_limit": tpm_limit,
            "description": description,
        }

        rate_limit = await self.create(data)

        logger.info(
            _("ai.log.rate_limit_created"),
            tenant_id=self.tenant_id,
            model_id=model_id,
            rpm_limit=rpm_limit,
            tpm_limit=tpm_limit,
        )

        return rate_limit


__all__ = ["TenantRateLimitService"]
