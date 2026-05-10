"""Tenant eligibility resolver for scheduled tenant task dispatch."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.orm import aliased

from app.core.base_model import utc_now
from app.core.scope import ScopeChecker
from app.enums.plugin import (
    PluginLicenseTypeEnum,
    PluginPricingTypeEnum,
    PluginStatusEnum,
)
from app.models.system.plugin import Plugin
from app.models.system.plugin_license import PluginLicense
from app.models.system.resource_tenant_assignment import ResourceTenantAssignment
from app.models.system.tenant_task_binding import TenantTaskBinding
from app.models.tenant.tenant import Tenant
from app.models.tenant.tenant_plan import TenantPlan
from app.plugins.exposure_policy import build_plugin_exposure_profile
from app.plugins.runtime_gate import evaluate_plugin_runtime_gate

_TRUE_ENTITLEMENT_VALUES = {"1", "true", "yes", "on", "enabled"}


def _normalize_requirement_values(values: object) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        raw_values: Iterable[object] = (values,)
    elif isinstance(values, Mapping):
        raw_values = (values,)
    elif isinstance(values, Iterable):
        raw_values = values
    else:
        raw_values = (values,)

    normalized: list[str] = []
    seen: set[str] = set()
    for raw_value in raw_values:
        value = str(raw_value or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return tuple(normalized)


def _entitlement_flag_enabled(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in _TRUE_ENTITLEMENT_VALUES
    return bool(value)


def _to_naive_utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _row_item(row: Any, index: int, default: Any = None) -> Any:
    try:
        return row[index]
    except (IndexError, KeyError, TypeError):
        return default


@dataclass(frozen=True)
class TaskTenantEligibilityRequirements:
    """中文: 任务级功能/插件权益要求。

    EN: Task-level feature/plugin entitlement requirements.
    """

    feature_codes: tuple[str, ...] = field(default_factory=tuple)
    plugin_names: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "feature_codes",
            _normalize_requirement_values(self.feature_codes),
        )
        object.__setattr__(
            self,
            "plugin_names",
            _normalize_requirement_values(self.plugin_names),
        )

    @property
    def has_requirements(self) -> bool:
        return bool(self.feature_codes or self.plugin_names)

    @classmethod
    def from_definition(
        cls,
        definition: object | None,
    ) -> TaskTenantEligibilityRequirements:
        if definition is None:
            return cls()
        return cls(
            feature_codes=getattr(definition, "required_feature_codes", None),
            plugin_names=getattr(definition, "required_plugin_names", None),
        )


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
        if self.requirements.has_requirements:
            stmt = select(Tenant.id, TenantPlan.features)
        else:
            stmt = select(Tenant.id)
        stmt = stmt.join(TenantPlan, self.eligible_tenant_join_condition()).where(
            *self.eligible_tenant_filters()
        )
        normalized_ids = self._normalize_tenant_ids(tenant_ids)
        if normalized_ids:
            stmt = stmt.where(Tenant.id.in_(normalized_ids))
        stmt = stmt.order_by(Tenant.id.asc())
        result = await self.db.execute(stmt)
        if not self.requirements.has_requirements:
            return [int(tenant_id) for tenant_id in result.scalars().all()]

        tenant_ids: list[int] = []
        for row in result.all():
            tenant_id = int(_row_item(row, 0))
            features = _row_item(row, 1, {})
            if not self._plan_features_allow_requirements(
                features,
                self.requirements,
            ):
                continue
            if not await self._plugin_requirements_allow_tenant(tenant_id):
                continue
            tenant_ids.append(tenant_id)
        return tenant_ids

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
        if not self._plan_features_allow_requirements(
            getattr(plan, "features", None),
            self.requirements,
        ):
            return TaskTenantEligibilityResult(
                False,
                tenant_id,
                "tenant_entitlement_not_available",
            )
        if not await self._plugin_requirements_allow_tenant(tenant_id):
            return TaskTenantEligibilityResult(
                False,
                tenant_id,
                "tenant_entitlement_not_available",
            )
        return TaskTenantEligibilityResult(True, tenant_id)

    @staticmethod
    def _plan_features_allow_requirements(
        features: object,
        requirements: TaskTenantEligibilityRequirements | None,
    ) -> bool:
        req = requirements or TaskTenantEligibilityRequirements()
        if not req.feature_codes:
            return True
        if not isinstance(features, Mapping):
            return False
        return all(
            _entitlement_flag_enabled(features.get(feature_code))
            for feature_code in req.feature_codes
        )

    async def _plugin_requirements_allow_tenant(self, tenant_id: int) -> bool:
        if not self.requirements.plugin_names:
            return True
        for plugin_name in self.requirements.plugin_names:
            gate = await evaluate_plugin_runtime_gate(
                self.db,
                plugin_name,
                tenant_id=tenant_id,
                require_enabled=True,
                enforce_scope=True,
            )
            if not gate.allowed:
                return False
        return True

    @classmethod
    def resolve_all_tenant_ids_sync(
        cls,
        session,
        *,
        task_definition_id: int | None = None,
        requirements: TaskTenantEligibilityRequirements | None = None,
    ) -> list[int]:
        req = requirements or TaskTenantEligibilityRequirements()
        disabled_binding = aliased(TenantTaskBinding)
        selected_columns = (
            (Tenant.id, TenantPlan.features) if req.has_requirements else (Tenant.id,)
        )
        query = (
            session.query(*selected_columns)
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
        rows = query.order_by(Tenant.id.asc()).all()
        if not req.has_requirements:
            return [int(tenant_id) for (tenant_id,) in rows]

        tenant_ids: list[int] = []
        for row in rows:
            tenant_id = int(_row_item(row, 0))
            features = _row_item(row, 1, {})
            if not cls._plan_features_allow_requirements(features, req):
                continue
            if not cls._plugin_requirements_allow_tenant_sync(
                session,
                tenant_id,
                req,
            ):
                continue
            tenant_ids.append(tenant_id)
        return tenant_ids

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
        req = requirements or TaskTenantEligibilityRequirements()
        if not cls._plan_features_allow_requirements(
            getattr(plan, "features", None),
            req,
        ):
            return TaskTenantEligibilityResult(
                False,
                tenant_id,
                "tenant_entitlement_not_available",
            )
        if not cls._plugin_requirements_allow_tenant_sync(session, tenant_id, req):
            return TaskTenantEligibilityResult(
                False,
                tenant_id,
                "tenant_entitlement_not_available",
            )
        return TaskTenantEligibilityResult(True, tenant_id)

    @staticmethod
    def _plugin_license_allows_sync(session, plugin: Plugin) -> bool:
        pricing_type = str(getattr(plugin, "pricing_type", "") or "")
        if pricing_type != PluginPricingTypeEnum.PAID.value:
            return True

        now = utc_now()
        records = (
            session.query(PluginLicense)
            .filter(
                PluginLicense.plugin_id == getattr(plugin, "id", None),
                PluginLicense.is_deleted.is_(False),
                PluginLicense.is_valid.is_(True),
            )
            .all()
        )
        for record in records:
            if (
                getattr(record, "license_type", None)
                == PluginLicenseTypeEnum.TRIAL.value
            ):
                expires_at = _to_naive_utc(getattr(record, "trial_expires_at", None))
            else:
                expires_at = _to_naive_utc(getattr(record, "expires_at", None))
            if expires_at is not None and now >= expires_at:
                continue
            return True
        return False

    @classmethod
    def _plugin_scope_allows_tenant_sync(
        cls,
        session,
        plugin: Plugin,
        tenant_id: int,
    ) -> bool:
        profile = build_plugin_exposure_profile(
            getattr(plugin, "manifest", None) or {},
            scope=getattr(plugin, "scope", None),
        )
        runtime_scope = profile.tenant_runtime_scope
        if runtime_scope is None:
            return False
        if runtime_scope in ScopeChecker.get_all_tenants_visible_scopes():
            return True
        if runtime_scope not in ScopeChecker.get_assignment_required_scopes():
            return False

        assignment = (
            session.query(ResourceTenantAssignment.id)
            .filter(
                ResourceTenantAssignment.resource_type == "plugin",
                ResourceTenantAssignment.resource_id == getattr(plugin, "id", None),
                ResourceTenantAssignment.tenant_id == tenant_id,
                ResourceTenantAssignment.is_active.is_(True),
                ResourceTenantAssignment.is_deleted.is_(False),
            )
            .first()
        )
        return assignment is not None

    @classmethod
    def _plugin_requirements_allow_tenant_sync(
        cls,
        session,
        tenant_id: int,
        requirements: TaskTenantEligibilityRequirements | None,
    ) -> bool:
        req = requirements or TaskTenantEligibilityRequirements()
        if not req.plugin_names:
            return True
        for plugin_name in req.plugin_names:
            plugin = (
                session.query(Plugin)
                .filter(
                    Plugin.name == plugin_name,
                    Plugin.is_deleted.is_(False),
                )
                .first()
            )
            if plugin is None:
                return False
            if getattr(plugin, "status", None) != PluginStatusEnum.ENABLED.value:
                return False
            if not cls._plugin_scope_allows_tenant_sync(session, plugin, tenant_id):
                return False
            if not cls._plugin_license_allows_sync(session, plugin):
                return False
        return True


__all__ = [
    "TaskTenantEligibilityRequirements",
    "TaskTenantEligibilityResult",
    "TaskTenantEligibilityService",
]
