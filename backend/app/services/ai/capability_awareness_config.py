"""Capability awareness config helpers / 能力感知配置辅助函数

Provides a typed runtime view over tenant config items used by dynamic
capability awareness.
为动态能力感知提供租户配置项的强类型运行时视图。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.configs.service import ConfigService

DEFAULT_DYNAMIC_CAPABILITY_AWARENESS_ENABLED = True
DEFAULT_CAPABILITY_DESCRIPTION_STYLE = "detailed"
DEFAULT_MAX_CAPABILITY_ITEMS_PER_CATEGORY = 20
_ALLOWED_CAPABILITY_DESCRIPTION_STYLES = {"detailed", "concise"}


@dataclass(frozen=True)
class TenantCapabilityAwarenessSettings:
    """Tenant capability awareness settings / 租户能力感知设置"""

    enable_dynamic_capability_awareness: bool = (
        DEFAULT_DYNAMIC_CAPABILITY_AWARENESS_ENABLED
    )
    capability_description_style: str = DEFAULT_CAPABILITY_DESCRIPTION_STYLE
    max_capability_items_per_category: int = DEFAULT_MAX_CAPABILITY_ITEMS_PER_CATEGORY


def _coerce_bool(value: Any, *, default: bool) -> bool:
    """Coerce config values to bool / 将配置值归一化为布尔值"""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    return default


def _coerce_style(value: Any) -> str:
    """Coerce config values to supported style / 将配置值归一化为支持的风格"""
    normalized = str(value or "").strip().lower()
    if normalized in _ALLOWED_CAPABILITY_DESCRIPTION_STYLES:
        return normalized
    return DEFAULT_CAPABILITY_DESCRIPTION_STYLE


def _coerce_positive_int(value: Any, *, default: int) -> int:
    """Coerce config values to positive int / 将配置值归一化为正整数"""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(parsed, 1)


async def get_tenant_capability_awareness_settings(
    db: Any,
    tenant_id: int,
) -> TenantCapabilityAwarenessSettings:
    """Load tenant capability awareness settings / 加载租户能力感知设置"""
    config_service = ConfigService(db)

    raw_enabled = await config_service.get_tenant_config(
        tenant_id,
        "tenant_ai_enable_dynamic_capability_awareness",
        default=DEFAULT_DYNAMIC_CAPABILITY_AWARENESS_ENABLED,
    )
    raw_style = await config_service.get_tenant_config(
        tenant_id,
        "tenant_ai_capability_description_style",
        default=DEFAULT_CAPABILITY_DESCRIPTION_STYLE,
    )
    raw_max_items = await config_service.get_tenant_config(
        tenant_id,
        "tenant_ai_max_capability_items_per_category",
        default=DEFAULT_MAX_CAPABILITY_ITEMS_PER_CATEGORY,
    )

    return TenantCapabilityAwarenessSettings(
        enable_dynamic_capability_awareness=_coerce_bool(
            raw_enabled,
            default=DEFAULT_DYNAMIC_CAPABILITY_AWARENESS_ENABLED,
        ),
        capability_description_style=_coerce_style(raw_style),
        max_capability_items_per_category=_coerce_positive_int(
            raw_max_items,
            default=DEFAULT_MAX_CAPABILITY_ITEMS_PER_CATEGORY,
        ),
    )


__all__ = [
    "DEFAULT_DYNAMIC_CAPABILITY_AWARENESS_ENABLED",
    "DEFAULT_CAPABILITY_DESCRIPTION_STYLE",
    "DEFAULT_MAX_CAPABILITY_ITEMS_PER_CATEGORY",
    "TenantCapabilityAwarenessSettings",
    "get_tenant_capability_awareness_settings",
]
