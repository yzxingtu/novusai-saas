"""
企业 AI 模型速率限制配置 Service / Tenant AI Rate Limit Service
"""


from app.core.base_service import TenantService
from app.core.i18n import _
from app.core.logging import LogManager
from app.exceptions import BusinessException, NotFoundException
from app.models.ai import TenantModelRateLimit
from app.repositories.ai.model_repository import AIModelRepository
from app.repositories.ai.tenant_rate_limit_repository import (
    TenantModelRateLimitRepository,
)

logger = LogManager.get_logger("ai.rate_limit_service")


class TenantRateLimitService(TenantService[TenantModelRateLimit, TenantModelRateLimitRepository]):
    """
    企业 AI 模型速率限制配置 Service / Tenant model rate limit service.
    """

    model = TenantModelRateLimit
    repository_class = TenantModelRateLimitRepository

    async def get_rate_limit(
        self,
        model_id: int
    ) -> TenantModelRateLimit | None:
        """
        获取企业对指定模型的速率限制配置 / Get rate limit config for tenant and model.

        Args:
            model_id: 模型 ID

        Returns:
            TenantModelRateLimit 实例
        """
        return await self.repo.get_latest_active_limit(self.tenant_id, model_id)

    async def get_effective_rate_limits(
        self,
        model_id: int
    ) -> dict:
        """
        获取有效的速率限制（优先使用企业配置，否则使用模型默认值）/ Get effective rate limits (tenant first, then model default).

        Args:
            model_id: 模型 ID

        Returns:
            包含 rpm_limit 和 tpm_limit 的字典
        """
        model_repo = AIModelRepository(self.db)
        model = await model_repo.get_by_id(model_id)

        model_rpm = getattr(model, "rpm_limit", None)
        model_tpm = getattr(model, "tpm_limit", None)

        # 先查企业配置 / Read tenant config first
        tenant_limit = await self.get_rate_limit(model_id)

        if tenant_limit and tenant_limit.is_active:
            effective_rpm = (
                tenant_limit.rpm_limit
                if tenant_limit.rpm_limit is not None
                else model_rpm
            )
            effective_tpm = (
                tenant_limit.tpm_limit
                if tenant_limit.tpm_limit is not None
                else model_tpm
            )
            return {
                "rpm_limit": effective_rpm,
                "tpm_limit": effective_tpm,
                "source": (
                    "tenant"
                    if tenant_limit.rpm_limit is not None
                    or tenant_limit.tpm_limit is not None
                    else ("model" if model else "none")
                ),
                "rpm_source": (
                    "tenant"
                    if tenant_limit.rpm_limit is not None
                    else ("model" if model_rpm is not None else "none")
                ),
                "tpm_source": (
                    "tenant"
                    if tenant_limit.tpm_limit is not None
                    else ("model" if model_tpm is not None else "none")
                ),
                "model_default_rpm_limit": model_rpm,
                "model_default_tpm_limit": model_tpm,
            }

        # 如果企业没配置，查模型默认值 / If tenant has no config, use model defaults
        if model:
            return {
                "rpm_limit": model_rpm,
                "tpm_limit": model_tpm,
                "source": "model",
                "rpm_source": "model" if model_rpm is not None else "none",
                "tpm_source": "model" if model_tpm is not None else "none",
                "model_default_rpm_limit": model_rpm,
                "model_default_tpm_limit": model_tpm,
            }

        # 都没有配置 / Neither side configured
        return {
            "rpm_limit": None,
            "tpm_limit": None,
            "source": "none",
            "rpm_source": "none",
            "tpm_source": "none",
            "model_default_rpm_limit": None,
            "model_default_tpm_limit": None,
        }

    async def get_active_limits(
        self,
        model_id: int | None = None,
    ) -> list[TenantModelRateLimit]:
        """
        获取企业活跃速率限制列表 / Get active rate limit list for tenant.

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
        rpm_limit: int | None = None,
        tpm_limit: int | None = None,
        description: str | None = None
    ) -> TenantModelRateLimit:
        """
        创建速率限制配置 / Create rate limit config.

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
            "Rate limit created: tenant_id={} model_id={} rpm_limit={} tpm_limit={}",
            self.tenant_id, model_id, rpm_limit, tpm_limit,
        )

        return rate_limit

    async def _before_create(self, data: dict) -> None:
        await super()._before_create(data)
        is_active = data.get("is_active", True)
        if not is_active:
            return

        model_id = int(data["model_id"])
        has_conflict = await self.repo.has_active_conflict(
            tenant_id=self.tenant_id,
            model_id=model_id,
        )
        if has_conflict:
            raise BusinessException(message=_("ai.error.rate_limit_duplicate_active"))

    async def _before_update(self, id: int, data: dict) -> None:
        await super()._before_update(id, data)
        current = await self.repo.get_by_id(id)
        if current is None:
            raise NotFoundException(message=_("ai.error.rate_limit_not_found"))

        next_active = bool(data.get("is_active", current.is_active))
        if not next_active:
            return

        next_model_id = int(data.get("model_id", current.model_id))
        has_conflict = await self.repo.has_active_conflict(
            tenant_id=self.tenant_id,
            model_id=next_model_id,
            exclude_id=id,
        )
        if has_conflict:
            raise BusinessException(message=_("ai.error.rate_limit_duplicate_active"))


__all__ = ["TenantRateLimitService"]
