"""Tenant config workflow service. / 企业配置控制器工作流服务。"""

from __future__ import annotations

import io
import uuid
from collections.abc import Iterable
from typing import Any

from app.captcha.provider import CaptchaProviderMetadata
from app.captcha.registry import registry as captcha_registry
from app.configs.registry import config_registry
from app.configs.service import ConfigService
from app.core.i18n import _, get_locale
from app.core.response import build_inline_error_result
from app.enums.config import ConfigScope
from app.enums.error_code import ErrorCode
from app.exceptions import BusinessException, NotFoundException
from app.plugins.preview import resolve_i18n
from app.schemas.system.config import (
    ConfigGroupResponse,
    ConfigItemResponse,
    DisplayRuleSchema,
)
from app.services.system.plugin_read_model_service import PluginReadModelService
from app.services.tenant.tenant_role_option_service import TenantRoleOptionService

_CAPTCHA_PROVIDER_CONFIG_KEYS = {"captcha_provider", "tenant_captcha_provider"}
_SENSITIVE_KEYWORDS = {"secret", "key", "password", "token"}


def _to_manifest_locale(locale: str) -> str:
    normalized = str(locale or "").strip()
    if normalized == "zh_CN":
        return "zh-CN"
    return normalized or "zh-CN"


def _resolve_provider_label(
    provider_code: str,
    metadata: CaptchaProviderMetadata | None,
) -> str:
    if metadata and metadata.display_name:
        return (
            resolve_i18n(
                metadata.display_name,
                locale=_to_manifest_locale(get_locale()),
            )
            or provider_code
        )
    return provider_code


def _supports_required_endpoints(
    provider_code: str,
    metadata: CaptchaProviderMetadata | None,
    required_endpoints: set[str],
) -> bool:
    if provider_code == "image":
        return True
    if not required_endpoints:
        return True

    endpoints = {
        str(item or "").strip().lower()
        for item in (metadata.public_endpoints if metadata else [])
    }
    return required_endpoints.issubset(endpoints)


def _inject_captcha_provider_options(
    configs: list[dict[str, Any]],
    *,
    required_endpoints: Iterable[str],
    unavailable_label_key: str,
) -> None:
    required = {
        str(item or "").strip().lower()
        for item in required_endpoints
        if str(item or "").strip()
    }

    for config in configs:
        if config.get("key") not in _CAPTCHA_PROVIDER_CONFIG_KEYS:
            continue
        if str(config.get("value_type") or "").strip().lower() != "select":
            continue

        existing_options = list(config.get("options") or [])
        existing_values = {
            str(option.get("value") or "").strip() for option in existing_options
        }

        dynamic_options: list[dict[str, str]] = []
        for provider_code, metadata in captcha_registry.items():
            code = str(provider_code or "").strip()
            if not code or code == "image":
                continue
            if code in existing_values:
                continue
            if not _supports_required_endpoints(code, metadata, required):
                continue

            dynamic_options.append(
                {
                    "value": code,
                    "label": _resolve_provider_label(code, metadata),
                }
            )

        dynamic_options.sort(key=lambda item: str(item["label"]).lower())
        config["options"] = [*existing_options, *dynamic_options]

        current_value = str(config.get("value") or "").strip()
        final_values = {
            str(option.get("value") or "").strip() for option in config["options"]
        }
        if current_value and current_value not in final_values:
            config["options"].append(
                {
                    "value": current_value,
                    "label": _(
                        unavailable_label_key,
                        provider=current_value,
                    ),
                }
            )
        break


def _mask_sensitive_options(options: dict[str, Any] | None) -> dict[str, Any]:
    if not options:
        return {}
    masked: dict[str, Any] = {}
    for key, value in options.items():
        if not isinstance(value, str) or not value:
            masked[key] = value
            continue
        key_lower = key.lower()
        is_sensitive = any(word in key_lower for word in _SENSITIVE_KEYWORDS)
        if is_sensitive and len(value) > 4:
            masked[key] = f"{value[:2]}{'*' * min(len(value) - 4, 8)}{value[-2:]}"
        elif is_sensitive:
            masked[key] = "****"
        else:
            masked[key] = value
    return masked


