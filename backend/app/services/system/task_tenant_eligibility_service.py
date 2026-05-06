"""Tenant eligibility resolver for scheduled tenant task dispatch."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from sqlalchemy import and_, select
from sqlalchemy.orm import aliased

from app.models.system.tenant_task_binding import TenantTaskBinding
from app.models.tenant.tenant import Tenant
from app.models.tenant.tenant_plan import TenantPlan


@dataclass(frozen=True)
class TaskTenantEligibilityRequirements:
    """中文: 预留任务级功能/插件权益要求。

    EN: Carries future task-level feature/plugin entitlement requirements.
    """

    feature_codes: tuple[str, ...] = field(default_factory=tuple)
    plugin_names: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class TaskTenantEligibilityResult:
    """中文: 企业调度资格判定结果。

    EN: Result for tenant scheduling eligibility resolution.
    """

    is_eligible: bool
    tenant_id: int
    reason: str | None = None


class TaskTenantEligibilityService:
    """Resolve the shared tenant eligibility contract for scheduled tasks."""

    def __init__(
        self,
        db,
        *,
        requirements: TaskTenantEligibilityRequirements | None = None,
    ) -> None:
        self.db = db
        self.requirements = requirements or TaskTenantEligibilityRequirements()

    @staticmethod
    def eligible_tenant_filters():
        return (
            Tenant.is_deleted.is_(False),
            Tenant.is_active.is_(True),
            Tenant.plan_id.is_not(None),
            TenantPlan.is_deleted.is_(False),
            TenantPlan.is_active.is_(True),
        )

    @staticmethod
    def eligible_tenant_join_condition():
        return TenantPlan.id == Tenant.plan_id

    @staticmethod
    def _normalize_tenant_ids(tenant_ids: Iterable[int] | None) -> list[int]:
        if tenant_ids is None:
            return []
        normalized: list[int] = []
        seen: set[int] = set()
        for raw_id in tenant_ids:
            tenant_id = int(raw_id)
            if tenant_id in seen:
                continue
            seen.add(tenant_id)
            normalized.append(tenant_id)
        return normalized

    async def resolve_eligible_tenant_ids(
        self,
        tenant_ids: Iterable[int] | None = None,
    ) -> list[int]:
        stmt = (
            select(Tenant.id)
            .join(TenantPlan, self.eligible_tenant_join_condition())
            .where(*self.eligible_tenant_filters())
            .order_by(Tenant.id.asc())
        )
        normalized_ids = self._normalize_tenant_ids(tenant_ids)
        if normalized_ids:
            stmt = stmt.where(Tenant.id.in_(normalized_ids))
        stmt = self._apply_entitlement_filters(stmt)
        result = await self.db.execute(stmt)
        return [int(tenant_id) for tenant_id in result.scalars().all()]

    async def resolve_tenant_eligibility(
        self,
        tenant_id: int,
    ) -> TaskTenantEligibilityResult:
        tenant = await self.db.get(Tenant, tenant_id)
        return await self.resolve_tenant_model_eligibility(tenant_id, tenant)

    async def resolve_tenant_model_eligibility(
        self,
        tenant_id: int,
        tenant,
    ) -> TaskTenantEligibilityResult:
        if tenant is None or bool(getattr(tenant, "is_deleted", False)):
            return TaskTenantEligibilityResult(False, tenant_id, "tenant_not_available")
        if not bool(getattr(tenant, "is_active", False)):
            return TaskTenantEligibilityResult(False, tenant_id, "tenant_inactive")
        plan_id = getattr(tenant, "plan_id", None)
        if plan_id is None:
            return TaskTenantEligibilityResult(
                False,
                tenant_id,
                "tenant_plan_not_available",
            )
        plan = getattr(tenant, "tenant_plan", None)
        if plan is None:
            plan = await self.db.get(TenantPlan, plan_id)
        if (
            plan is None
            or bool(getattr(plan, "is_deleted", False))
            or not bool(getattr(plan, "is_active", False))
        ):
            return TaskTenantEligibilityResult(
                False,
                tenant_id,
                "tenant_plan_not_available",
            )
        if not await self._entitlements_allow_tenant(tenant_id):
            return TaskTenantEligibilityResult(
                False,
                tenant_id,
                "tenant_entitlement_not_available",
            )
        return TaskTenantEligibilityResult(True, tenant_id)

    def _apply_entitlement_filters(self, stmt):
        _ = self.requirements
        return stmt

    async def _entitlements_allow_tenant(self, tenant_id: int) -> bool:
        _ = (tenant_id, self.requirements)
        return True

    @classmethod
    def resolve_all_tenant_ids_sync(
        cls,
        session,
        *,
        task_definition_id: int | None = None,
        requirements: TaskTenantEligibilityRequirements | None = None,
    ) -> list[int]:
        disabled_binding = aliased(TenantTaskBinding)
        query = (
            session.query(Tenant.id)
            .join(TenantPlan, cls.eligible_tenant_join_condition())
            .filter(*cls.eligible_tenant_filters())
        )
        if task_definition_id is not None:
            query = query.outerjoin(
                disabled_binding,
                and_(
                    disabled_binding.task_definition_id == task_definition_id,
                    disabled_binding.tenant_id == Tenant.id,
                    disabled_binding.is_deleted.is_(False),
                    disabled_binding.is_enabled.is_(False),
                ),
            ).filter(disabled_binding.id.is_(None))
        query = cls._apply_entitlement_filters_sync(query, requirements)
        rows = query.order_by(Tenant.id.asc()).all()
        return [int(tenant_id) for (tenant_id,) in rows]

    @classmethod
    def resolve_tenant_eligibility_sync(
        cls,
        session,
        tenant_id: int,
        *,
        requirements: TaskTenantEligibilityRequirements | None = None,
    ) -> TaskTenantEligibilityResult:
        tenant = (
            session.query(Tenant)
            .filter(
                Tenant.id == tenant_id,
                Tenant.is_deleted.is_(False),
            )
            .first()
        )
        if tenant is None:
            return TaskTenantEligibilityResult(False, tenant_id, "tenant_not_available")
        if not bool(getattr(tenant, "is_active", False)):
            return TaskTenantEligibilityResult(False, tenant_id, "tenant_inactive")
        plan_id = getattr(tenant, "plan_id", None)
        if plan_id is None:
            return TaskTenantEligibilityResult(
                False,
                tenant_id,
                "tenant_plan_not_available",
            )
        plan = (
            session.query(TenantPlan)
            .filter(
                TenantPlan.id == plan_id,
                TenantPlan.is_deleted.is_(False),
                TenantPlan.is_active.is_(True),
            )
            .first()
        )
        if plan is None:
            return TaskTenantEligibilityResult(
                False,
                tenant_id,
                "tenant_plan_not_available",
            )
        if not cls._entitlements_allow_tenant_sync(
            session,
            tenant_id,
            requirements,
        ):
            return TaskTenantEligibilityResult(
                False,
                tenant_id,
                "tenant_entitlement_not_available",
            )
        return TaskTenantEligibilityResult(True, tenant_id)

    @staticmethod
    def _apply_entitlement_filters_sync(query, requirements):
        _ = requirements
        return query

    @staticmethod
    def _entitlements_allow_tenant_sync(session, tenant_id: int, requirements) -> bool:
        _ = (session, tenant_id, requirements)
        return True


__all__ = [
    "TaskTenantEligibilityRequirements",
    "TaskTenantEligibilityResult",
    "TaskTenantEligibilityService",
]
