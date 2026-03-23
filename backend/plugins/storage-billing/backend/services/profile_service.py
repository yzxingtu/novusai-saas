"""Provider profile services for storage billing plugin."""

from __future__ import annotations

import inspect
from collections.abc import Mapping
from typing import Any

from app.core.i18n import _
from app.exceptions import BusinessException

from ..constants import (
    COLLECTOR_IMPLEMENTATION_STATUS,
    DEFAULT_PROVIDER_PROFILES,
    PROVIDER_BILL_SOURCES,
    PROVIDER_SECRET_FIELDS,
    SUPPORTED_CLOUD_DRIVERS,
    get_provider_bill_source_capability,
    get_provider_implemented_bill_sources,
    get_provider_required_fields,
    get_default_provider_profiles,
)

_LEGACY_FLAT_FIELD_MAP: dict[str, dict[str, str]] = {
    "qiniu-kodo": {
        "enabled": "qiniu_enabled",
        "profile_code": "qiniu_profile_code",
        "bill_source": "qiniu_bill_source",
        "access_key": "qiniu_access_key",
        "secret_key": "qiniu_secret_key",
        "account_identifier": "qiniu_account_identifier",
    },
    "aliyun-oss": {
        "enabled": "aliyun_enabled",
        "profile_code": "aliyun_profile_code",
        "bill_source": "aliyun_bill_source",
        "region": "aliyun_region",
        "access_key_id": "aliyun_access_key_id",
        "access_key_secret": "aliyun_access_key_secret",
        "bill_bucket": "aliyun_bill_bucket",
        "bill_prefix": "aliyun_bill_prefix",
        "account_identifier": "aliyun_account_identifier",
    },
    "tencent-cos": {
        "enabled": "tencent_enabled",
        "profile_code": "tencent_profile_code",
        "bill_source": "tencent_bill_source",
        "region": "tencent_region",
        "secret_id": "tencent_secret_id",
        "secret_key": "tencent_secret_key",
        "bill_bucket": "tencent_bill_bucket",
        "bill_prefix": "tencent_bill_prefix",
        "account_identifier": "tencent_account_identifier",
    },
}


def _stringify(value: Any) -> str:
    return str(value or "").strip()


