"""Config group definitions / 配置分组定义

Defines platform-level and tenant-level config groups.
定义平台级和租户级的配置分组

Icon convention / 图标规范:
Uses Lucide icon library / 使用 Lucide 图标库: https://lucide.dev/icons
Format / 格式: "lucide:{icon-name}"
Example / 示例: "lucide:settings", "lucide:shield", "lucide:mail"
Icon names use kebab-case / 图标名称使用 kebab-case
"""

from app.configs.meta import ConfigGroupMeta
from app.enums.config import ConfigScope

# ==========================================
# Platform config groups / 平台配置分组
# ==========================================

# General settings group / 通用设置分组
PLATFORM_GENERAL_GROUP = ConfigGroupMeta(
    code="platform_general",
    name_key="config.group.platform_general.name",
    description_key="config.group.platform_general.desc",
    scope=ConfigScope.ADMIN_ONLY,
    icon="lucide:settings",
    sort_order=10,
)

# Security settings group / 安全设置分组
PLATFORM_SECURITY_GROUP = ConfigGroupMeta(
    code="platform_security",
    name_key="config.group.platform_security.name",
    description_key="config.group.platform_security.desc",
    scope=ConfigScope.ADMIN_ONLY,
    icon="lucide:shield",
    sort_order=20,
)

# Email settings group / 邮件设置分组
PLATFORM_EMAIL_GROUP = ConfigGroupMeta(
    code="platform_email",
    name_key="config.group.platform_email.name",
    description_key="config.group.platform_email.desc",
    scope=ConfigScope.ADMIN_ONLY,
    icon="lucide:mail",
    sort_order=30,
)

# Storage settings group / 存储设置分组
PLATFORM_STORAGE_GROUP = ConfigGroupMeta(
    code="platform_storage",
    name_key="config.group.platform_storage.name",
    description_key="config.group.platform_storage.desc",
    scope=ConfigScope.ADMIN_ONLY,
    icon="lucide:database",
    sort_order=40,
)


# ==========================================
# Tenant config groups / 租户配置分组
# ==========================================

# Tenant general settings group / 租户通用设置分组
TENANT_GENERAL_GROUP = ConfigGroupMeta(
    code="tenant_general",
    name_key="config.group.tenant_general.name",
    description_key="config.group.tenant_general.desc",
    scope=ConfigScope.ALL_TENANTS,
    icon="lucide:shield",
    sort_order=10,
)

# Tenant appearance settings group / 租户外观设置分组
TENANT_APPEARANCE_GROUP = ConfigGroupMeta(
    code="tenant_appearance",
    name_key="config.group.tenant_appearance.name",
    description_key="config.group.tenant_appearance.desc",
    scope=ConfigScope.ALL_TENANTS,
    icon="lucide:palette",
    sort_order=20,
)

# Tenant features settings group / 租户功能设置分组
TENANT_FEATURES_GROUP = ConfigGroupMeta(
    code="tenant_features",
    name_key="config.group.tenant_features.name",
    description_key="config.group.tenant_features.desc",
    scope=ConfigScope.ALL_TENANTS,
    icon="lucide:users",
    sort_order=30,
)

TENANT_STORAGE_GROUP = ConfigGroupMeta(
    code="tenant_storage",
    name_key="config.group.tenant_storage.name",
    description_key="config.group.tenant_storage.desc",
    scope=ConfigScope.ALL_TENANTS,
    icon="lucide:database",
    sort_order=40,
)


# ==========================================
# Group lists / 分组列表
# ==========================================

# SSL certificate settings group / SSL 证书设置分组
PLATFORM_SSL_GROUP = ConfigGroupMeta(
    code="platform_ssl",
    name_key="config.group.platform_ssl.name",
    description_key="config.group.platform_ssl.desc",
    scope=ConfigScope.ADMIN_ONLY,
    icon="lucide:shield-check",
    sort_order=50,
)

# WebSocket & notification settings group / WebSocket & 通知设置分组
PLATFORM_WEBSOCKET_GROUP = ConfigGroupMeta(
    code="platform_websocket",
    name_key="config.group.platform_websocket.name",
    description_key="config.group.platform_websocket.desc",
    scope=ConfigScope.ADMIN_ONLY,
    icon="lucide:radio",
    sort_order=70,
)

# AI Toolkit settings group / AI Toolkit 设置分组
PLATFORM_AI_TOOLKIT_GROUP = ConfigGroupMeta(
    code="platform_ai_toolkit",
    name_key="config.group.platform_ai_toolkit.name",
    description_key="config.group.platform_ai_toolkit.desc",
    scope=ConfigScope.ADMIN_ONLY,
    icon="lucide:wrench",
    sort_order=60,
)

# AI Memory settings group / AI 记忆设置分组
PLATFORM_AI_MEMORY_GROUP = ConfigGroupMeta(
    code="platform_ai_memory",
    name_key="config.group.platform_ai_memory.name",
    description_key="config.group.platform_ai_memory.desc",
    scope=ConfigScope.ADMIN_ONLY,
    icon="lucide:brain-circuit",
    sort_order=65,
)

# All platform config groups / 所有平台配置分组
PLATFORM_CONFIG_GROUPS = [
    PLATFORM_GENERAL_GROUP,
    PLATFORM_SECURITY_GROUP,
    PLATFORM_EMAIL_GROUP,
    PLATFORM_STORAGE_GROUP,
    PLATFORM_SSL_GROUP,
    PLATFORM_AI_TOOLKIT_GROUP,
    PLATFORM_AI_MEMORY_GROUP,
    PLATFORM_WEBSOCKET_GROUP,
]

# All tenant config groups / 所有租户配置分组
TENANT_CONFIG_GROUPS = [
    TENANT_GENERAL_GROUP,
    TENANT_APPEARANCE_GROUP,
    TENANT_FEATURES_GROUP,
    TENANT_STORAGE_GROUP,
]

# All config groups / 所有配置分组
ALL_CONFIG_GROUPS = PLATFORM_CONFIG_GROUPS + TENANT_CONFIG_GROUPS


__all__ = [
    # Platform groups / 平台分组
    "PLATFORM_GENERAL_GROUP",
    "PLATFORM_SECURITY_GROUP",
    "PLATFORM_EMAIL_GROUP",
    "PLATFORM_STORAGE_GROUP",
    "PLATFORM_SSL_GROUP",
    "PLATFORM_AI_TOOLKIT_GROUP",
    "PLATFORM_AI_MEMORY_GROUP",
    "PLATFORM_WEBSOCKET_GROUP",
    "PLATFORM_CONFIG_GROUPS",
    # Tenant groups / 租户分组
    "TENANT_GENERAL_GROUP",
    "TENANT_APPEARANCE_GROUP",
    "TENANT_FEATURES_GROUP",
    "TENANT_STORAGE_GROUP",
    "TENANT_CONFIG_GROUPS",
    # All / 全部
    "ALL_CONFIG_GROUPS",
]
