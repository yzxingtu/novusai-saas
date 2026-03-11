"""
Configuration definitions module / 配置定义模块

Import all config definitions and register to global ConfigRegistry.
导入所有配置定义并注册到全局 ConfigRegistry
"""

# Import platform configs (triggers config registration to groups) / 导入平台配置（触发配置项注册到分组）
# Import tenant configs (triggers config registration to groups) / 导入租户配置（触发配置项注册到分组）
from app.configs.definitions import platform, tenant

# Import group definitions / 导入分组定义
from app.configs.definitions.groups import (
    ALL_CONFIG_GROUPS,
    PLATFORM_CONFIG_GROUPS,
    TENANT_CONFIG_GROUPS,
)
from app.configs.registry import config_registry


def register_all_configs() -> None:
    """Register all configs to registry / 注册所有配置到 registry

    Called during application startup.
    在应用启动时调用此函数
    """
    # Register all config groups (groups already contain config items) / 注册所有配置分组（分组中已包含配置项）
    for group in ALL_CONFIG_GROUPS:
        if not config_registry.has_group(group.code):
            config_registry.register_group(group)


# Auto-register / 自动注册
register_all_configs()


__all__ = [
    "PLATFORM_CONFIG_GROUPS",
    "TENANT_CONFIG_GROUPS",
    "ALL_CONFIG_GROUPS",
    "register_all_configs",
    "platform",
    "tenant",
]
