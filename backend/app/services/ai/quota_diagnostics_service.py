"""
AI 配额诊断 Service / AI quota diagnostics service
"""

from __future__ import annotations

from app.ai.quota import QuotaExceeded, UsageTracker
from app.ai.rate_limiter import RateLimiter, RateLimitExceeded
from app.core.base_schema import PageResponse
from app.core.i18n import _
from app.core.query_parser import QuerySpec
from app.enums.ai import QuotaTypeEnum
from app.models.ai import TenantModelRateLimit, TenantQuota
from app.repositories.ai.quota_diagnostics_repository import (
    AIQuotaDiagnosticsRepository,
)
from app.repositories.ai.tenant_quota_repository import TenantQuotaRepository
from app.repositories.ai.tenant_rate_limit_repository import (
    TenantModelRateLimitRepository,
)
from app.schemas.ai.quota_diagnostics import (
    AdminQuotaDiagnosticItem,
    AdminRateLimitDiagnosticItem,
    AIQuotaDiagnosticsSummary,
)
from app.services.ai.tenant_rate_limit_service import TenantRateLimitService


class AIQuotaDiagnosticsService:
    """
    管理端 AI 配额/限速诊断 Service / Admin AI quota & rate-limit diagnostics service.
    """

    def __init__(self, db) -> None:
        self.db = db
        self.repo = AIQuotaDiagnosticsRepository(db)

    async def get_summary(self) -> AIQuotaDiagnosticsSummary:
        all_quotas = await self.repo.list_all_quota_rules()
        all_rate_limits = await self.repo.list_all_rate_limit_rules()
        tenant_name_map = await self.repo.get_tenant_name_map(
            {item.tenant_id for item in all_rate_limits}
        )

        quota_items = [
            await self._build_quota_diagnostic(item)
            for item in all_quotas
            if item.is_active
        ]
        rate_limit_items = [
            await self._build_rate_limit_diagnostic(item, tenant_name_map)
            for item in all_rate_limits
            if item.is_active
        ]

        return AIQuotaDiagnosticsSummary(
            total_quota_rules=len(all_quotas),
            active_quota_rules=sum(1 for item in all_quotas if item.is_active),
            hard_quota_rules=sum(
                1
                for item in all_quotas
                if item.is_active and item.quota_type == QuotaTypeEnum.HARD.value
            ),
            soft_quota_rules=sum(
                1
                for item in all_quotas
                if item.is_active and item.quota_type == QuotaTypeEnum.SOFT.value
            ),
            quota_warning_rules=sum(1 for item in quota_items if item.is_warning),
            quota_exceeded_rules=sum(1 for item in quota_items if item.is_exceeded),
            total_rate_limit_rules=len(all_rate_limits),
            active_rate_limit_rules=sum(
                1 for item in all_rate_limits if item.is_active
            ),
            rate_limit_warning_rules=sum(
                1 for item in rate_limit_items if item.is_warning
            ),
            rate_limit_exceeded_rules=sum(
                1 for item in rate_limit_items if item.is_exceeded
            ),
        )

    async def list_quota_diagnostics(
        self,
        spec: QuerySpec,
    ) -> PageResponse[AdminQuotaDiagnosticItem]:
        items, total = await self.repo.list_quota_rules(spec)
        diagnostics = [await self._build_quota_diagnostic(item) for item in items]
        return PageResponse.create(
            items=diagnostics,
            total=total,
            page=spec.page,
            page_size=spec.size,
        )

    async def list_rate_limit_diagnostics(
        self,
        spec: QuerySpec,
    ) -> PageResponse[AdminRateLimitDiagnosticItem]:
        items, total = await self.repo.list_rate_limit_rules(spec)
        tenant_name_map = await self.repo.get_tenant_name_map(
            {item.tenant_id for item in items}
        )
        diagnostics = [
            await self._build_rate_limit_diagnostic(item, tenant_name_map)
            for item in items
        ]
        return PageResponse.create(
            items=diagnostics,
            total=total,
            page=spec.page,
            page_size=spec.size,
        )

    async def _build_quota_diagnostic(
        self,
        quota: TenantQuota,
    ) -> AdminQuotaDiagnosticItem:
        tracking_model_id = quota.model_id if quota.model_id is not None else 0
        usage = await UsageTracker.get_usage(
            tenant_id=quota.tenant_id,
            model_id=tracking_model_id,
            period=quota.period,
        )
        usage_percent = (usage / quota.limit * 100) if quota.limit > 0 else 0
        warning_threshold = quota.warning_threshold or 80
        is_exceeded = quota.is_active and usage_percent >= 100
        is_warning = (
            quota.is_active and not is_exceeded and usage_percent >= warning_threshold
        )
        runtime_status = (
            "inactive"
            if not quota.is_active
            else (
                "exceeded" if is_exceeded else ("warning" if is_warning else "healthy")
            )
        )

        scope_repo = TenantQuotaRepository(self.db, quota.tenant_id)
        latest_scope_rule = await scope_repo.get_latest_active_scope_quota(
            tenant_id=quota.tenant_id,
            model_id=quota.model_id,
            period=quota.period,
        )
        is_latest_scope_rule = (
            True
            if not quota.is_active
            else latest_scope_rule is None or latest_scope_rule.id == quota.id
        )

        is_hard = quota.quota_type == QuotaTypeEnum.HARD.value and quota.is_active
        exhaustion_message_preview = (
            _("ai.error.quota_exceeded").format(
                current=max(quota.limit, usage),
                limit=quota.limit,
                period=quota.period,
            )
            if is_hard
            else None
        )

        tenant_name = getattr(getattr(quota, "tenant", None), "name", None)
        model_name = getattr(getattr(quota, "model", None), "name", None)

        return AdminQuotaDiagnosticItem(
            id=quota.id,
            tenant_id=quota.tenant_id,
            tenant_name=tenant_name,
            model_id=quota.model_id,
            model_name=model_name,
            period=quota.period,
            limit=quota.limit,
            quota_type=quota.quota_type,
            warning_threshold=quota.warning_threshold,
            is_active=quota.is_active,
            description=quota.description,
            scope_type="global" if quota.model_id is None else "model",
            tracking_model_id=tracking_model_id,
            usage=usage,
            remaining=max(0, quota.limit - usage),
            usage_percent=round(usage_percent, 2),
            is_warning=is_warning,
            is_exceeded=is_exceeded,
            runtime_status=runtime_status,
            exhaustion_action="deny" if is_hard else "allow",
            exhaustion_http_status=QuotaExceeded.status_code if is_hard else None,
            exhaustion_error_code=QuotaExceeded.code if is_hard else None,
            exhaustion_message_preview=exhaustion_message_preview,
            is_latest_scope_rule=is_latest_scope_rule,
            created_at=quota.created_at,
            updated_at=quota.updated_at,
        )

    async def _build_rate_limit_diagnostic(
        self,
        rate_limit: TenantModelRateLimit,
        tenant_name_map: dict[int, str],
    ) -> AdminRateLimitDiagnosticItem:
        service = TenantRateLimitService(self.db, rate_limit.tenant_id)
        effective = await service.get_effective_rate_limits(rate_limit.model_id)
        usage = await RateLimiter.get_current_usage(
            tenant_id=rate_limit.tenant_id,
            model_id=rate_limit.model_id,
        )
        current_rpm = int(usage.get("rpm", 0) or 0)
        current_tpm = int(usage.get("tpm", 0) or 0)
        effective_rpm = effective.get("rpm_limit")
        effective_tpm = effective.get("tpm_limit")
        rpm_usage_percent = (
            current_rpm / effective_rpm * 100
            if effective_rpm and effective_rpm > 0
            else 0
        )
        tpm_usage_percent = (
            current_tpm / effective_tpm * 100
            if effective_tpm and effective_tpm > 0
            else 0
        )
        is_exceeded = rate_limit.is_active and (
            (effective_rpm is not None and current_rpm >= effective_rpm)
            or (effective_tpm is not None and current_tpm >= effective_tpm)
        )
        is_warning = (
            rate_limit.is_active
            and not is_exceeded
            and (rpm_usage_percent >= 80 or tpm_usage_percent >= 80)
        )
        runtime_status = (
            "inactive"
            if not rate_limit.is_active
            else (
                "exceeded" if is_exceeded else ("warning" if is_warning else "healthy")
            )
        )

        repo = TenantModelRateLimitRepository(self.db, rate_limit.tenant_id)
        latest_rule = await repo.get_latest_active_limit(
            tenant_id=rate_limit.tenant_id,
            model_id=rate_limit.model_id,
        )
        is_latest_model_rule = (
            True
            if not rate_limit.is_active
            else latest_rule is None or latest_rule.id == rate_limit.id
        )

        message_preview = _("ai.rate_limited")
        if effective_rpm is not None and current_rpm >= effective_rpm:
            message_preview = _("ai.error.rpm_limit_exceeded").format(
                count=current_rpm,
                limit=effective_rpm,
            )
        elif effective_tpm is not None and current_tpm >= effective_tpm:
            message_preview = _("ai.error.tpm_limit_exceeded").format(
                count=current_tpm,
                limit=effective_tpm,
            )

        model_name = getattr(getattr(rate_limit, "model", None), "name", None)
        return AdminRateLimitDiagnosticItem(
            id=rate_limit.id,
            tenant_id=rate_limit.tenant_id,
            tenant_name=tenant_name_map.get(rate_limit.tenant_id),
            model_id=rate_limit.model_id,
            model_name=model_name,
            is_active=rate_limit.is_active,
            description=rate_limit.description,
            configured_rpm_limit=rate_limit.rpm_limit,
            configured_tpm_limit=rate_limit.tpm_limit,
            model_default_rpm_limit=effective.get("model_default_rpm_limit"),
            model_default_tpm_limit=effective.get("model_default_tpm_limit"),
            effective_rpm_limit=effective_rpm,
            effective_tpm_limit=effective_tpm,
            rpm_source=str(effective.get("rpm_source", "none")),
            tpm_source=str(effective.get("tpm_source", "none")),
            current_rpm=current_rpm,
            current_tpm=current_tpm,
            rpm_usage_percent=round(rpm_usage_percent, 2),
            tpm_usage_percent=round(tpm_usage_percent, 2),
            is_warning=is_warning,
            is_exceeded=is_exceeded,
            runtime_status=runtime_status,
            exhaustion_action="deny",
            exhaustion_http_status=RateLimitExceeded.status_code,
            exhaustion_error_code=RateLimitExceeded.code,
            exhaustion_message_preview=message_preview,
            is_latest_model_rule=is_latest_model_rule,
            created_at=rate_limit.created_at,
            updated_at=rate_limit.updated_at,
        )


__all__ = ["AIQuotaDiagnosticsService"]
