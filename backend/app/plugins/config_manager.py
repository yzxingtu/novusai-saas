"""
插件配置管理器

负责插件配置的合并、校验、上下文构建。
从 PluginManager 提取，降低 God Object 复杂度。
"""

from __future__ import annotations

from typing import Any

import jsonschema
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.i18n import _
from app.core.logging import LogManager
from app.exceptions import ValidationException
from app.plugins.base import BasePlugin
from app.plugins.context import PluginContext

logger = LogManager.get_logger("app")


class PluginConfigManager:
    """
    插件配置管理器

    职责：
    - 合并默认配置和自定义配置
    - JSON Schema 校验
    - 构建插件运行时上下文 (PluginContext)
    """

    @staticmethod
    def merge_config(
        default: dict[str, Any] | None,
        override: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """深度合并默认配置和自定义配置（嵌套 dict 递归合并）"""
        result = dict(default or {})
        if not override:
            return result
        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = PluginConfigManager.merge_config(result[key], value)
            else:
                result[key] = value
        return result

    @staticmethod
    def validate_config(
        schema: dict[str, Any], config: dict[str, Any]
    ) -> None:
        """使用 JSON Schema 校验配置"""
        try:
            jsonschema.validate(instance=config, schema=schema)
        except jsonschema.ValidationError as exc:
            raise ValidationException(
                _("plugin.config_validation_failed") + f": {exc.message}"
            ) from exc

    @staticmethod
    def extract_schema_defaults(schema: dict[str, Any]) -> dict[str, Any]:
        """从 JSON Schema 的 properties 中提取 default 值"""
        defaults: dict[str, Any] = {}
        if not schema:
            return defaults
        for key, prop in schema.get("properties", {}).items():
            if "default" in prop:
                defaults[key] = prop["default"]
        return defaults

    @staticmethod
    def build_context(
        instance: BasePlugin,
        db: AsyncSession | None = None,
        tenant_id: int | None = None,
        config: dict[str, Any] | None = None,
        model_id: int | None = None,
    ) -> PluginContext:
        """构建权限感知的插件运行时上下文"""
        from app.ai.events.bus import get_event_bus
        from app.ai.tools.registry import get_tool_registry
        from app.plugins.security import (
            build_permission_aware_context_kwargs,
            decrypt_sensitive_config,
        )

        plugin_logger = LogManager.get_logger(f"plugin.{instance.name}")

        # 根据声明的权限决定注入哪些能力
        ctx_kwargs = build_permission_aware_context_kwargs(
            declared_permissions=instance.required_permissions,
            db=db,
            event_bus=get_event_bus(),
            tool_registry=get_tool_registry(),
        )

        # 确定最终配置：优先使用传入的 config，否则用实例默认配置
        final_config = config or instance.default_config
        # 解密 DB 中存储的加密敏感字段（format:password）
        if final_config and instance.config_schema:
            final_config = decrypt_sensitive_config(
                final_config, instance.config_schema
            )

        return PluginContext(
            config=final_config,
            tenant_id=tenant_id,
            logger=plugin_logger,
            plugin_name=instance.name,
            plugin_version=instance.version,
            plugin_scope=instance.scope,
            model_id=model_id,
            **ctx_kwargs,
        )


__all__ = ["PluginConfigManager"]