class TenantConfigWorkflowService:
    """Owns tenant-config read/write workflows outside the controller file."""

    def __init__(self, db):
        self._db = db
        self._config_service = ConfigService(db)
        self._role_option_service = TenantRoleOptionService(db)

    def _get_group_or_raise(self, group_code: str):
        group = config_registry.get_group(group_code)
        if not group or group.scope != ConfigScope.ALL_TENANTS:
            raise NotFoundException(
                message=_("config.group_not_found"),
                code=ErrorCode.CONFIG_GROUP_NOT_FOUND,
            )
        return group

    async def _load_group_with_runtime_options(
        self,
        tenant_id: int,
        group_code: str,
    ) -> dict[str, Any] | None:
        groups_with_configs = await self._config_service.get_groups_with_configs(
            scope=ConfigScope.ALL_TENANTS,
            tenant_id=tenant_id,
        )
        target_group = next(
            (group for group in groups_with_configs if group["code"] == group_code),
            None,
        )
        if target_group is None:
            return None

        await self._role_option_service.inject_role_options_for_user_default_role(
            tenant_id=tenant_id,
            configs=target_group["configs"],
        )
        _inject_captcha_provider_options(
            target_group["configs"],
            required_endpoints={"tenant", "user"},
            unavailable_label_key="config.tenant.captcha_provider.unavailable_option",
        )
        return target_group

    def _translate_config_item(self, config: dict[str, Any]) -> ConfigItemResponse:
        translated_options = []
        for option in config.get("options", []):
            if option.get("label"):
                label = option["label"]
            elif option.get("label_key"):
                label = _(option["label_key"])
            else:
                label = str(option.get("value", ""))
            translated_options.append({"value": option["value"], "label": label})

        translated_rules = []
        for rule in config.get("validation_rules", []):
            translated_rules.append(
                {
                    "type": rule["type"],
                    "value": rule["value"],
                    "message": _(rule["message_key"])
                    if rule.get("message_key")
                    else "",
                }
            )

        display_rules = [
            DisplayRuleSchema(
                field=rule["field"],
                operator=rule.get("operator", "equals"),
                value=rule.get("value"),
                action=rule.get("action", "show"),
            )
            for rule in config.get("display_rules", [])
        ]
        children = [
            self._translate_config_item(child) for child in config.get("children", [])
        ]

        return ConfigItemResponse(
            key=config["key"],
            name=_(config["name_key"]),
            description=_(config["description_key"])
            if config.get("description_key")
            else None,
            value_type=config["value_type"],
            value=config["value"],
            default_value=config["default_value"],
            options=translated_options,
            validation_rules=translated_rules,
            is_required=config["is_required"],
            is_encrypted=config["is_encrypted"],
            sort_order=config["sort_order"],
            display_rules=display_rules,
            value_path=config.get("value_path", ""),
            children=children,
            tag_separator=config.get("tag_separator", ","),
            file_accept=config.get("file_accept", ""),
        )

    def _build_group_response(
        self, target_group: dict[str, Any]
    ) -> ConfigGroupResponse:
        configs = [
            self._translate_config_item(config) for config in target_group["configs"]
        ]
        return ConfigGroupResponse(
            code=target_group["code"],
            name=_(target_group["name_key"]),
            description=_(target_group["description_key"])
            if target_group.get("description_key")
            else None,
            icon=target_group.get("icon"),
            sort_order=target_group["sort_order"],
            configs=configs,
        )

    async def get_group_response(
        self,
        *,
        group_code: str,
        tenant_id: int,
    ) -> ConfigGroupResponse:
        self._get_group_or_raise(group_code)
        target_group = await self._load_group_with_runtime_options(
            tenant_id, group_code
        )
        if not target_group:
            raise NotFoundException(
                message=_("config.group_not_found"),
                code=ErrorCode.CONFIG_GROUP_NOT_FOUND,
            )
        return self._build_group_response(target_group)

    async def update_group_configs(
        self,
        *,
        configs: dict[str, Any],
        group_code: str,
        tenant_id: int,
    ) -> ConfigGroupResponse:
        group = self._get_group_or_raise(group_code)
        valid_keys = {config.key for config in group.configs}
        invalid_keys = set(configs.keys()) - valid_keys
        if invalid_keys:
            raise BusinessException(
                message=_("config.invalid_keys", keys=", ".join(invalid_keys)),
                code=ErrorCode.CONFIG_INVALID_KEYS,
            )

        for key, value in configs.items():
            await self._config_service.set_tenant_config(
                tenant_id=tenant_id,
                key=key,
                value=value,
            )
        await self._db.commit()
        return await self.get_group_response(group_code=group_code, tenant_id=tenant_id)

    async def get_storage_status(self, tenant_id: int) -> dict[str, Any]:
        from app.services.common.storage_config_resolver import StorageConfigResolver

        resolver = StorageConfigResolver(self._db)
        effective_mode = await resolver.get_storage_mode(tenant_id)

        tenant_self_config_enabled = await self._config_service.get_tenant_config(
            tenant_id,
            "tenant_storage_self_config_enabled",
            default=False,
        )
        tenant_mode = await self._config_service.get_tenant_config(
            tenant_id,
            "tenant_storage_mode",
            default="platform",
        )
        tenant_driver = await self._config_service.get_tenant_config(
            tenant_id,
            "tenant_storage_driver",
            default=None,
        )
        tenant_root_path = await self._config_service.get_tenant_config(
            tenant_id,
            "tenant_storage_root_path",
            default="",
        )
        tenant_base_url = await self._config_service.get_tenant_config(
            tenant_id,
            "tenant_storage_base_url",
            default="",
        )
        tenant_options = await self._config_service.get_tenant_config(
            tenant_id,
            "tenant_storage_options",
            default={},
        )

        if effective_mode == "platform":
            effective_driver = await self._config_service.get_platform_config(
                "platform_storage_driver",
                default="local",
            )
        else:
            effective_driver = tenant_driver

        response_data: dict[str, Any] = {
            "effective_mode": str(effective_mode),
            "effective_driver": str(effective_driver) if effective_driver else "local",
            "tenant_storage_mode": str(tenant_mode),
            "can_self_config": bool(tenant_self_config_enabled),
        }

        if effective_mode in {"admin_override", "custom"}:
            response_data["tenant_storage_driver"] = (
                str(tenant_driver) if tenant_driver else None
            )
            response_data["tenant_storage_root_path"] = str(tenant_root_path)
            response_data["tenant_storage_base_url"] = str(tenant_base_url)
            response_data["tenant_storage_options"] = _mask_sensitive_options(
                tenant_options or {}
            )
        else:
            response_data["tenant_storage_driver"] = None
            response_data["tenant_storage_root_path"] = ""
            response_data["tenant_storage_base_url"] = ""
            response_data["tenant_storage_options"] = {}

        return response_data

    async def save_storage_config(
        self, *, data: dict[str, Any], tenant_id: int
    ) -> None:
        tenant_enabled = await self._config_service.get_tenant_config(
            tenant_id,
            "tenant_storage_self_config_enabled",
            default=False,
        )
        if not tenant_enabled:
            raise BusinessException(
                message=_("config.storage.self_config_not_enabled"),
                code=ErrorCode.FORBIDDEN,
            )

        driver = data.get("tenant_storage_driver")
        if not driver:
            raise BusinessException(
                message=_("error.common.invalid_parameter"),
                code=ErrorCode.INVALID_PARAMETER,
            )
        root_path = data.get("tenant_storage_root_path", "")
        if not root_path or not str(root_path).strip():
            raise BusinessException(
                message=_("error.common.invalid_parameter"),
                code=ErrorCode.INVALID_PARAMETER,
            )
        if driver == "local":
            raise BusinessException(
                message=_("config.storage.local_not_allowed_for_tenant"),
                code=ErrorCode.INVALID_PARAMETER,
            )

        allowed = await self._config_service.get_platform_config(
            "platform_storage_allowed_custom_drivers",
            default=["aliyun-oss", "qiniu-kodo", "tencent-cos", "s3"],
        )
        if isinstance(allowed, list) and driver not in allowed:
            raise BusinessException(
                message=_("config.storage.driver_not_allowed"),
                code=ErrorCode.INVALID_PARAMETER,
            )

        config_map = {
            "tenant_storage_mode": "tenant_storage_mode",
            "tenant_storage_driver": "tenant_storage_driver",
            "tenant_storage_root_path": "tenant_storage_root_path",
            "tenant_storage_base_url": "tenant_storage_base_url",
            "tenant_storage_options": "tenant_storage_options",
        }
        for field, config_key in config_map.items():
            if field in data:
                await self._config_service.set_tenant_config(
                    tenant_id=tenant_id,
                    key=config_key,
                    value=data[field],
                )

        await self._db.commit()

    async def test_storage_connection(
        self,
        *,
        base_url: str,
        config: dict[str, Any],
        driver: str,
        root_path: str,
        tenant_id: int,
    ) -> dict[str, Any]:
        from app.storage import storage_manager
        from app.storage.base import StorageConfig

        tenant_enabled = await self._config_service.get_tenant_config(
            tenant_id,
            "tenant_storage_self_config_enabled",
            default=False,
        )
        if not tenant_enabled:
            raise BusinessException(
                message=_("config.storage.self_config_not_enabled"),
                code=ErrorCode.FORBIDDEN,
            )
        if driver == "local":
            raise BusinessException(
                message=_("config.storage.local_not_allowed_for_tenant"),
                code=ErrorCode.INVALID_PARAMETER,
            )

        allowed = await self._config_service.get_platform_config(
            "platform_storage_allowed_custom_drivers",
            default=["aliyun-oss", "qiniu-kodo", "tencent-cos", "s3"],
        )
        if isinstance(allowed, list) and driver not in allowed:
            raise BusinessException(
                message=_("config.storage.driver_not_allowed"),
                code=ErrorCode.INVALID_PARAMETER,
            )

        try:
            storage_config = StorageConfig(
                driver=driver,
                root_path=root_path or config.get("bucket", "test"),
                base_url=base_url or None,
                options=config,
            )
            driver_instance = storage_manager.get_driver(storage_config)
            test_key = f".novusai-test/{uuid.uuid4().hex[:8]}.txt"
            test_content = io.BytesIO(b"NovusAI tenant storage test")
            await driver_instance.put(test_key, test_content, mime_type="text/plain")
            exists = await driver_instance.exists(test_key)
            if not exists:
                return build_inline_error_result(
                    _("config.storage.test_file_not_found")
                )
            await driver_instance.delete(test_key)
            return {"success": True}
        except BusinessException:
            raise
        except Exception as exc:
            return build_inline_error_result(
                exc,
                fallback_message=_("common.server_error"),
            )

    async def list_storage_drivers(self) -> list[dict[str, Any]]:
        from app.storage import storage_manager

        allowed = await self._config_service.get_platform_config(
            "platform_storage_allowed_custom_drivers",
            default=["aliyun-oss", "qiniu-kodo", "tencent-cos", "s3"],
        )
        if not isinstance(allowed, list):
            allowed = ["aliyun-oss", "qiniu-kodo", "tencent-cos", "s3"]

        known_plugin_drivers = await PluginReadModelService(
            self._db
        ).get_known_storage_drivers()
        all_drivers = storage_manager.get_all_driver_info_list(known_plugin_drivers)
        return [
            driver
            for driver in all_drivers
            if driver["name"] in allowed and driver["name"] != "local"
        ]


__all__ = ["TenantConfigWorkflowService"]
