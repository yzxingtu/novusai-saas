"""
配置模块

提供配置元数据定义和注册中心功能
"""

from app.configs.meta import (
    ConfigMeta,
    ConfigGroupMeta,
    ConfigOption,
    ValidationRule,
    # 便捷函数
    min_value,
    max_value,
    min_length,
    max_length,
    pattern,
    option,
)
from app.configs.registry import (
    ConfigRegistry,
    config_registry,
    get_config_registry,
)
from app.configs.sync import (
    ConfigSyncService,
    sync_configs_on_startup,
)
from app.configs.service import (
    ConfigService,
    get_config_service,
    PLATFORM_TENANT_ID,
)

__all__ = [
    # 元数据类
    "ConfigMeta",
    "ConfigGroupMeta",
    "ConfigOption",
    "ValidationRule",
    # 注册中心
    "ConfigRegistry",
    "config_registry",
    "get_config_registry",
    # 便捷函数
    "min_value",
    "max_value",
    "min_length",
    "max_length",
    "pattern",
    "option",
    # 同步服务
    "ConfigSyncService",
    "sync_configs_on_startup",
    # 配置服务
    "ConfigService",
    "get_config_service",
    "PLATFORM_TENANT_ID",
]
