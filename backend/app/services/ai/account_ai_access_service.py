"""Account-level AI availability guard and switch helpers."""

from __future__ import annotations

from typing import Any, Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.i18n import _
from app.exceptions import AuthorizationException
from app.models.org.admin_org_node import AdminOrgNode
from app.models.org.tenant_org_node import TenantOrgNode
from app.models.system.admin import Admin
from app.models.tenant.tenant import Tenant
from app.models.tenant.tenant_admin import TenantAdmin
from app.models.tenant.tenant_user import TenantUser
from app.services.tenant.quota_service import QuotaService

ACCOUNT_AI_DISABLED_CODE: Final = 4032
ACCOUNT_AI_DISABLED_REASON: Final = "account_ai_disabled"
TENANT_PLAN_AI_DISABLED_CODE: Final = 4033
TENANT_PLAN_AI_DISABLED_REASON: Final = "tenant_plan_ai_disabled"
AI_CHAT_FEATURE: Final = "ai_chat"
LEADER_AI_DISABLED_REASON: Final = "leader_ai_disabled"


class AccountAIAccessService:
    """Enforce account and tenant-plan AI availability before runtime entry."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def require_platform_admin_ai_access(self, admin: Admin) -> None:
        """Block platform admins whose account AI switch is disabled."""
        profile = await self.get_platform_admin_ai_availability_profile(admin)
        if not profile["effective_ai_enabled"]:
            self._raise_account_disabled(
                reason=str(profile.get("ai_unavailable_reason") or "")
            )

    async def require_tenant_admin_ai_access(self, tenant_admin: TenantAdmin) -> None:
        """Block tenant admins when account or tenant plan disables AI."""
        profile = await self.get_tenant_admin_ai_availability_profile(tenant_admin)
        if not profile["tenant_ai_enabled"]:
            self._raise_tenant_plan_disabled()
        if not profile["effective_ai_enabled"]:
            self._raise_account_disabled(
                reason=str(profile.get("ai_unavailable_reason") or "")
            )

    async def require_tenant_user_ai_access(self, tenant_user: TenantUser) -> None:
        """Block tenant business users when the owning tenant plan disables AI."""
        tenant = await self._load_tenant_with_plan(tenant_user.tenant_id)
        if tenant is None or not self._tenant_plan_ai_enabled(tenant):
            self._raise_tenant_plan_disabled()

    async def get_platform_admin_ai_availability_profile(
        self,
        admin: Admin,
    ) -> dict[str, Any]:
        """Build account and leader-chain AI availability for platform admins."""
        account_ai_enabled = self._account_ai_enabled(admin)
        if not account_ai_enabled:
            return {
                "account_ai_enabled": False,
                "leader_ai_enabled": True,
                "tenant_ai_enabled": True,
                "effective_ai_enabled": False,
                "ai_unavailable_reason": ACCOUNT_AI_DISABLED_REASON,
            }

        leader_ai_enabled = await self._platform_leader_chain_ai_enabled(admin)
        effective_ai_enabled = account_ai_enabled and leader_ai_enabled
        reason: str | None = None
        if not leader_ai_enabled:
            reason = LEADER_AI_DISABLED_REASON

        return {
            "account_ai_enabled": account_ai_enabled,
            "leader_ai_enabled": leader_ai_enabled,
            "tenant_ai_enabled": True,
            "effective_ai_enabled": effective_ai_enabled,
            "ai_unavailable_reason": None if effective_ai_enabled else reason,
        }

    async def get_tenant_admin_ai_availability_profile(
        self,
        tenant_admin: TenantAdmin,
    ) -> dict[str, Any]:
        """Build tenant-admin AI availability from account, leader chain, and plan."""
        account_ai_enabled = self._account_ai_enabled(tenant_admin)
        projected_tenant_ai = self._projected_tenant_ai_enabled(tenant_admin)

        if projected_tenant_ai is False:
            return {
                "account_ai_enabled": account_ai_enabled,
                "leader_ai_enabled": True,
                "tenant_ai_enabled": False,
                "effective_ai_enabled": False,
                "ai_unavailable_reason": TENANT_PLAN_AI_DISABLED_REASON,
            }

        if not account_ai_enabled:
            return {
                "account_ai_enabled": False,
                "leader_ai_enabled": True,
                "tenant_ai_enabled": True,
                "effective_ai_enabled": False,
                "ai_unavailable_reason": ACCOUNT_AI_DISABLED_REASON,
            }

        leader_ai_enabled = await self._tenant_leader_chain_ai_enabled(tenant_admin)

        tenant = await self._load_tenant_with_plan(tenant_admin.tenant_id)
        tenant_ai_enabled = False if tenant is None else self._tenant_plan_ai_enabled(
            tenant
        )
        if projected_tenant_ai is not None:
            tenant_ai_enabled = projected_tenant_ai and tenant_ai_enabled

        effective_ai_enabled = (
            account_ai_enabled and leader_ai_enabled and tenant_ai_enabled
        )
        reason: str | None = None
        if not tenant_ai_enabled:
            reason = TENANT_PLAN_AI_DISABLED_REASON
        elif not account_ai_enabled:
            reason = ACCOUNT_AI_DISABLED_REASON
        elif not leader_ai_enabled:
            reason = LEADER_AI_DISABLED_REASON

        return {
            "account_ai_enabled": account_ai_enabled,
            "leader_ai_enabled": leader_ai_enabled,
            "tenant_ai_enabled": tenant_ai_enabled,
            "effective_ai_enabled": effective_ai_enabled,
            "ai_unavailable_reason": None if effective_ai_enabled else reason,
        }

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
                Tenant.is_active.is_(True),
                Tenant.is_deleted.is_(False),
            )
        )
        return result.scalar_one_or_none()

    async def _platform_leader_chain_ai_enabled(self, admin: Admin) -> bool:
        org_node_id = getattr(admin, "org_node_id", None)
        if org_node_id is None:
            return True

        org_node = await self._db.get(AdminOrgNode, org_node_id)
        if org_node is None or org_node.is_deleted:
            return True

        node_ids = self._parse_org_path(getattr(org_node, "path", None), org_node_id)
        if not node_ids:
            return True

        result = await self._db.execute(
            select(Admin.ai_enabled)
            .join(AdminOrgNode, AdminOrgNode.leader_id == Admin.id)
            .where(
                AdminOrgNode.id.in_(node_ids),
                AdminOrgNode.is_deleted.is_(False),
                Admin.is_deleted.is_(False),
                Admin.id != admin.id,
            )
        )
        return all(bool(value) for value in result.scalars().all())

    async def _tenant_leader_chain_ai_enabled(self, tenant_admin: TenantAdmin) -> bool:
        org_node_id = getattr(tenant_admin, "org_node_id", None)
        if org_node_id is None:
            return True

        org_node = await self._db.get(TenantOrgNode, org_node_id)
        if (
            org_node is None
            or org_node.is_deleted
            or org_node.tenant_id != tenant_admin.tenant_id
        ):
            return True

        node_ids = self._parse_org_path(getattr(org_node, "path", None), org_node_id)
        if not node_ids:
            return True

        result = await self._db.execute(
            select(TenantAdmin.ai_enabled)
            .join(TenantOrgNode, TenantOrgNode.leader_id == TenantAdmin.id)
            .where(
                TenantOrgNode.tenant_id == tenant_admin.tenant_id,
                TenantOrgNode.id.in_(node_ids),
                TenantOrgNode.is_deleted.is_(False),
                TenantAdmin.tenant_id == tenant_admin.tenant_id,
                TenantAdmin.is_deleted.is_(False),
                TenantAdmin.id != tenant_admin.id,
            )
        )
        return all(bool(value) for value in result.scalars().all())

    @staticmethod
    def _parse_org_path(path: str | None, fallback_id: int) -> list[int]:
        if not path:
            return [fallback_id]
        node_ids: list[int] = []
        for raw_part in path.strip("/").split("/"):
            try:
                node_ids.append(int(raw_part))
            except ValueError:
                continue
        return list(dict.fromkeys(node_ids or [fallback_id]))

    def _tenant_plan_ai_enabled(self, tenant: Tenant) -> bool:
        has_plan = getattr(tenant, "plan_id", None) is not None
        if not bool(getattr(tenant, "is_active", False)):
            return False
        plan = getattr(tenant, "tenant_plan", None)
        if not has_plan or plan is None or not getattr(plan, "is_active", False):
            return False
        return QuotaService(self._db, tenant).get_feature("ai_enabled", has_plan)

    @staticmethod
    def _raise_account_disabled(reason: str = ACCOUNT_AI_DISABLED_REASON) -> None:
        reason = (
            reason
            if reason == LEADER_AI_DISABLED_REASON
            else ACCOUNT_AI_DISABLED_REASON
        )
        message_key = (
            "ai.error.leader_ai_disabled"
            if reason == LEADER_AI_DISABLED_REASON
            else "ai.error.account_ai_disabled"
        )
        raise AuthorizationException(
            message=_(message_key),
            code=ACCOUNT_AI_DISABLED_CODE,
            extra={"reason": reason, "feature": AI_CHAT_FEATURE},
        )

    @staticmethod
    def _raise_tenant_plan_disabled() -> None:
        raise AuthorizationException(
            message=_("ai.error.tenant_plan_ai_disabled"),
            code=TENANT_PLAN_AI_DISABLED_CODE,
            extra={
                "reason": TENANT_PLAN_AI_DISABLED_REASON,
                "feature": AI_CHAT_FEATURE,
            },
        )


__all__ = [
    "ACCOUNT_AI_DISABLED_CODE",
    "ACCOUNT_AI_DISABLED_REASON",
    "AI_CHAT_FEATURE",
    "LEADER_AI_DISABLED_REASON",
    "TENANT_PLAN_AI_DISABLED_CODE",
    "TENANT_PLAN_AI_DISABLED_REASON",
    "AccountAIAccessService",
]
