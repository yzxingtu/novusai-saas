"""Platform general settings config items / 平台通用设置配置项

Includes site basic info and maintenance mode.
包含站点基本信息与维护模式配置
"""

from app.configs.definitions.groups import PLATFORM_GENERAL_GROUP
from app.configs.meta import ConfigMeta, DisplayRule, max_length, min_length
from app.enums.config import ConfigScope, ConfigValueType

# ==========================================
# Site basic info / 站点基本信息
# ==========================================

# Site name / 站点名称
SITE_NAME = ConfigMeta(
    key="site_name",
    name_key="config.platform.site_name.name",
    description_key="config.platform.site_name.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.STRING,
    default_value="NovusAI SaaS",
    is_required=True,
    validation_rules=[
        min_length(1, "validation.min_length"),
        max_length(100, "validation.max_length"),
    ],
    sort_order=10,
)

# Site description / 站点描述
SITE_DESCRIPTION = ConfigMeta(
    key="site_description",
    name_key="config.platform.site_description.name",
    description_key="config.platform.site_description.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.TEXT,
    default_value="现代化 AI 集成 SaaS 开发框架",
    validation_rules=[
        max_length(500, "validation.max_length"),
    ],
    sort_order=20,
)

# Site Logo / 站点 Logo
SITE_LOGO = ConfigMeta(
    key="site_logo",
    name_key="config.platform.site_logo.name",
    description_key="config.platform.site_logo.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.IMAGE,
    default_value="",
    sort_order=30,
)

# Site Favicon / 站点 Favicon
SITE_FAVICON = ConfigMeta(
    key="site_favicon",
    name_key="config.platform.site_favicon.name",
    description_key="config.platform.site_favicon.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.IMAGE,
    default_value="",
    sort_order=40,
)

# Site dark logo / 站点深色 Logo
LOGO_DARK = ConfigMeta(
    key="logo_dark",
    name_key="config.platform.logo_dark.name",
    description_key="config.platform.logo_dark.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.IMAGE,
    default_value="",
    sort_order=45,
)

# Copyright info / 版权信息
SITE_COPYRIGHT = ConfigMeta(
    key="site_copyright",
    name_key="config.platform.site_copyright.name",
    description_key="config.platform.site_copyright.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.STRING,
    default_value="\u00a9 2025 NovusAI. All rights reserved.",
    validation_rules=[
        max_length(200, "validation.max_length"),
    ],
    sort_order=50,
)

# ICP filing number / ICP 备案号
SITE_ICP = ConfigMeta(
    key="site_icp",
    name_key="config.platform.site_icp.name",
    description_key="config.platform.site_icp.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.STRING,
    default_value="",
    sort_order=60,
)
# ==========================================
# Maintenance mode / 维护模式
# ==========================================

# Maintenance mode toggle / 维护模式开关
MAINTENANCE_MODE = ConfigMeta(
    key="maintenance_mode",
    name_key="config.platform.maintenance_mode.name",
    description_key="config.platform.maintenance_mode.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.BOOLEAN,
    default_value=False,
    sort_order=100,
)

# Maintenance mode message / 维护模式提示信息
MAINTENANCE_MESSAGE = ConfigMeta(
    key="maintenance_message",
    name_key="config.platform.maintenance_message.name",
    description_key="config.platform.maintenance_message.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.TEXT,
    default_value="系统正在维护中，请稍后再试。",
    validation_rules=[
        max_length(1000, "validation.max_length"),
    ],
    sort_order=110,
    display_rules=[
        DisplayRule(
            field="maintenance_mode", operator="equals", value=True, action="show"
        ),
    ],
)


# ==========================================
# Register configs to group / 注册配置到分组
# ==========================================

PLATFORM_GENERAL_GROUP.configs = [
    SITE_NAME,
    SITE_DESCRIPTION,
    SITE_LOGO,
    SITE_FAVICON,
    LOGO_DARK,
    SITE_COPYRIGHT,
    SITE_ICP,
    MAINTENANCE_MODE,
    MAINTENANCE_MESSAGE,
]


__all__ = [
    "SITE_NAME",
    "SITE_DESCRIPTION",
    "SITE_LOGO",
    "SITE_FAVICON",
    "LOGO_DARK",
    "SITE_COPYRIGHT",
    "SITE_ICP",
    "MAINTENANCE_MODE",
    "MAINTENANCE_MESSAGE",
]
