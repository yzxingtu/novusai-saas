"""Configuration module / 配置模块

Provides config metadata definitions and registry functionality.
提供配置元数据定义和注册中心功能
"""

from app.configs.meta import (
    ConfigGroupMeta,
    ConfigMeta,
    ConfigOption,
    ValidationRule,
    max_length,
    max_value,
    min_length,
    # Convenience functions / 便捷函数
    min_value,
    option,
    pattern,
)
from app.configs.registry import (
    ConfigRegistry,
    config_registry,
    get_config_registry,
)
from app.configs.service import (
    PLATFORM_TENANT_ID,
    ConfigService,
    get_config_service,
)
from app.configs.sync import (
    ConfigSyncService,
    sync_configs_on_startup,
)

__all__ = [
    # Metadata classes / 元数据类
    "ConfigMeta",
    "ConfigGroupMeta",
    "ConfigOption",
    "ValidationRule",
    # Registry / 注册中心
    "ConfigRegistry",
    "config_registry",
    "get_config_registry",
    # Convenience functions / 便捷函数
    "min_value",
    "max_value",
    "min_length",
    "max_length",
    "pattern",
    "option",
    # Sync service / 同步服务
    "ConfigSyncService",
    "sync_configs_on_startup",
    # Config service / 配置服务
    "ConfigService",
    "get_config_service",
    "PLATFORM_TENANT_ID",
]
