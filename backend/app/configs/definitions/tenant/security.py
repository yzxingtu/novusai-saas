"""Tenant security settings config items / 企业安全设置配置项

Includes tenant-level login security, password policy, etc.
包含企业级的登录安全、密码策略等配置
"""

from app.configs.definitions.groups import TENANT_GENERAL_GROUP
from app.configs.meta import ConfigMeta, DisplayRule, max_value, min_value, option
from app.enums.config import ConfigScope, ConfigValueType

# ==========================================
# Login security / 登录安全
# ==========================================

# Enable captcha / 启用验证码
TENANT_CAPTCHA_ENABLED = ConfigMeta(
    key="tenant_captcha_enabled",
    name_key="config.tenant.captcha_enabled.name",
    description_key="config.tenant.captcha_enabled.desc",
    scope=ConfigScope.ALL_TENANTS,
    value_type=ConfigValueType.BOOLEAN,
    default_value=True,
    sort_order=10,
)

# Enable captcha for user login / 启用用户端登录验证码
USER_LOGIN_CAPTCHA_ENABLED = ConfigMeta(
    key="user_login_captcha_enabled",
    name_key="config.tenant.user_login_captcha_enabled.name",
    description_key="config.tenant.user_login_captcha_enabled.desc",
    scope=ConfigScope.ALL_TENANTS,
    value_type=ConfigValueType.BOOLEAN,
    default_value=True,
    sort_order=11,
)

# Shared captcha driver (tenant admin + user login) / 企业管理员与用户登录共享验证码驱动
TENANT_CAPTCHA_PROVIDER = ConfigMeta(
    key="tenant_captcha_provider",
    name_key="config.tenant.captcha_provider.name",
    description_key="config.tenant.captcha_provider.desc",
    scope=ConfigScope.ALL_TENANTS,
    value_type=ConfigValueType.SELECT,
    default_value="image",
    options=[
        option("image", "config.tenant.captcha_provider.image"),
    ],
    sort_order=12,
)

# Shared captcha difficulty (tenant admin + user login) / 企业管理员与用户登录共享验证码难度
TENANT_CAPTCHA_DIFFICULTY = ConfigMeta(
    key="tenant_captcha_difficulty",
    name_key="config.tenant.captcha_difficulty.name",
    description_key="config.tenant.captcha_difficulty.desc",
    scope=ConfigScope.ALL_TENANTS,
    value_type=ConfigValueType.SELECT,
    default_value="medium",
    options=[
        option("easy", "config.tenant.captcha_difficulty.easy"),
        option("medium", "config.tenant.captcha_difficulty.medium"),
        option("hard", "config.tenant.captcha_difficulty.hard"),
    ],
    sort_order=15,
)

# User login captcha enable threshold / 用户端登录验证码启用阈值
USER_LOGIN_CAPTCHA_ENABLE_THRESHOLD = ConfigMeta(
    key="user_login_captcha_enable_threshold",
    name_key="config.tenant.user_login_captcha_enable_threshold.name",
    description_key="config.tenant.user_login_captcha_enable_threshold.desc",
    scope=ConfigScope.ALL_TENANTS,
    value_type=ConfigValueType.NUMBER,
    default_value=0,
    validation_rules=[
        min_value(0, "validation.min_value"),
        max_value(10, "validation.max_value"),
    ],
    sort_order=16,
    display_rules=[
        DisplayRule(
            field="user_login_captcha_enabled",
            operator="equals",
            value=True,
            action="show",
        ),
    ],
)

# Allowed login methods / 允许的登录方式
TENANT_LOGIN_METHODS = ConfigMeta(
    key="tenant_login_methods",
    name_key="config.tenant.login_methods.name",
    description_key="config.tenant.login_methods.desc",
    scope=ConfigScope.ALL_TENANTS,
    value_type=ConfigValueType.MULTI_SELECT,
    default_value=["password", "sms"],
    options=[
        option("password", "config.tenant.login_methods.password"),
        option("sms", "config.tenant.login_methods.sms"),
        option("email", "config.tenant.login_methods.email"),
        option("wechat", "config.tenant.login_methods.wechat"),
        option("dingtalk", "config.tenant.login_methods.dingtalk"),
    ],
    sort_order=20,
)

# Login failure lockout attempts (overrides platform default) / 登录失败锁定次数（覆盖平台默认）
TENANT_LOGIN_MAX_ATTEMPTS = ConfigMeta(
    key="tenant_login_max_attempts",
    name_key="config.tenant.login_max_attempts.name",
    description_key="config.tenant.login_max_attempts.desc",
    scope=ConfigScope.ALL_TENANTS,
    value_type=ConfigValueType.NUMBER,
    default_value=5,
    validation_rules=[
        min_value(3, "validation.min_value"),
        max_value(20, "validation.max_value"),
    ],
    sort_order=30,
)

