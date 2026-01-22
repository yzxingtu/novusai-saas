"""
租户安全设置配置项

包含租户级的登录安全、密码策略等配置
"""

from app.configs.meta import ConfigMeta, min_value, max_value, option
from app.configs.definitions.groups import TENANT_GENERAL_GROUP
from app.enums.config import ConfigScope, ConfigValueType


# ==========================================
# 登录安全
# ==========================================

# 启用验证码
TENANT_CAPTCHA_ENABLED = ConfigMeta(
    key="tenant_captcha_enabled",
    name_key="config.tenant.captcha_enabled.name",
    description_key="config.tenant.captcha_enabled.desc",
    scope=ConfigScope.TENANT,
    value_type=ConfigValueType.BOOLEAN,
    default_value=True,
    sort_order=10,
)

# 允许的登录方式
TENANT_LOGIN_METHODS = ConfigMeta(
    key="tenant_login_methods",
    name_key="config.tenant.login_methods.name",
    description_key="config.tenant.login_methods.desc",
    scope=ConfigScope.TENANT,
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

# 登录失败锁定次数（覆盖平台默认）
TENANT_LOGIN_MAX_ATTEMPTS = ConfigMeta(
    key="tenant_login_max_attempts",
    name_key="config.tenant.login_max_attempts.name",
    description_key="config.tenant.login_max_attempts.desc",
    scope=ConfigScope.TENANT,
    value_type=ConfigValueType.NUMBER,
    default_value=5,
    validation_rules=[
        min_value(3, "validation.min_value"),
        max_value(20, "validation.max_value"),
    ],
    sort_order=30,
)

# 账户锁定时长（分钟）
TENANT_LOGIN_LOCKOUT_MINUTES = ConfigMeta(
    key="tenant_login_lockout_minutes",
    name_key="config.tenant.login_lockout_minutes.name",
    description_key="config.tenant.login_lockout_minutes.desc",
    scope=ConfigScope.TENANT,
    value_type=ConfigValueType.NUMBER,
    default_value=30,
    validation_rules=[
        min_value(5, "validation.min_value"),
        max_value(1440, "validation.max_value"),
    ],
    sort_order=40,
)


# ==========================================
# 密码策略
# ==========================================

# 密码最小长度
TENANT_PASSWORD_MIN_LENGTH = ConfigMeta(
    key="tenant_password_min_length",
    name_key="config.tenant.password_min_length.name",
    description_key="config.tenant.password_min_length.desc",
    scope=ConfigScope.TENANT,
    value_type=ConfigValueType.NUMBER,
    default_value=8,
    validation_rules=[
        min_value(6, "validation.min_value"),
        max_value(32, "validation.max_value"),
    ],
    sort_order=50,
)

# 密码复杂度要求
TENANT_PASSWORD_COMPLEXITY = ConfigMeta(
    key="tenant_password_complexity",
    name_key="config.tenant.password_complexity.name",
    description_key="config.tenant.password_complexity.desc",
    scope=ConfigScope.TENANT,
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
# 会话设置
# ==========================================

# 会话超时时间（分钟）
TENANT_SESSION_TIMEOUT = ConfigMeta(
    key="tenant_session_timeout",
    name_key="config.tenant.session_timeout.name",
    description_key="config.tenant.session_timeout.desc",
    scope=ConfigScope.TENANT,
    value_type=ConfigValueType.NUMBER,
    default_value=120,
    validation_rules=[
        min_value(15, "validation.min_value"),
        max_value(1440, "validation.max_value"),
    ],
    sort_order=70,
)


# ==========================================
# 注册配置到分组
# ==========================================

TENANT_GENERAL_GROUP.configs = [
    TENANT_CAPTCHA_ENABLED,
    TENANT_LOGIN_METHODS,
    TENANT_LOGIN_MAX_ATTEMPTS,
    TENANT_LOGIN_LOCKOUT_MINUTES,
    TENANT_PASSWORD_MIN_LENGTH,
    TENANT_PASSWORD_COMPLEXITY,
    TENANT_SESSION_TIMEOUT,
]


__all__ = [
    "TENANT_CAPTCHA_ENABLED",
    "TENANT_LOGIN_METHODS",
    "TENANT_LOGIN_MAX_ATTEMPTS",
    "TENANT_LOGIN_LOCKOUT_MINUTES",
    "TENANT_PASSWORD_MIN_LENGTH",
    "TENANT_PASSWORD_COMPLEXITY",
    "TENANT_SESSION_TIMEOUT",
]
