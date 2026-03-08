"""
租户品牌设置配置项

包含租户 Logo、登录页定制等配置
"""

from app.configs.definitions.groups import TENANT_APPEARANCE_GROUP
from app.configs.meta import ConfigMeta, max_length
from app.enums.config import ConfigScope, ConfigValueType

# ==========================================
# Logo 和图标
# ==========================================

# 租户 Logo
TENANT_LOGO = ConfigMeta(
    key="tenant_logo",
    name_key="config.tenant.logo.name",
    description_key="config.tenant.logo.desc",
    scope=ConfigScope.ALL_TENANTS,
    value_type=ConfigValueType.IMAGE,
    default_value="",
    sort_order=10,
)

# 租户 Favicon
TENANT_FAVICON = ConfigMeta(
    key="tenant_favicon",
    name_key="config.tenant.favicon.name",
    description_key="config.tenant.favicon.desc",
    scope=ConfigScope.ALL_TENANTS,
    value_type=ConfigValueType.IMAGE,
    default_value="",
    sort_order=20,
)

# 登录页背景图
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
# 自定义文本
# ==========================================

# 登录页标题
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

# 登录页副标题
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

# 页脚版权
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


# ==========================================
# 注册配置到分组
# ==========================================

TENANT_APPEARANCE_GROUP.configs = [
    TENANT_LOGO,
    TENANT_FAVICON,
    TENANT_LOGIN_BG,
    TENANT_LOGIN_TITLE,
    TENANT_LOGIN_SUBTITLE,
    TENANT_FOOTER_COPYRIGHT,
]


__all__ = [
    "TENANT_LOGO",
    "TENANT_FAVICON",
    "TENANT_LOGIN_BG",
    "TENANT_LOGIN_TITLE",
    "TENANT_LOGIN_SUBTITLE",
    "TENANT_FOOTER_COPYRIGHT",
]
