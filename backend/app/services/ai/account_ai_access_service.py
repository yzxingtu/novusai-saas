"""Account-level AI availability guard and switch helpers."""

from __future__ import annotations

from typing import Any, Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.i18n import _
from app.exceptions import AuthorizationException
from app.models.system.admin import Admin
from app.models.tenant.tenant import Tenant
from app.models.tenant.tenant_admin import TenantAdmin
from app.services.tenant.quota_service import QuotaService

ACCOUNT_AI_DISABLED_CODE: Final = 4032
ACCOUNT_AI_DISABLED_REASON: Final = "account_ai_disabled"
TENANT_PLAN_AI_DISABLED_CODE: Final = 4033
TENANT_PLAN_AI_DISABLED_REASON: Final = "tenant_plan_ai_disabled"
AI_CHAT_FEATURE: Final = "ai_chat"


class AccountAIAccessService:
    """Enforce account and tenant-plan AI availability before runtime entry."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def require_platform_admin_ai_access(self, admin: Admin) -> None:
        """Block platform admins whose account AI switch is disabled."""
        if not self._account_ai_enabled(admin):
            self._raise_account_disabled()

    async def require_tenant_admin_ai_access(self, tenant_admin: TenantAdmin) -> None:
        """Block tenant admins when account or tenant plan disables AI."""
        if not self._account_ai_enabled(tenant_admin):
            self._raise_account_disabled()

        projected_tenant_ai = self._projected_tenant_ai_enabled(tenant_admin)
        if projected_tenant_ai is False:
            self._raise_tenant_plan_disabled()

        tenant = await self._load_tenant_with_plan(tenant_admin.tenant_id)
        if tenant is None:
            self._raise_tenant_plan_disabled()

        if not self._tenant_plan_ai_enabled(tenant):
            self._raise_tenant_plan_disabled()

    @staticmethod
    def _account_ai_enabled(account: Any) -> bool:
        return bool(getattr(account, "ai_enabled", True))

    @staticmethod
    def _projected_tenant_ai_enabled(account: Any) -> bool | None:
        for attr in ("tenant_plan_ai_enabled", "tenant_ai_enabled"):
            value = getattr(account, attr, None)
            if isinstance(value, bool):
                return value
        return None

    async def _load_tenant_with_plan(self, tenant_id: int) -> Tenant | None:
        result = await self._db.execute(
            select(Tenant)
            .options(selectinload(Tenant.tenant_plan))
            .where(
                Tenant.id == tenant_id,
                Tenant.is_deleted.is_(False),
            )
        )
        return result.scalar_one_or_none()

    def _tenant_plan_ai_enabled(self, tenant: Tenant) -> bool:
        has_plan = getattr(tenant, "plan_id", None) is not None
        return QuotaService(self._db, tenant).get_feature("ai_enabled", has_plan)

    @staticmethod
    def _raise_account_disabled() -> None:
        raise AuthorizationException(
            message=_("ai.error.account_ai_disabled"),
            code=ACCOUNT_AI_DISABLED_CODE,
            extra={"reason": ACCOUNT_AI_DISABLED_REASON, "feature": AI_CHAT_FEATURE},
        )

    @staticmethod
    def _raise_tenant_plan_disabled() -> None:
        raise AuthorizationException(
            message=_("ai.error.tenant_plan_ai_disabled"),
            code=TENANT_PLAN_AI_DISABLED_CODE,
            extra={"reason": TENANT_PLAN_AI_DISABLED_REASON, "feature": AI_CHAT_FEATURE},
        )


__all__ = [
    "ACCOUNT_AI_DISABLED_CODE",
    "ACCOUNT_AI_DISABLED_REASON",
    "AI_CHAT_FEATURE",
    "TENANT_PLAN_AI_DISABLED_CODE",
    "TENANT_PLAN_AI_DISABLED_REASON",
    "AccountAIAccessService",
]
