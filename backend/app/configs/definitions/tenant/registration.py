"""Tenant user registration config items / 企业用户注册配置项

Includes tenant-level user self-registration configs.
包含企业级的用户自助注册相关配置
"""

from app.configs.definitions.groups import TENANT_FEATURES_GROUP
from app.configs.meta import ConfigMeta, ConfigOption, DisplayRule
from app.enums.config import ConfigScope, ConfigValueType


# ==========================================
# User registration / 用户注册
# ==========================================

# Whether user registration is open / 是否开放用户注册
USER_REGISTRATION_ENABLED = ConfigMeta(
    key="user_registration_enabled",
    name_key="config.tenant.user_registration_enabled.name",
    description_key="config.tenant.user_registration_enabled.desc",
    scope=ConfigScope.ALL_TENANTS,
    value_type=ConfigValueType.BOOLEAN,
    default_value=False,
    sort_order=100,
)

# Whether registration requires captcha / 注册是否需要验证码
USER_REGISTRATION_CAPTCHA_ENABLED = ConfigMeta(
    key="user_registration_captcha_enabled",
    name_key="config.tenant.user_registration_captcha_enabled.name",
    description_key="config.tenant.user_registration_captcha_enabled.desc",
    scope=ConfigScope.ALL_TENANTS,
    value_type=ConfigValueType.BOOLEAN,
    default_value=True,
    sort_order=110,
    display_rules=[
        DisplayRule(field="tenant_allow_registration", operator="equals", value=True, action="show"),
    ],
)

# Whether registered users are active by default / 注册用户是否默认激活
USER_DEFAULT_ACTIVE = ConfigMeta(
    key="user_default_active",
    name_key="config.tenant.user_default_active.name",
    description_key="config.tenant.user_default_active.desc",
    scope=ConfigScope.ALL_TENANTS,
    value_type=ConfigValueType.BOOLEAN,
    default_value=True,
    sort_order=120,
    display_rules=[
        DisplayRule(field="tenant_allow_registration", operator="equals", value=True, action="show"),
    ],
)

# Whether registration requires approval (controlled by features.py tenant_registration_approval, kept for compatibility) / 注册是否需要审批（已由 features.py 控制，保留兼容）
USER_REQUIRE_APPROVAL = ConfigMeta(
    key="user_require_approval",
    name_key="config.tenant.user_require_approval.name",
    description_key="config.tenant.user_require_approval.desc",
    scope=ConfigScope.ALL_TENANTS,
    value_type=ConfigValueType.BOOLEAN,
    default_value=False,
    sort_order=130,
    display_rules=[
        DisplayRule(field="tenant_allow_registration", operator="equals", value=True, action="show"),
    ],
)

# Default role ID for registered users (auto-set by seed, admin can modify) / 注册用户默认角色 ID
USER_DEFAULT_ROLE_ID = ConfigMeta(
    key="user_default_role_id",
    name_key="config.tenant.user_default_role_id.name",
    description_key="config.tenant.user_default_role_id.desc",
    scope=ConfigScope.ALL_TENANTS,
    value_type=ConfigValueType.SELECT,
    default_value=0,
    sort_order=140,
    options=[
        ConfigOption(value=0, label_key="config.tenant.user_default_role_id.option_none"),
    ],
    display_rules=[
        DisplayRule(field="tenant_allow_registration", operator="equals", value=True, action="show"),
    ],
)

# Privacy policy URL / 隐私政策链接
USER_PRIVACY_POLICY_URL = ConfigMeta(
    key="user_privacy_policy_url",
    name_key="config.tenant.user_privacy_policy_url.name",
    description_key="config.tenant.user_privacy_policy_url.desc",
    scope=ConfigScope.ALL_TENANTS,
    value_type=ConfigValueType.STRING,
    default_value="",
    sort_order=150,
    display_rules=[
        DisplayRule(field="tenant_allow_registration", operator="equals", value=True, action="show"),
    ],
)

# Terms of service URL / 服务条款链接
USER_TERMS_URL = ConfigMeta(
    key="user_terms_url",
    name_key="config.tenant.user_terms_url.name",
    description_key="config.tenant.user_terms_url.desc",
    scope=ConfigScope.ALL_TENANTS,
    value_type=ConfigValueType.STRING,
    default_value="",
    sort_order=160,
    display_rules=[
        DisplayRule(field="tenant_allow_registration", operator="equals", value=True, action="show"),
    ],
)


# ==========================================
# Register configs to group / 注册配置到分组
# Note: USER_REGISTRATION_ENABLED replaced by features.py tenant_allow_registration
# 注意：USER_REGISTRATION_ENABLED 已由 features.py 的 tenant_allow_registration 替代
# ==========================================

TENANT_FEATURES_GROUP.configs = TENANT_FEATURES_GROUP.configs + [
    USER_REGISTRATION_CAPTCHA_ENABLED,
    USER_DEFAULT_ACTIVE,
    USER_DEFAULT_ROLE_ID,
    USER_PRIVACY_POLICY_URL,
    USER_TERMS_URL,
]


__all__ = [
    "USER_REGISTRATION_ENABLED",
    "USER_REGISTRATION_CAPTCHA_ENABLED",
    "USER_DEFAULT_ACTIVE",
    "USER_REQUIRE_APPROVAL",
    "USER_DEFAULT_ROLE_ID",
    "USER_PRIVACY_POLICY_URL",
    "USER_TERMS_URL",
]
