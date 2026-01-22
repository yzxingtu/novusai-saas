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
    scope=ConfigScope.PLATFORM,
    icon="lucide:settings",
    sort_order=10,
)

# 安全设置分组
PLATFORM_SECURITY_GROUP = ConfigGroupMeta(
    code="platform_security",
    name_key="config.group.platform_security.name",
    description_key="config.group.platform_security.desc",
    scope=ConfigScope.PLATFORM,
    icon="lucide:shield",
    sort_order=20,
)

# 邮件设置分组
PLATFORM_EMAIL_GROUP = ConfigGroupMeta(
    code="platform_email",
    name_key="config.group.platform_email.name",
    description_key="config.group.platform_email.desc",
    scope=ConfigScope.PLATFORM,
    icon="lucide:mail",
    sort_order=30,
)

# 存储设置分组
PLATFORM_STORAGE_GROUP = ConfigGroupMeta(
    code="platform_storage",
    name_key="config.group.platform_storage.name",
    description_key="config.group.platform_storage.desc",
    scope=ConfigScope.PLATFORM,
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
    scope=ConfigScope.TENANT,
    icon="lucide:sliders-horizontal",
    sort_order=10,
)

# 租户外观设置分组
TENANT_APPEARANCE_GROUP = ConfigGroupMeta(
    code="tenant_appearance",
    name_key="config.group.tenant_appearance.name",
    description_key="config.group.tenant_appearance.desc",
    scope=ConfigScope.TENANT,
    icon="lucide:palette",
    sort_order=20,
)

# 租户功能设置分组
TENANT_FEATURES_GROUP = ConfigGroupMeta(
    code="tenant_features",
    name_key="config.group.tenant_features.name",
    description_key="config.group.tenant_features.desc",
    scope=ConfigScope.TENANT,
    icon="lucide:puzzle",
    sort_order=30,
)


# ==========================================
# 分组列表
# ==========================================

# 所有平台配置分组
PLATFORM_CONFIG_GROUPS = [
    PLATFORM_GENERAL_GROUP,
    PLATFORM_SECURITY_GROUP,
    PLATFORM_EMAIL_GROUP,
    PLATFORM_STORAGE_GROUP,
]

# 所有租户配置分组
TENANT_CONFIG_GROUPS = [
    TENANT_GENERAL_GROUP,
    TENANT_APPEARANCE_GROUP,
    TENANT_FEATURES_GROUP,
]

# 所有配置分组
ALL_CONFIG_GROUPS = PLATFORM_CONFIG_GROUPS + TENANT_CONFIG_GROUPS


__all__ = [
    # 平台分组
    "PLATFORM_GENERAL_GROUP",
    "PLATFORM_SECURITY_GROUP",
    "PLATFORM_EMAIL_GROUP",
    "PLATFORM_STORAGE_GROUP",
    "PLATFORM_CONFIG_GROUPS",
    # 租户分组
    "TENANT_GENERAL_GROUP",
    "TENANT_APPEARANCE_GROUP",
    "TENANT_FEATURES_GROUP",
    "TENANT_CONFIG_GROUPS",
    # 全部
    "ALL_CONFIG_GROUPS",
]
