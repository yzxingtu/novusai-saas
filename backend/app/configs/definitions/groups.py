"""
配置分组定义

定义平台级和租户级的配置分组

图标规范:
使用 Lucide 图标库: https://lucide.dev/icons
格式: "lucide:{icon-name}"
示例: "lucide:settings", "lucide:shield", "lucide:mail"
图标名称使用 kebab-case（小写字母，单词间用连字符分隔）
"""

from app.configs.meta import ConfigGroupMeta
from app.enums.config import ConfigScope

# ==========================================
# 平台配置分组
# ==========================================

# 通用设置分组
PLATFORM_GENERAL_GROUP = ConfigGroupMeta(
    code="platform_general",
    name_key="config.group.platform_general.name",
    description_key="config.group.platform_general.desc",
    scope=ConfigScope.ADMIN_ONLY,
    icon="lucide:settings",
    sort_order=10,
)

# 安全设置分组
PLATFORM_SECURITY_GROUP = ConfigGroupMeta(
    code="platform_security",
    name_key="config.group.platform_security.name",
    description_key="config.group.platform_security.desc",
    scope=ConfigScope.ADMIN_ONLY,
    icon="lucide:shield",
    sort_order=20,
)

# 邮件设置分组
PLATFORM_EMAIL_GROUP = ConfigGroupMeta(
    code="platform_email",
    name_key="config.group.platform_email.name",
    description_key="config.group.platform_email.desc",
    scope=ConfigScope.ADMIN_ONLY,
    icon="lucide:mail",
    sort_order=30,
)

# 存储设置分组
PLATFORM_STORAGE_GROUP = ConfigGroupMeta(
    code="platform_storage",
    name_key="config.group.platform_storage.name",
    description_key="config.group.platform_storage.desc",
    scope=ConfigScope.ADMIN_ONLY,
    icon="lucide:database",
    sort_order=40,
)


# ==========================================
# 租户配置分组
# ==========================================

# 租户基础设置分组
TENANT_GENERAL_GROUP = ConfigGroupMeta(
    code="tenant_general",
    name_key="config.group.tenant_general.name",
    description_key="config.group.tenant_general.desc",
    scope=ConfigScope.ALL_TENANTS,
    icon="lucide:sliders-horizontal",
    sort_order=10,
)

# 租户外观设置分组
TENANT_APPEARANCE_GROUP = ConfigGroupMeta(
    code="tenant_appearance",
    name_key="config.group.tenant_appearance.name",
    description_key="config.group.tenant_appearance.desc",
    scope=ConfigScope.ALL_TENANTS,
    icon="lucide:palette",
    sort_order=20,
)

# 租户功能设置分组
TENANT_FEATURES_GROUP = ConfigGroupMeta(
    code="tenant_features",
    name_key="config.group.tenant_features.name",
    description_key="config.group.tenant_features.desc",
    scope=ConfigScope.ALL_TENANTS,
    icon="lucide:puzzle",
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
# 分组列表
# ==========================================

# SSL 证书设置分组
PLATFORM_SSL_GROUP = ConfigGroupMeta(
    code="platform_ssl",
    name_key="config.group.platform_ssl.name",
    description_key="config.group.platform_ssl.desc",
    scope=ConfigScope.ADMIN_ONLY,
    icon="lucide:shield-check",
    sort_order=50,
)

# WebSocket & 通知设置分组
PLATFORM_WEBSOCKET_GROUP = ConfigGroupMeta(
    code="platform_websocket",
    name_key="config.group.platform_websocket.name",
    description_key="config.group.platform_websocket.desc",
    scope=ConfigScope.ADMIN_ONLY,
    icon="lucide:radio",
    sort_order=70,
)

# AI Toolkit 安全设置分组
PLATFORM_AI_TOOLKIT_GROUP = ConfigGroupMeta(
    code="platform_ai_toolkit",
    name_key="config.group.platform_ai_toolkit.name",
    description_key="config.group.platform_ai_toolkit.desc",
    scope=ConfigScope.ADMIN_ONLY,
    icon="lucide:wrench",
    sort_order=60,
)

# AI 记忆设置分组
PLATFORM_AI_MEMORY_GROUP = ConfigGroupMeta(
    code="platform_ai_memory",
    name_key="config.group.platform_ai_memory.name",
    description_key="config.group.platform_ai_memory.desc",
    scope=ConfigScope.ADMIN_ONLY,
    icon="lucide:brain-circuit",
    sort_order=65,
)

# 所有平台配置分组
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

# 所有租户配置分组
TENANT_CONFIG_GROUPS = [
    TENANT_GENERAL_GROUP,
    TENANT_APPEARANCE_GROUP,
    TENANT_FEATURES_GROUP,
    TENANT_STORAGE_GROUP,
]

# 所有配置分组
ALL_CONFIG_GROUPS = PLATFORM_CONFIG_GROUPS + TENANT_CONFIG_GROUPS


__all__ = [
    # 平台分组
    "PLATFORM_GENERAL_GROUP",
    "PLATFORM_SECURITY_GROUP",
    "PLATFORM_EMAIL_GROUP",
    "PLATFORM_STORAGE_GROUP",
    "PLATFORM_SSL_GROUP",
    "PLATFORM_AI_TOOLKIT_GROUP",
    "PLATFORM_AI_MEMORY_GROUP",
    "PLATFORM_WEBSOCKET_GROUP",
    "PLATFORM_CONFIG_GROUPS",
    # 租户分组
    "TENANT_GENERAL_GROUP",
    "TENANT_APPEARANCE_GROUP",
    "TENANT_FEATURES_GROUP",
    "TENANT_STORAGE_GROUP",
    "TENANT_CONFIG_GROUPS",
    # 全部
    "ALL_CONFIG_GROUPS",
]