# Account lockout duration (minutes) / 账户锁定时长（分钟）
TENANT_LOGIN_LOCKOUT_MINUTES = ConfigMeta(
    key="tenant_login_lockout_minutes",
    name_key="config.tenant.login_lockout_minutes.name",
    description_key="config.tenant.login_lockout_minutes.desc",
    scope=ConfigScope.ALL_TENANTS,
    value_type=ConfigValueType.NUMBER,
    default_value=30,
    validation_rules=[
        min_value(5, "validation.min_value"),
        max_value(1440, "validation.max_value"),
    ],
    sort_order=40,
)

# Tenant admin login captcha enable threshold / 企业管理员登录验证码启用阈值
TENANT_CAPTCHA_ENABLE_THRESHOLD = ConfigMeta(
    key="tenant_captcha_enable_threshold",
    name_key="config.tenant.captcha_enable_threshold.name",
    description_key="config.tenant.captcha_enable_threshold.desc",
    scope=ConfigScope.ALL_TENANTS,
    value_type=ConfigValueType.NUMBER,
    default_value=2,
    validation_rules=[
        min_value(0, "validation.min_value"),
        max_value(10, "validation.max_value"),
    ],
    sort_order=45,
)


# ==========================================
# Password policy / 密码策略
# ==========================================

# Min password length / 密码最小长度
TENANT_PASSWORD_MIN_LENGTH = ConfigMeta(
    key="tenant_password_min_length",
    name_key="config.tenant.password_min_length.name",
    description_key="config.tenant.password_min_length.desc",
    scope=ConfigScope.ALL_TENANTS,
    value_type=ConfigValueType.NUMBER,
    default_value=8,
    validation_rules=[
        min_value(6, "validation.min_value"),
        max_value(32, "validation.max_value"),
    ],
    sort_order=50,
)

# Password complexity / 密码复杂度要求
TENANT_PASSWORD_COMPLEXITY = ConfigMeta(
    key="tenant_password_complexity",
    name_key="config.tenant.password_complexity.name",
    description_key="config.tenant.password_complexity.desc",
    scope=ConfigScope.ALL_TENANTS,
    value_type=ConfigValueType.SELECT,
    default_value="medium",
    options=[
        option("low", "config.tenant.password_complexity.low"),
        option("medium", "config.tenant.password_complexity.medium"),
        option("high", "config.tenant.password_complexity.high"),
    ],
    sort_order=60,
)


# ==========================================
# Session settings / 会话设置
# ==========================================

# Session timeout (minutes) / 会话超时时间（分钟）
TENANT_SESSION_TIMEOUT = ConfigMeta(
    key="tenant_session_timeout",
    name_key="config.tenant.session_timeout.name",
    description_key="config.tenant.session_timeout.desc",
    scope=ConfigScope.ALL_TENANTS,
    value_type=ConfigValueType.NUMBER,
    default_value=120,
    validation_rules=[
        min_value(15, "validation.min_value"),
        max_value(1440, "validation.max_value"),
    ],
    sort_order=70,
)


# ==========================================
# Register configs to group / 注册配置到分组
# ==========================================

TENANT_GENERAL_GROUP.configs = [
    TENANT_CAPTCHA_ENABLED,
    USER_LOGIN_CAPTCHA_ENABLED,
    TENANT_CAPTCHA_PROVIDER,
    TENANT_CAPTCHA_DIFFICULTY,
    USER_LOGIN_CAPTCHA_ENABLE_THRESHOLD,
    TENANT_LOGIN_METHODS,
    TENANT_LOGIN_MAX_ATTEMPTS,
    TENANT_LOGIN_LOCKOUT_MINUTES,
    TENANT_CAPTCHA_ENABLE_THRESHOLD,
    TENANT_PASSWORD_MIN_LENGTH,
    TENANT_PASSWORD_COMPLEXITY,
    TENANT_SESSION_TIMEOUT,
]


__all__ = [
    "TENANT_CAPTCHA_ENABLED",
    "USER_LOGIN_CAPTCHA_ENABLED",
    "TENANT_CAPTCHA_PROVIDER",
    "TENANT_CAPTCHA_DIFFICULTY",
    "USER_LOGIN_CAPTCHA_ENABLE_THRESHOLD",
    "TENANT_LOGIN_METHODS",
    "TENANT_LOGIN_MAX_ATTEMPTS",
    "TENANT_LOGIN_LOCKOUT_MINUTES",
    "TENANT_CAPTCHA_ENABLE_THRESHOLD",
    "TENANT_PASSWORD_MIN_LENGTH",
    "TENANT_PASSWORD_COMPLEXITY",
    "TENANT_SESSION_TIMEOUT",
]