def _to_bool(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _configured_secret_fields(provider: str, profile: dict[str, Any]) -> dict[str, bool]:
    return {
        field: bool(_stringify(profile.get(field)))
        for field in PROVIDER_SECRET_FIELDS.get(provider) or []
    }


def _normalize_provider_profiles(raw_config: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    profiles = get_default_provider_profiles()
    raw = dict(raw_config or {})
    source_profiles = raw.get("providers")
    source_profiles = dict(source_profiles or {}) if isinstance(source_profiles, dict) else {}

    for provider in SUPPORTED_CLOUD_DRIVERS:
        current = dict(profiles.get(provider) or {})
        nested_profile = source_profiles.get(provider)
        if isinstance(nested_profile, dict):
            current.update(nested_profile)

        for field, legacy_key in (_LEGACY_FLAT_FIELD_MAP.get(provider) or {}).items():
            if field in current and nested_profile is not None and field in nested_profile:
                continue
            if legacy_key in raw:
                current[field] = raw.get(legacy_key)

        current["enabled"] = _to_bool(current.get("enabled"))
        current["profile_code"] = _stringify(current.get("profile_code")) or _stringify(
            DEFAULT_PROVIDER_PROFILES.get(provider, {}).get("profile_code")
        )
        current["bill_source"] = _stringify(current.get("bill_source")) or _stringify(
            DEFAULT_PROVIDER_PROFILES.get(provider, {}).get("bill_source")
        )
        profiles[provider] = current

    return profiles


def _merge_profile(
    provider: str,
    current: dict[str, Any],
    incoming: dict[str, Any] | None,
) -> dict[str, Any]:
    result = dict(DEFAULT_PROVIDER_PROFILES.get(provider) or {})
    result.update(current or {})
    patch = dict(incoming or {})
    secret_fields = set(PROVIDER_SECRET_FIELDS.get(provider) or [])

    for key, value in patch.items():
        if key == "enabled":
            result[key] = _to_bool(value)
            continue

        if key in secret_fields:
            if value is None:
                result[key] = ""
            elif isinstance(value, str) and not value.strip():
                continue
            else:
                result[key] = value.strip() if isinstance(value, str) else value
            continue

        if isinstance(value, str):
            result[key] = value.strip()
        else:
            result[key] = value

    result["enabled"] = _to_bool(result.get("enabled"))
    result["profile_code"] = _stringify(result.get("profile_code")) or _stringify(
        DEFAULT_PROVIDER_PROFILES.get(provider, {}).get("profile_code")
    )
    result["bill_source"] = _stringify(result.get("bill_source")) or _stringify(
        DEFAULT_PROVIDER_PROFILES.get(provider, {}).get("bill_source")
    )
    return result


def _build_runtime_profile(
    provider: str,
    profile: dict[str, Any],
    *,
    driver_plugin_enabled: bool | None,
) -> dict[str, Any]:
    runtime = dict(profile)
    runtime["enabled"] = _to_bool(runtime.get("enabled"))
    runtime["profile_code"] = _stringify(runtime.get("profile_code")) or _stringify(
        DEFAULT_PROVIDER_PROFILES.get(provider, {}).get("profile_code")
    )
    runtime["bill_source"] = _stringify(runtime.get("bill_source")) or _stringify(
        DEFAULT_PROVIDER_PROFILES.get(provider, {}).get("bill_source")
    )
    selected_bill_source = _stringify(runtime.get("bill_source"))
    runtime["driver_enabled"] = driver_plugin_enabled
    runtime["supported_bill_sources"] = list(PROVIDER_BILL_SOURCES.get(provider) or [])
    runtime["required_fields"] = get_provider_required_fields(
        provider,
        selected_bill_source,
    )
    capability = get_provider_bill_source_capability(provider, selected_bill_source)
    runtime["configured_fields"] = _configured_secret_fields(provider, runtime)
    runtime["configured_secret_fields"] = dict(runtime["configured_fields"])
    implemented_sources = get_provider_implemented_bill_sources(provider)
    runtime["collector_ready"] = (
        bool(COLLECTOR_IMPLEMENTATION_STATUS.get(provider, False))
        and selected_bill_source in implemented_sources
    )
    runtime["settlement_mode"] = _stringify(capability.get("settlement_mode")) or "unsupported"
    runtime["settlement_cycle"] = _stringify(capability.get("settlement_cycle")) or "daily"
    runtime["strict_reconciliation_supported"] = bool(
        capability.get("strict_daily_reconciliation_supported", False)
    )
    runtime["manual_pull_supported"] = bool(
        capability.get("manual_pull_supported", False)
    )
    runtime["scheduled_daily_supported"] = bool(
        capability.get("scheduled_daily_supported", False)
    )
    runtime["supported_period_types"] = list(capability.get("supported_period_types") or [])
    runtime["recommended_scope_types"] = list(
        capability.get("recommended_scope_types") or []
    )
    runtime["capability_message"] = _stringify(capability.get("capability_message"))
    runtime["implemented"] = bool(capability.get("implemented", False))
    return runtime


def _serialize_profile(
    provider: str,
    runtime_profile: dict[str, Any],
    *,
    include_secret_placeholders: bool,
) -> dict[str, Any]:
    payload = dict(runtime_profile)
    if include_secret_placeholders:
        for field in PROVIDER_SECRET_FIELDS.get(provider) or []:
            payload[field] = ""
    else:
        for field in PROVIDER_SECRET_FIELDS.get(provider) or []:
            payload.pop(field, None)
    return payload


def build_provider_validation(
    provider: str,
    profile: dict[str, Any],
    *,
    driver_plugin_enabled: bool | None,
) -> dict[str, Any]:
    runtime_profile = _build_runtime_profile(
        provider,
        profile,
        driver_plugin_enabled=driver_plugin_enabled,
    )
    errors: list[str] = []
    warnings: list[str] = []
    enabled = bool(runtime_profile.get("enabled"))
    bill_source = _stringify(runtime_profile.get("bill_source"))
    implemented_sources = get_provider_implemented_bill_sources(provider)
    required_fields = get_provider_required_fields(provider, bill_source)
    capability = get_provider_bill_source_capability(provider, bill_source)

    if provider not in SUPPORTED_CLOUD_DRIVERS:
        errors.append(_("Unsupported provider."))

    if enabled:
        for field in required_fields:
            if not _stringify(runtime_profile.get(field)):
                errors.append(_(f"Missing required field: {field}"))

        allowed_sources = PROVIDER_BILL_SOURCES.get(provider) or []
        if bill_source and bill_source not in allowed_sources:
            errors.append(
                _(f"Unsupported bill source '{bill_source}' for provider '{provider}'.")
            )

        if driver_plugin_enabled is False:
            errors.append(
                _(f"Required storage driver plugin '{provider}' is not enabled.")
            )

        if bill_source and bill_source not in implemented_sources:
            errors.append(
                _(f"Selected bill source '{bill_source}' is not implemented yet.")
            )

    if not implemented_sources:
        warnings.append(_("Official bill collector is not implemented yet."))
    if _stringify(capability.get("capability_message")) and not bool(
        capability.get("strict_daily_reconciliation_supported", False)
    ):
        warnings.append(_(capability["capability_message"]))

    status = "valid" if not errors else "invalid"
    return {
        "provider": provider,
        "enabled": enabled,
        "profile_valid": not errors,
        "collector_ready": bill_source in implemented_sources,
        "status": status,
        "errors": errors,
        "warnings": warnings,
        "driver_plugin_enabled": driver_plugin_enabled,
        "driver_enabled": driver_plugin_enabled,
        "supported_bill_sources": list(PROVIDER_BILL_SOURCES.get(provider) or []),
        "required_fields": required_fields,
        "settlement_mode": _stringify(capability.get("settlement_mode")) or "unsupported",
        "settlement_cycle": _stringify(capability.get("settlement_cycle")) or "daily",
        "strict_reconciliation_supported": bool(
            capability.get("strict_daily_reconciliation_supported", False)
        ),
        "manual_pull_supported": bool(capability.get("manual_pull_supported", False)),
        "scheduled_daily_supported": bool(
            capability.get("scheduled_daily_supported", False)
        ),
        "supported_period_types": list(capability.get("supported_period_types") or []),
        "recommended_scope_types": list(
            capability.get("recommended_scope_types") or []
        ),
        "capability_message": _stringify(capability.get("capability_message")),
    }


class StorageBillingProviderProfileService:
    """Plugin global provider-profile configuration service."""

    def __init__(self, ctx, *, host_read=None) -> None:
        self._ctx = ctx
        self._host_read = host_read if host_read is not None else getattr(ctx, "host", None)

    @classmethod
    def from_context(cls, ctx) -> "StorageBillingProviderProfileService":
        return cls(ctx, host_read=getattr(ctx, "host", None))

    async def _get_driver_plugin_enabled_map(self) -> dict[str, bool | None]:
        result: dict[str, bool | None] = {
            provider: None for provider in SUPPORTED_CLOUD_DRIVERS
        }
        if self._host_read is None:
            return result

        summary_reader = getattr(self._host_read, "get_plugin_runtime_summary", None)
        if callable(summary_reader):
            if inspect.iscoroutinefunction(summary_reader):
                summary = await summary_reader(SUPPORTED_CLOUD_DRIVERS)
            else:
                summary = summary_reader(SUPPORTED_CLOUD_DRIVERS)
            for item in summary or []:
                name = _stringify(item.get("name"))
                if name in result:
                    result[name] = bool(item.get("enabled"))

        if all(value is not None for value in result.values()):
            return result

        drivers_reader = getattr(self._host_read, "get_enabled_storage_drivers", None)
        if not callable(drivers_reader):
            return result

        if inspect.iscoroutinefunction(drivers_reader):
            drivers = await drivers_reader()
        else:
            drivers = drivers_reader()
        for item in drivers or []:
            code = _stringify(item.get("code"))
            if code not in result or result[code] is not None:
                continue
            is_available = bool(item.get("is_available", True))
            plugin_status = _stringify(item.get("plugin_status")).lower()
            result[code] = is_available and plugin_status in {"", "enabled"}

        return result

    async def _load_config(self) -> dict[str, Any]:
        get_config = getattr(self._ctx, "get_config", None)
        if not callable(get_config):
            return {}
        if inspect.iscoroutinefunction(get_config):
            config = await get_config()
        else:
            config = get_config()
        if not isinstance(config, Mapping):
            return {}
        return dict(config)

    async def _build_response(self, *, include_secret_placeholders: bool) -> dict[str, Any]:
        current_config = await self._load_config()
        profiles = _normalize_provider_profiles(current_config)
        enabled_map = await self._get_driver_plugin_enabled_map()

        runtime_profiles = {
            provider: _build_runtime_profile(
                provider,
                profile,
                driver_plugin_enabled=enabled_map.get(provider),
            )
            for provider, profile in profiles.items()
        }

        return {
            "providers": {
                provider: _serialize_profile(
                    provider,
                    runtime_profile,
                    include_secret_placeholders=include_secret_placeholders,
                )
                for provider, runtime_profile in runtime_profiles.items()
            },
            "validations": {
                provider: build_provider_validation(
                    provider,
                    profiles[provider],
                    driver_plugin_enabled=enabled_map.get(provider),
                )
                for provider in SUPPORTED_CLOUD_DRIVERS
            },
            "supported_providers": list(SUPPORTED_CLOUD_DRIVERS),
        }

    async def list_provider_profiles(self) -> dict[str, Any]:
        return await self._build_response(include_secret_placeholders=False)

    async def save_provider_profiles(self, payload: dict[str, Any]) -> dict[str, Any]:
        providers = dict(payload.get("providers") or {})
        if not providers:
            raise BusinessException(message=_("Provider profiles payload is empty."))

        unsupported = [
            provider for provider in providers if provider not in SUPPORTED_CLOUD_DRIVERS
        ]
        if unsupported:
            raise BusinessException(
                message=_(f"Unsupported providers: {', '.join(sorted(unsupported))}")
            )

        current_config = await self._load_config()
        current_profiles = _normalize_provider_profiles(current_config)
        merged_profiles: dict[str, dict[str, Any]] = {}
        for provider in SUPPORTED_CLOUD_DRIVERS:
            incoming = providers.get(provider)
            merged_profiles[provider] = _merge_profile(
                provider,
                current_profiles.get(provider) or {},
                incoming if isinstance(incoming, dict) else None,
            )

        legacy_keys = {
            legacy_key
            for mapping in _LEGACY_FLAT_FIELD_MAP.values()
            for legacy_key in mapping.values()
        }
        next_config = {
            key: value
            for key, value in current_config.items()
            if key != "providers" and key not in legacy_keys
        }
        next_config["providers"] = merged_profiles

        await self._ctx.update_config(next_config)
        return await self._build_response(include_secret_placeholders=True)

    async def validate_provider_profile(
        self,
        provider_code: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_provider = _stringify(provider_code)
        if normalized_provider not in SUPPORTED_CLOUD_DRIVERS:
            raise BusinessException(message=_(f"Unsupported provider: {provider_code}"))

        current_config = await self._load_config()
        profiles = _normalize_provider_profiles(current_config)
        if payload:
            profiles[normalized_provider] = _merge_profile(
                normalized_provider,
                profiles.get(normalized_provider) or {},
                dict(payload or {}),
            )

        enabled_map = await self._get_driver_plugin_enabled_map()
        validation = build_provider_validation(
            normalized_provider,
            profiles[normalized_provider],
            driver_plugin_enabled=enabled_map.get(normalized_provider),
        )
        runtime_profile = _build_runtime_profile(
            normalized_provider,
            profiles[normalized_provider],
            driver_plugin_enabled=enabled_map.get(normalized_provider),
        )
        return {
            **validation,
            "profile": _serialize_profile(
                normalized_provider,
                runtime_profile,
                include_secret_placeholders=True,
            ),
        }

    async def get_provider_runtime_profile(self, provider_code: str) -> dict[str, Any]:
        normalized_provider = _stringify(provider_code)
        profiles = _normalize_provider_profiles(await self._load_config())
        if normalized_provider not in profiles:
            raise BusinessException(message=_(f"Unsupported provider: {provider_code}"))
        enabled_map = await self._get_driver_plugin_enabled_map()
        return _build_runtime_profile(
            normalized_provider,
            profiles[normalized_provider],
            driver_plugin_enabled=enabled_map.get(normalized_provider),
        )


__all__ = [
    "StorageBillingProviderProfileService",
    "_normalize_provider_profiles",
    "build_provider_validation",
]
