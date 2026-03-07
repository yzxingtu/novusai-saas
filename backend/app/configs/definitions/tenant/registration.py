"""
租户用户注册配置项

包含租户级的用户自助注册相关配置
"""

from app.configs.definitions.groups import TENANT_FEATURES_GROUP
from app.configs.meta import ConfigMeta, DisplayRule
from app.enums.config import ConfigScope, ConfigValueType


# ==========================================
# 用户注册
# ==========================================

# 是否开放用户注册
USER_REGISTRATION_ENABLED = ConfigMeta(
    key="user_registration_enabled",
    name_key="config.tenant.user_registration_enabled.name",
    description_key="config.tenant.user_registration_enabled.desc",
    scope=ConfigScope.ALL_TENANTS,
    value_type=ConfigValueType.BOOLEAN,
    default_value=False,
    sort_order=100,
)

# 注册是否需要验证码
USER_REGISTRATION_CAPTCHA_ENABLED = ConfigMeta(
    key="user_registration_captcha_enabled",
    name_key="config.tenant.user_registration_captcha_enabled.name",
    description_key="config.tenant.user_registration_captcha_enabled.desc",
    scope=ConfigScope.ALL_TENANTS,
    value_type=ConfigValueType.BOOLEAN,
    default_value=True,
    sort_order=110,
    display_rules=[
        DisplayRule(field="user_registration_enabled", operator="equals", value=True, action="show"),
    ],
)

# 注册用户是否默认激活
USER_DEFAULT_ACTIVE = ConfigMeta(
    key="user_default_active",
    name_key="config.tenant.user_default_active.name",
    description_key="config.tenant.user_default_active.desc",
    scope=ConfigScope.ALL_TENANTS,
    value_type=ConfigValueType.BOOLEAN,
    default_value=True,
    sort_order=120,
    display_rules=[
        DisplayRule(field="user_registration_enabled", operator="equals", value=True, action="show"),
    ],
)

# 注册是否需要审批
USER_REQUIRE_APPROVAL = ConfigMeta(
    key="user_require_approval",
    name_key="config.tenant.user_require_approval.name",
    description_key="config.tenant.user_require_approval.desc",
    scope=ConfigScope.ALL_TENANTS,
    value_type=ConfigValueType.BOOLEAN,
    default_value=False,
    sort_order=130,
    display_rules=[
        DisplayRule(field="user_registration_enabled", operator="equals", value=True, action="show"),
    ],
)

# 注册用户默认角色 ID（由种子自动设置，管理员可修改）
USER_DEFAULT_ROLE_ID = ConfigMeta(
    key="user_default_role_id",
    name_key="config.tenant.user_default_role_id.name",
    description_key="config.tenant.user_default_role_id.desc",
    scope=ConfigScope.ALL_TENANTS,
    value_type=ConfigValueType.NUMBER,
    default_value=0,
    sort_order=140,
    display_rules=[
        DisplayRule(field="user_registration_enabled", operator="equals", value=True, action="show"),
    ],
)


# ==========================================
# 注册配置到分组
# ==========================================

TENANT_FEATURES_GROUP.configs = TENANT_FEATURES_GROUP.configs + [
    USER_REGISTRATION_ENABLED,
    USER_REGISTRATION_CAPTCHA_ENABLED,
    USER_DEFAULT_ACTIVE,
    USER_REQUIRE_APPROVAL,
    USER_DEFAULT_ROLE_ID,
]


__all__ = [
    "USER_REGISTRATION_ENABLED",
    "USER_REGISTRATION_CAPTCHA_ENABLED",
    "USER_DEFAULT_ACTIVE",
    "USER_REQUIRE_APPROVAL",
    "USER_DEFAULT_ROLE_ID",
]
