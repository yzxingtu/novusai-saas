"""Tenant binding services. / 租户计费绑定服务。"""

from __future__ import annotations

import inspect
from collections.abc import Mapping
from typing import Any

from sqlalchemy import desc, func, select

from app.core.base_model import utc_now
from app.core.i18n import _
from app.exceptions import BusinessException, NotFoundException

from ..constants import EXCLUDED_DRIVERS, SUPPORTED_CLOUD_DRIVERS
from ..models import (
    StorageBillingModeEnum,
    StorageBillingScopeTypeEnum,
    StorageBillingValidationStatusEnum,
    StorageProviderCodeEnum,
    StorageTenantBinding,
)
from .profile_service import StorageBillingProviderProfileService
from .reconciliation_service import _get_plugin_db

_SUPPORTED_MODES = {
    StorageBillingModeEnum.OFFICIAL_RECONCILED.value,
    StorageBillingModeEnum.OFFICIAL_PASS_THROUGH.value,
}
_SUPPORTED_SCOPE_TYPES = {
    StorageBillingScopeTypeEnum.BUCKET.value,
    StorageBillingScopeTypeEnum.DOMAIN.value,
    StorageBillingScopeTypeEnum.ACCOUNT.value,
    StorageBillingScopeTypeEnum.TAG.value,
}
_SUPPORTED_PROVIDER_CODES = {item.value for item in StorageProviderCodeEnum}


