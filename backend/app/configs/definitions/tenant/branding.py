"""Tenant branding settings config items / 企业品牌设置配置项

Includes tenant Logo, login page customization, etc.
包含企业 Logo、登录页定制等配置
"""

from app.configs.definitions.groups import TENANT_APPEARANCE_GROUP
from app.configs.meta import ConfigMeta, max_length
from app.enums.config import ConfigScope, ConfigValueType

# ==========================================
# Logo and icons / Logo 和图标
# ==========================================

# Tenant Logo / 企业 Logo
TENANT_LOGO = ConfigMeta(
    key="tenant_logo",
    name_key="config.tenant.logo.name",
    description_key="config.tenant.logo.desc",
    scope=ConfigScope.ALL_TENANTS,
    value_type=ConfigValueType.IMAGE,
    default_value="",
    sort_order=10,
)

# Tenant Favicon / 企业 Favicon
TENANT_FAVICON = ConfigMeta(
    key="tenant_favicon",
    name_key="config.tenant.favicon.name",
    description_key="config.tenant.favicon.desc",
    scope=ConfigScope.ALL_TENANTS,
    value_type=ConfigValueType.IMAGE,
    default_value="",
    sort_order=20,
)

# Tenant dark logo / 企业深色 Logo
TENANT_LOGO_DARK = ConfigMeta(
    key="tenant_logo_dark",
    name_key="config.tenant.logo_dark.name",
    description_key="config.tenant.logo_dark.desc",
    scope=ConfigScope.ALL_TENANTS,
    value_type=ConfigValueType.IMAGE,
    default_value="",
    sort_order=25,
)

# Login page background image / 登录页背景图
TENANT_LOGIN_BG = ConfigMeta(
    key="tenant_login_bg",
    name_key="config.tenant.login_bg.name",
    description_key="config.tenant.login_bg.desc",
    scope=ConfigScope.ALL_TENANTS,
    value_type=ConfigValueType.IMAGE,
    default_value="",
    sort_order=30,
)


# ==========================================
# Custom text / 自定义文本
# ==========================================

# Login page title / 登录页标题
TENANT_LOGIN_TITLE = ConfigMeta(
    key="tenant_login_title",
    name_key="config.tenant.login_title.name",
    description_key="config.tenant.login_title.desc",
    scope=ConfigScope.ALL_TENANTS,
    value_type=ConfigValueType.STRING,
    default_value="",
    validation_rules=[
        max_length(100, "validation.max_length"),
    ],
    sort_order=60,
)

# Login page subtitle / 登录页副标题
TENANT_LOGIN_SUBTITLE = ConfigMeta(
    key="tenant_login_subtitle",
    name_key="config.tenant.login_subtitle.name",
    description_key="config.tenant.login_subtitle.desc",
    scope=ConfigScope.ALL_TENANTS,
    value_type=ConfigValueType.STRING,
    default_value="",
    validation_rules=[
        max_length(200, "validation.max_length"),
    ],
    sort_order=70,
)

# Footer copyright / 页脚版权
TENANT_FOOTER_COPYRIGHT = ConfigMeta(
    key="tenant_footer_copyright",
    name_key="config.tenant.footer_copyright.name",
    description_key="config.tenant.footer_copyright.desc",
    scope=ConfigScope.ALL_TENANTS,
    value_type=ConfigValueType.STRING,
    default_value="",
    validation_rules=[
        max_length(200, "validation.max_length"),
    ],
    sort_order=80,
)

# ICP filing number / ICP 备案号
TENANT_ICP = ConfigMeta(
    key="tenant_icp",
    name_key="config.tenant.icp.name",
    description_key="config.tenant.icp.desc",
    scope=ConfigScope.ALL_TENANTS,
    value_type=ConfigValueType.STRING,
    default_value="",
    validation_rules=[
        max_length(100, "validation.max_length"),
    ],
    sort_order=90,
)


# ==========================================
# Register configs to group / 注册配置到分组
# ==========================================

TENANT_APPEARANCE_GROUP.configs = [
    TENANT_LOGO,
    TENANT_FAVICON,
    TENANT_LOGO_DARK,
    TENANT_LOGIN_BG,
    TENANT_LOGIN_TITLE,
    TENANT_LOGIN_SUBTITLE,
    TENANT_FOOTER_COPYRIGHT,
    TENANT_ICP,
]


__all__ = [
    "TENANT_LOGO",
    "TENANT_FAVICON",
    "TENANT_LOGO_DARK",
    "TENANT_LOGIN_BG",
    "TENANT_LOGIN_TITLE",
    "TENANT_LOGIN_SUBTITLE",
    "TENANT_FOOTER_COPYRIGHT",
    "TENANT_ICP",
]
