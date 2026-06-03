"""Tenant registration config items / 企业注册配置项

Includes tenant-level registration flow and legal document configs.
包含企业级的注册流程与法律文档配置
"""

from app.configs.definitions.groups import TENANT_REGISTRATION_GROUP
from app.configs.meta import ConfigMeta, ConfigOption, DisplayRule, max_length
from app.enums.config import ConfigScope, ConfigValueType

# Whether tenant allows user self-registration / 企业是否允许用户自助注册
TENANT_ALLOW_REGISTRATION = ConfigMeta(
    key="tenant_allow_registration",
    name_key="config.tenant.allow_registration.name",
    description_key="config.tenant.allow_registration.desc",
    scope=ConfigScope.ALL_TENANTS,
    value_type=ConfigValueType.BOOLEAN,
    default_value=True,
    sort_order=10,
)

# Whether new users require approval / 新用户是否需要审批
TENANT_REGISTRATION_APPROVAL = ConfigMeta(
    key="tenant_registration_approval",
    name_key="config.tenant.registration_approval.name",
    description_key="config.tenant.registration_approval.desc",
    scope=ConfigScope.ALL_TENANTS,
    value_type=ConfigValueType.BOOLEAN,
    default_value=False,
    sort_order=20,
    display_rules=[
        DisplayRule(
            field="tenant_allow_registration",
            operator="equals",
            value=True,
            action="show",
        ),
    ],
)

# Whether registration requires captcha / 注册是否需要验证码
USER_REGISTRATION_CAPTCHA_ENABLED = ConfigMeta(
    key="user_registration_captcha_enabled",
    name_key="config.tenant.user_registration_captcha_enabled.name",
    description_key="config.tenant.user_registration_captcha_enabled.desc",
    scope=ConfigScope.ALL_TENANTS,
    value_type=ConfigValueType.BOOLEAN,
    default_value=True,
    sort_order=30,
    display_rules=[
        DisplayRule(
            field="tenant_allow_registration",
            operator="equals",
            value=True,
            action="show",
        ),
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
    sort_order=40,
    display_rules=[
        DisplayRule(
            field="tenant_allow_registration",
            operator="equals",
            value=True,
            action="show",
        ),
    ],
)

# Default role ID for registered users / 注册用户默认角色 ID
USER_DEFAULT_ROLE_ID = ConfigMeta(
    key="user_default_role_id",
    name_key="config.tenant.user_default_role_id.name",
    description_key="config.tenant.user_default_role_id.desc",
    scope=ConfigScope.ALL_TENANTS,
    value_type=ConfigValueType.SELECT,
    default_value=0,
    sort_order=50,
    options=[
        ConfigOption(
            value=0, label_key="config.tenant.user_default_role_id.option_none"
        ),
    ],
    allow_dynamic_options=True,
    display_rules=[
        DisplayRule(
            field="tenant_allow_registration",
            operator="equals",
            value=True,
            action="show",
        ),
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
    sort_order=60,
    display_rules=[
        DisplayRule(
            field="tenant_allow_registration",
            operator="equals",
            value=True,
            action="show",
        ),
    ],
)

# Privacy policy body (HTML, shown on user site) / 隐私政策正文（HTML，用户端站内展示）
USER_PRIVACY_POLICY_HTML = ConfigMeta(
    key="user_privacy_policy_html",
    name_key="config.tenant.user_privacy_policy_html.name",
    description_key="config.tenant.user_privacy_policy_html.desc",
    scope=ConfigScope.ALL_TENANTS,
    value_type=ConfigValueType.HTML,
    default_value="",
    validation_rules=[
        max_length(200_000, "validation.max_length"),
    ],
    sort_order=70,
    display_rules=[
        DisplayRule(
            field="tenant_allow_registration",
            operator="equals",
            value=True,
            action="show",
        ),
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
    sort_order=80,
    display_rules=[
        DisplayRule(
            field="tenant_allow_registration",
            operator="equals",
            value=True,
            action="show",
        ),
    ],
)

# Terms of service body (HTML) / 服务条款正文（HTML）
USER_TERMS_HTML = ConfigMeta(
    key="user_terms_html",
    name_key="config.tenant.user_terms_html.name",
    description_key="config.tenant.user_terms_html.desc",
    scope=ConfigScope.ALL_TENANTS,
    value_type=ConfigValueType.HTML,
    default_value="",
    validation_rules=[
        max_length(200_000, "validation.max_length"),
    ],
    sort_order=90,
    display_rules=[
        DisplayRule(
            field="tenant_allow_registration",
            operator="equals",
            value=True,
            action="show",
        ),
    ],
)


TENANT_REGISTRATION_GROUP.configs = [
    TENANT_ALLOW_REGISTRATION,
    TENANT_REGISTRATION_APPROVAL,
    USER_REGISTRATION_CAPTCHA_ENABLED,
    USER_DEFAULT_ACTIVE,
    USER_DEFAULT_ROLE_ID,
    USER_PRIVACY_POLICY_URL,
    USER_PRIVACY_POLICY_HTML,
    USER_TERMS_URL,
    USER_TERMS_HTML,
]


__all__ = [
    "TENANT_ALLOW_REGISTRATION",
    "TENANT_REGISTRATION_APPROVAL",
    "USER_REGISTRATION_CAPTCHA_ENABLED",
    "USER_DEFAULT_ACTIVE",
    "USER_DEFAULT_ROLE_ID",
    "USER_PRIVACY_POLICY_URL",
    "USER_TERMS_URL",
    "USER_PRIVACY_POLICY_HTML",
    "USER_TERMS_HTML",
]