def _to_bool(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _stringify(value: Any) -> str:
    return str(value or "").strip()


class StorageBillingBindingService:
    """Tenant billing binding CRUD + validation service.
    / 租户账单绑定 CRUD 与校验服务。
    """

    def __init__(self, ctx, *, host_read=None) -> None:
        self._ctx = ctx
        self._db = _get_plugin_db(ctx)
        self._host_read = (
            host_read if host_read is not None else getattr(ctx, "host", None)
        )
        self._profile_service = StorageBillingProviderProfileService(
            ctx,
            host_read=self._host_read,
        )

    @classmethod
    def from_context(cls, ctx) -> StorageBillingBindingService:
        return cls(ctx, host_read=getattr(ctx, "host", None))

    async def list_bindings(self, request) -> dict[str, Any]:
        page = max(1, int(request.query_params.get("page[number]", "1")))
        size = min(100, max(1, int(request.query_params.get("page[size]", "20"))))
        tenant_id = request.query_params.get(
            "filter[tenant_id][eq]"
        ) or request.query_params.get("tenant_id")
        provider_code = request.query_params.get(
            "filter[provider_code][eq]"
        ) or request.query_params.get("provider_code")
        validation_status = request.query_params.get(
            "filter[validation_status][eq]"
        ) or request.query_params.get("validation_status")
        is_active = request.query_params.get(
            "filter[is_active][eq]"
        ) or request.query_params.get("is_active")

        query = select(StorageTenantBinding).where(
            StorageTenantBinding.is_deleted.is_(False)
        )
        count_query = select(func.count(StorageTenantBinding.id)).where(
            StorageTenantBinding.is_deleted.is_(False)
        )

        if tenant_id:
            tenant_id_int = int(tenant_id)
            query = query.where(StorageTenantBinding.tenant_id == tenant_id_int)
            count_query = count_query.where(
                StorageTenantBinding.tenant_id == tenant_id_int
            )
        if provider_code:
            normalized_provider = _stringify(provider_code)
            query = query.where(
                StorageTenantBinding.provider_code == normalized_provider
            )
            count_query = count_query.where(
                StorageTenantBinding.provider_code == normalized_provider
            )
        if validation_status:
            normalized_status = _stringify(validation_status)
            query = query.where(
                StorageTenantBinding.validation_status == normalized_status
            )
            count_query = count_query.where(
                StorageTenantBinding.validation_status == normalized_status
            )
        if is_active is not None and _stringify(is_active):
            active_value = _to_bool(is_active)
            query = query.where(StorageTenantBinding.is_active.is_(active_value))
            count_query = count_query.where(
                StorageTenantBinding.is_active.is_(active_value)
            )

        total = int((await self._db.execute(count_query)).scalar_one() or 0)
        result = await self._db.execute(
            query.order_by(
                desc(StorageTenantBinding.updated_at), desc(StorageTenantBinding.id)
            )
            .offset((page - 1) * size)
            .limit(size)
        )
        items = [self._serialize_binding(item) for item in result.scalars().all()]
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": size,
        }

    async def create_binding(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = self._normalize_binding_payload(payload)
        await self._assert_binding_not_exists(
            tenant_id=data["tenant_id"],
            provider_code=data["provider_code"],
            scope_type=data["scope_type"],
            scope_value=data["scope_value"],
        )

        tenant_snapshot = await self._get_tenant_snapshot(data["tenant_id"])
        validation = await self._validate_binding_data(
            data, tenant_snapshot=tenant_snapshot
        )

        instance = StorageTenantBinding(
            tenant_id=data["tenant_id"],
            provider_code=data["provider_code"],
            driver_code=data["driver_code"],
            provider_profile_code=data["provider_profile_code"],
            billing_mode=data["billing_mode"],
            scope_type=data["scope_type"],
            scope_value=data["scope_value"],
            bucket_name=data["bucket_name"],
            domain_name=data["domain_name"],
            account_identifier=data["account_identifier"],
            tag_key=data["tag_key"],
            tag_value=data["tag_value"],
            validation_status=validation["validation_status"],
            validation_message=validation["validation_message"],
            entitlement_snapshot_json=self._build_entitlement_snapshot(tenant_snapshot),
            metadata_json=dict(data.get("metadata_json") or {}),
            is_active=data["is_active"],
            validated_at=validation["validated_at"],
        )
        self._db.add(instance)
        await self._db.flush()
        await self._maybe_refresh(instance)
        return self._build_mutation_result(instance, validation)

    async def update_binding(
        self, binding_id: int, payload: dict[str, Any]
    ) -> dict[str, Any]:
        instance = await self._get_binding(binding_id)
        data = self._normalize_binding_payload(payload, current=instance)

        duplicate = await self._find_existing_binding(
            tenant_id=data["tenant_id"],
            provider_code=data["provider_code"],
            scope_type=data["scope_type"],
            scope_value=data["scope_value"],
        )
        if duplicate is not None and duplicate.id != instance.id:
            raise BusinessException(
                message=_(
                    "A binding with the same tenant/provider/scope already exists."
                )
            )

        tenant_snapshot = await self._get_tenant_snapshot(data["tenant_id"])
        validation = await self._validate_binding_data(
            data, tenant_snapshot=tenant_snapshot
        )

        instance.tenant_id = data["tenant_id"]
        instance.provider_code = data["provider_code"]
        instance.driver_code = data["driver_code"]
        instance.provider_profile_code = data["provider_profile_code"]
        instance.billing_mode = data["billing_mode"]
        instance.scope_type = data["scope_type"]
        instance.scope_value = data["scope_value"]
        instance.bucket_name = data["bucket_name"]
        instance.domain_name = data["domain_name"]
        instance.account_identifier = data["account_identifier"]
        instance.tag_key = data["tag_key"]
        instance.tag_value = data["tag_value"]
        instance.validation_status = validation["validation_status"]
        instance.validation_message = validation["validation_message"]
        instance.entitlement_snapshot_json = self._build_entitlement_snapshot(
            tenant_snapshot
        )
        instance.metadata_json = dict(data.get("metadata_json") or {})
        instance.is_active = data["is_active"]
        instance.validated_at = validation["validated_at"]
        await self._db.flush()
        await self._maybe_refresh(instance)
        return self._build_mutation_result(instance, validation)

    async def validate_binding(self, binding_id: int) -> dict[str, Any]:
        instance = await self._get_binding(binding_id)
        tenant_snapshot = await self._get_tenant_snapshot(instance.tenant_id)
        data = self._normalize_binding_payload(
            {
                "tenant_id": instance.tenant_id,
                "provider_code": instance.provider_code,
                "driver_code": instance.driver_code,
                "provider_profile_code": instance.provider_profile_code,
                "billing_mode": instance.billing_mode,
                "scope_type": instance.scope_type,
                "scope_value": instance.scope_value,
                "bucket_name": instance.bucket_name,
                "domain_name": instance.domain_name,
                "account_identifier": instance.account_identifier,
                "tag_key": instance.tag_key,
                "tag_value": instance.tag_value,
                "metadata_json": dict(instance.metadata_json or {}),
                "is_active": instance.is_active,
            }
        )
        validation = await self._validate_binding_data(
            data, tenant_snapshot=tenant_snapshot
        )
        instance.validation_status = validation["validation_status"]
        instance.validation_message = validation["validation_message"]
        instance.entitlement_snapshot_json = self._build_entitlement_snapshot(
            tenant_snapshot
        )
        instance.validated_at = validation["validated_at"]
        await self._db.flush()
        await self._maybe_refresh(instance)
        return self._build_mutation_result(instance, validation)

    async def get_tenant_prerequisites(self, tenant_id: int) -> dict[str, Any]:
        tenant_snapshot = await self._get_tenant_snapshot(tenant_id)
        storage_context = await self._get_tenant_storage_context(tenant_id)
        platform_storage_context = await self._get_platform_storage_context()
        billing_storage_context = self._resolve_billing_storage_context(
            storage_context,
            platform_storage_context,
        )
        provider_profiles = await self._profile_service.list_provider_profiles()

        result = await self._db.execute(
            select(StorageTenantBinding)
            .where(
                StorageTenantBinding.tenant_id == tenant_id,
                StorageTenantBinding.is_deleted.is_(False),
            )
            .order_by(
                desc(StorageTenantBinding.is_active),
                desc(StorageTenantBinding.updated_at),
                desc(StorageTenantBinding.id),
            )
        )
        bindings = [self._serialize_binding(item) for item in result.scalars().all()]

        plan = dict(tenant_snapshot.get("plan") or {})
        features = dict(plan.get("features") or {})
        tenant_storage_mode = (
            _stringify(storage_context.get("storage_mode")) or "platform"
        )
        tenant_storage_config = dict(storage_context.get("storage_config") or {})
        tenant_effective_driver = _stringify(tenant_storage_config.get("driver"))
        billing_storage_config = dict(
            billing_storage_context.get("storage_config") or {}
        )
        current_driver = _stringify(billing_storage_config.get("driver"))
        feature_enabled = _to_bool(features.get("storage_billing_enabled"))
        provider_map = dict(provider_profiles.get("providers") or {})
        validation_map = dict(provider_profiles.get("validations") or {})
        current_provider_profile = dict(provider_map.get(current_driver) or {})
        current_provider_validation = dict(validation_map.get(current_driver) or {})
        active_bindings = [item for item in bindings if item["is_active"]]
        valid_active_bindings = [
            item
            for item in active_bindings
            if item["validation_status"]
            == StorageBillingValidationStatusEnum.VALID.value
        ]
        matching_active_bindings = [
            item for item in active_bindings if item["provider_code"] == current_driver
        ]
        valid_matching_bindings = [
            item
            for item in matching_active_bindings
            if item["validation_status"]
            == StorageBillingValidationStatusEnum.VALID.value
        ]

        missing_reasons: list[str] = []
        if not feature_enabled:
            missing_reasons.append("plan_feature_disabled")
        if tenant_storage_mode != "platform":
            missing_reasons.append("tenant_not_using_platform_storage")
        elif not current_driver:
            missing_reasons.append("current_driver_unsupported")
        elif current_driver in EXCLUDED_DRIVERS:
            missing_reasons.append("current_driver_not_billable")
        elif current_driver and current_driver not in SUPPORTED_CLOUD_DRIVERS:
            missing_reasons.append("current_driver_unsupported")
        elif current_driver:
            if not _to_bool(current_provider_profile.get("enabled")):
                missing_reasons.append("provider_profile_disabled")
            elif list(current_provider_validation.get("errors") or []):
                missing_reasons.append("provider_profile_invalid")
            elif (
                current_provider_profile.get("driver_enabled") is False
                or current_provider_validation.get("driver_enabled") is False
            ):
                missing_reasons.append("driver_plugin_disabled")
            elif not active_bindings:
                missing_reasons.append("binding_missing")
            elif not matching_active_bindings:
                missing_reasons.append("binding_provider_mismatch")
            elif not valid_matching_bindings:
                missing_reasons.append("binding_invalid")
        elif not active_bindings:
            missing_reasons.append("binding_missing")

        provider_capabilities = {
            provider: {
                "settlement_mode": dict(profile).get("settlement_mode"),
                "settlement_cycle": dict(profile).get("settlement_cycle"),
                "strict_reconciliation_supported": dict(profile).get(
                    "strict_reconciliation_supported"
                ),
                "manual_pull_supported": dict(profile).get("manual_pull_supported"),
                "scheduled_daily_supported": dict(profile).get(
                    "scheduled_daily_supported"
                ),
                "supported_period_types": list(
                    dict(profile).get("supported_period_types") or []
                ),
                "official_billing_lag_days": dict(profile).get(
                    "official_billing_lag_days"
                ),
                "official_target_rule": dict(profile).get("official_target_rule"),
                "capability_message": dict(profile).get("capability_message"),
                "recommended_scope_types": list(
                    dict(profile).get("recommended_scope_types") or []
                ),
            }
            for provider, profile in dict(
                provider_profiles.get("providers") or {}
            ).items()
            if current_driver and provider == current_driver
        }

        return {
            "ok": True,
            "tenant_id": tenant_id,
            "plan": {
                "plan_id": tenant_snapshot.get("plan_id"),
                "code": plan.get("code"),
                "name": plan.get("name"),
                "storage_billing_enabled": feature_enabled,
            },
            "storage_context": storage_context,
            "platform_storage_context": platform_storage_context,
            "provider_profiles": provider_profiles,
            "provider_capabilities": provider_capabilities,
            "bindings": {
                "items": bindings,
                "total": len(bindings),
                "active_total": len(active_bindings),
                "valid_active_total": len(valid_active_bindings),
                "matching_active_total": len(matching_active_bindings),
                "ready_total": len(valid_matching_bindings),
            },
            "prerequisites": {
                "ready": feature_enabled and not missing_reasons,
                "feature_enabled": feature_enabled,
                "current_driver": current_driver,
                "current_driver_billable": current_driver in SUPPORTED_CLOUD_DRIVERS,
                "tenant_effective_driver": tenant_effective_driver,
                "tenant_storage_mode": tenant_storage_mode,
                "charge_local_storage": False,
                "missing_reasons": missing_reasons,
            },
        }

    async def ensure_tenant_billing_ready(self, tenant_id: int) -> dict[str, Any]:
        result = await self.get_tenant_prerequisites(tenant_id)
        prerequisites = dict(result.get("prerequisites") or {})
        if prerequisites.get("ready"):
            return result

        raise BusinessException(
            message=_("Storage billing is not ready for the current tenant."),
            data={
                "current_driver": prerequisites.get("current_driver"),
                "missing_reasons": list(prerequisites.get("missing_reasons") or []),
                "tenant_effective_driver": prerequisites.get("tenant_effective_driver"),
                "tenant_id": tenant_id,
                "tenant_storage_mode": prerequisites.get("tenant_storage_mode"),
            },
        )

    async def _maybe_refresh(self, instance: StorageTenantBinding) -> None:
        refresh = getattr(self._db, "refresh", None)
        if not callable(refresh):
            return
        maybe_result = refresh(instance)
        if inspect.iscoroutine(maybe_result):
            await maybe_result

    async def _get_binding(self, binding_id: int) -> StorageTenantBinding:
        result = await self._db.execute(
            select(StorageTenantBinding).where(
                StorageTenantBinding.id == binding_id,
                StorageTenantBinding.is_deleted.is_(False),
            )
        )
        binding = result.scalar_one_or_none()
        if binding is None:
            raise NotFoundException(message=_("Storage billing binding not found."))
        return binding

    async def _assert_binding_not_exists(
        self,
        *,
        tenant_id: int,
        provider_code: str,
        scope_type: str,
        scope_value: str,
    ) -> None:
        existing = await self._find_existing_binding(
            tenant_id=tenant_id,
            provider_code=provider_code,
            scope_type=scope_type,
            scope_value=scope_value,
        )
        if existing is not None:
            raise BusinessException(
                message=_(
                    "A binding with the same tenant/provider/scope already exists."
                )
            )

    async def _find_existing_binding(
        self,
        *,
        tenant_id: int,
        provider_code: str,
        scope_type: str,
        scope_value: str,
    ) -> StorageTenantBinding | None:
        result = await self._db.execute(
            select(StorageTenantBinding).where(
                StorageTenantBinding.tenant_id == tenant_id,
                StorageTenantBinding.provider_code == provider_code,
                StorageTenantBinding.scope_type == scope_type,
                StorageTenantBinding.scope_value == scope_value,
                StorageTenantBinding.is_deleted.is_(False),
            )
        )
        return result.scalar_one_or_none()

    async def _get_tenant_snapshot(self, tenant_id: int) -> dict[str, Any]:
        if self._host_read is None:
            raise BusinessException(
                message=_("Storage billing host facade is unavailable.")
            )
        snapshot = await self._host_read.get_tenant_plan_snapshot(tenant_id)
        if snapshot is None:
            raise BusinessException(message=_("Tenant does not exist."))
        return snapshot

    async def _get_tenant_storage_context(self, tenant_id: int) -> dict[str, Any]:
        if self._host_read is None:
            return {}
        reader = getattr(self._host_read, "get_tenant_storage_context", None)
        if not callable(reader):
            return {}
        payload = reader(tenant_id)
        if inspect.isawaitable(payload):
            payload = await payload
        if not isinstance(payload, Mapping):
            return {}
        return dict(payload)

    async def _get_platform_storage_context(self) -> dict[str, Any]:
        if self._host_read is None:
            return {}
        reader = getattr(self._host_read, "get_platform_storage_context", None)
        if not callable(reader):
            return {}
        payload = reader()
        if inspect.isawaitable(payload):
            payload = await payload
        if not isinstance(payload, Mapping):
            return {}
        return dict(payload)

    @staticmethod
    def _resolve_billing_storage_context(
        tenant_storage_context: Mapping[str, Any] | None,
        platform_storage_context: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        _ = tenant_storage_context
        # Phase-1 billing is defined against platform-managed storage only. The
        # tenant storage context decides eligibility, but the driver used for
        # readiness/validation must stay aligned with reconciliation.
        return dict(platform_storage_context or {})

    async def _validate_binding_data(
        self,
        data: dict[str, Any],
        *,
        tenant_snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        errors: list[str] = []
        warnings: list[str] = []

        plan = dict(tenant_snapshot.get("plan") or {})
        features = dict(plan.get("features") or {})
        if not _to_bool(features.get("storage_billing_enabled")):
            errors.append(_("Tenant plan does not enable storage billing."))

        provider_profile = await self._profile_service.get_provider_runtime_profile(
            data["provider_code"]
        )
        if not _to_bool(provider_profile.get("enabled")):
            errors.append(_("Provider profile is not enabled."))
        if data["provider_profile_code"] != _stringify(
            provider_profile.get("profile_code")
        ):
            errors.append(
                _("Provider profile code does not match the active configured profile.")
            )
        if provider_profile.get("driver_enabled") is False:
            errors.append(_("The corresponding storage driver plugin is not enabled."))

        profile_validation = await self._profile_service.validate_provider_profile(
            data["provider_code"]
        )
        errors.extend(profile_validation["errors"])
        warnings.extend(profile_validation["warnings"])

        tenant_storage_context = await self._get_tenant_storage_context(
            data["tenant_id"]
        )
        tenant_storage_mode = (
            _stringify(tenant_storage_context.get("storage_mode")) or "platform"
        )
        platform_storage_context = await self._get_platform_storage_context()
        billing_storage_context = self._resolve_billing_storage_context(
            tenant_storage_context,
            platform_storage_context,
        )
        current_driver = _stringify(
            dict(billing_storage_context.get("storage_config") or {}).get("driver")
        )
        if tenant_storage_mode != "platform":
            errors.append(_("Tenant is not using platform-managed storage."))
        elif not current_driver:
            errors.append(_("Current platform storage driver is unsupported."))
        elif current_driver in EXCLUDED_DRIVERS:
            errors.append(_("Current platform storage driver is not billable."))
        elif current_driver and current_driver not in SUPPORTED_CLOUD_DRIVERS:
            errors.append(_("Current platform storage driver is unsupported."))
        elif current_driver and current_driver != data["provider_code"]:
            errors.append(
                _(
                    "Tenant current storage driver does not match the billing binding provider."
                )
            )

        if (
            data["provider_code"] == StorageProviderCodeEnum.QINIU_KODO.value
            and data["scope_type"] != StorageBillingScopeTypeEnum.ACCOUNT.value
        ):
            errors.append(
                _("Qiniu monthly settled billing currently requires account scope.")
            )

        if (
            data["provider_code"] == StorageProviderCodeEnum.QINIU_KODO.value
            and data["billing_mode"]
            == StorageBillingModeEnum.OFFICIAL_PASS_THROUGH.value
        ):
            errors.append(_("Qiniu official_pass_through is not supported in phase 1."))

        if (
            data["provider_code"] == StorageProviderCodeEnum.TENCENT_COS.value
            and data["billing_mode"]
            == StorageBillingModeEnum.OFFICIAL_PASS_THROUGH.value
            and data["scope_type"] != StorageBillingScopeTypeEnum.BUCKET.value
        ):
            errors.append(
                _(
                    "Tencent COS official_pass_through mode currently requires bucket scope."
                )
            )

        message = "; ".join(errors or warnings) or _("Binding validation is pending.")
        status = (
            StorageBillingValidationStatusEnum.VALID.value
            if not errors
            else StorageBillingValidationStatusEnum.INVALID.value
        )
        return {
            "validation_status": status,
            "validation_message": message,
            "status": status,
            "message": message,
            "errors": errors,
            "warnings": warnings,
            "validated_at": utc_now(),
        }

    def _normalize_binding_payload(
        self,
        payload: dict[str, Any],
        *,
        current: StorageTenantBinding | None = None,
    ) -> dict[str, Any]:
        provider_code = _stringify(
            payload.get("provider_code")
            if payload.get("provider_code") is not None
            else getattr(current, "provider_code", "")
        )
        if provider_code not in _SUPPORTED_PROVIDER_CODES:
            raise BusinessException(message=_("Unsupported provider code."))

        scope_type = _stringify(
            payload.get("scope_type")
            if payload.get("scope_type") is not None
            else getattr(current, "scope_type", "")
        )
        if scope_type not in _SUPPORTED_SCOPE_TYPES:
            raise BusinessException(message=_("Unsupported binding scope type."))

        billing_mode = _stringify(
            payload.get("billing_mode")
            if payload.get("billing_mode") is not None
            else getattr(
                current,
                "billing_mode",
                StorageBillingModeEnum.OFFICIAL_RECONCILED.value,
            )
        )
        if billing_mode not in _SUPPORTED_MODES:
            raise BusinessException(message=_("Unsupported billing mode."))

        tenant_id = int(
            payload.get("tenant_id")
            if payload.get("tenant_id") is not None
            else getattr(current, "tenant_id", 0)
        )
        if tenant_id <= 0:
            raise BusinessException(message=_("tenant_id is required."))

        scope_value = _stringify(
            payload.get("scope_value")
            if payload.get("scope_value") is not None
            else getattr(current, "scope_value", "")
        )
        bucket_name = self._coalesce_scope_value(payload, current, "bucket_name")
        domain_name = self._coalesce_scope_value(payload, current, "domain_name")
        account_identifier = self._coalesce_scope_value(
            payload, current, "account_identifier"
        )
        tag_key = self._coalesce_scope_value(payload, current, "tag_key")
        tag_value = self._coalesce_scope_value(payload, current, "tag_value")

        if scope_type == StorageBillingScopeTypeEnum.BUCKET.value:
            scope_value = bucket_name or scope_value
            bucket_name = scope_value
            if not scope_value:
                raise BusinessException(
                    message=_("bucket_name is required for bucket scope.")
                )
            domain_name = ""
            account_identifier = ""
            tag_key = ""
            tag_value = ""
        elif scope_type == StorageBillingScopeTypeEnum.DOMAIN.value:
            scope_value = domain_name or scope_value
            domain_name = scope_value
            if not scope_value:
                raise BusinessException(
                    message=_("domain_name is required for domain scope.")
                )
            bucket_name = ""
            account_identifier = ""
            tag_key = ""
            tag_value = ""
        elif scope_type == StorageBillingScopeTypeEnum.ACCOUNT.value:
            scope_value = account_identifier or scope_value
            account_identifier = scope_value
            if not scope_value:
                raise BusinessException(
                    message=_("account_identifier is required for account scope.")
                )
            bucket_name = ""
            domain_name = ""
            tag_key = ""
            tag_value = ""
        else:
            if not tag_key or not tag_value:
                raise BusinessException(
                    message=_("tag_key and tag_value are required for tag scope.")
                )
            scope_value = scope_value or f"{tag_key}:{tag_value}"
            bucket_name = ""
            domain_name = ""
            account_identifier = ""

        driver_code = (
            _stringify(
                payload.get("driver_code")
                if payload.get("driver_code") is not None
                else getattr(current, "driver_code", provider_code)
            )
            or provider_code
        )
        if driver_code != provider_code:
            raise BusinessException(
                message=_("driver_code must match provider_code in phase one.")
            )

        provider_profile_code = _stringify(
            payload.get("provider_profile_code")
            if payload.get("provider_profile_code") is not None
            else getattr(current, "provider_profile_code", "")
        )
        if not provider_profile_code:
            provider_profile_code = self._default_profile_code(provider_code)

        metadata_json = payload.get("metadata_json")
        if metadata_json is None and current is not None:
            metadata_json = dict(current.metadata_json or {})

        is_active = (
            _to_bool(payload.get("is_active"))
            if payload.get("is_active") is not None
            else bool(getattr(current, "is_active", True))
        )

        return {
            "tenant_id": tenant_id,
            "provider_code": provider_code,
            "driver_code": driver_code,
            "provider_profile_code": provider_profile_code,
            "billing_mode": billing_mode,
            "scope_type": scope_type,
            "scope_value": scope_value,
            "bucket_name": bucket_name or None,
            "domain_name": domain_name or None,
            "account_identifier": account_identifier or None,
            "tag_key": tag_key or None,
            "tag_value": tag_value or None,
            "metadata_json": dict(metadata_json or {}),
            "is_active": is_active,
        }

    def _coalesce_scope_value(
        self,
        payload: dict[str, Any],
        current: StorageTenantBinding | None,
        field: str,
    ) -> str:
        if payload.get(field) is not None:
            return _stringify(payload.get(field))
        return _stringify(getattr(current, field, ""))

    def _default_profile_code(self, provider_code: str) -> str:
        prefix_map = {
            StorageProviderCodeEnum.QINIU_KODO.value: "qiniu-default",
            StorageProviderCodeEnum.ALIYUN_OSS.value: "aliyun-default",
            StorageProviderCodeEnum.TENCENT_COS.value: "tencent-default",
        }
        return prefix_map[provider_code]

    def _build_entitlement_snapshot(
        self, tenant_snapshot: dict[str, Any]
    ) -> dict[str, Any]:
        plan = dict(tenant_snapshot.get("plan") or {})
        features = dict(plan.get("features") or {})
        return {
            "tenant_id": tenant_snapshot.get("tenant_id"),
            "tenant_code": tenant_snapshot.get("tenant_code"),
            "tenant_name": tenant_snapshot.get("tenant_name"),
            "plan_id": tenant_snapshot.get("plan_id"),
            "plan_code": plan.get("code"),
            "plan_name": plan.get("name"),
            "storage_billing_enabled": _to_bool(
                features.get("storage_billing_enabled")
            ),
        }

    def _build_mutation_result(
        self,
        row: StorageTenantBinding,
        validation: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "ok": True,
            "binding": self._serialize_binding(row),
            "validation": validation,
        }

    def _serialize_binding(self, row: StorageTenantBinding) -> dict[str, Any]:
        return {
            "id": row.id,
            "binding_key": row.binding_key,
            "tenant_id": row.tenant_id,
            "provider_code": row.provider_code,
            "driver_code": row.driver_code,
            "provider_profile_code": row.provider_profile_code,
            "billing_mode": row.billing_mode,
            "scope_type": row.scope_type,
            "scope_value": row.scope_value,
            "bucket_name": row.bucket_name,
            "domain_name": row.domain_name,
            "account_identifier": row.account_identifier,
            "tag_key": row.tag_key,
            "tag_value": row.tag_value,
            "validation_status": row.validation_status,
            "validation_message": row.validation_message,
            "entitlement_snapshot": dict(row.entitlement_snapshot_json or {}),
            "metadata": dict(row.metadata_json or {}),
            "is_active": bool(row.is_active),
            "validated_at": row.validated_at.isoformat() if row.validated_at else None,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }


__all__ = ["StorageBillingBindingService"]
