"""
平台安全设置配置项

包含密码策略、登录安全、会话设置等配置
"""

from app.configs.meta import ConfigMeta, min_value, max_value, option
from app.configs.definitions.groups import PLATFORM_SECURITY_GROUP
from app.enums.config import ConfigScope, ConfigValueType


# ==========================================
# 密码策略
# ==========================================

# 密码最小长度
PASSWORD_MIN_LENGTH = ConfigMeta(
    key="password_min_length",
    name_key="config.platform.password_min_length.name",
    description_key="config.platform.password_min_length.desc",
    scope=ConfigScope.PLATFORM,
    value_type=ConfigValueType.NUMBER,
    default_value=8,
    is_required=True,
    validation_rules=[
        min_value(6, "validation.min_value"),
        max_value(32, "validation.max_value"),
    ],
    sort_order=10,
)

# 密码复杂度要求
PASSWORD_COMPLEXITY = ConfigMeta(
    key="password_complexity",
    name_key="config.platform.password_complexity.name",
    description_key="config.platform.password_complexity.desc",
    scope=ConfigScope.PLATFORM,
    value_type=ConfigValueType.SELECT,
    default_value="medium",
    options=[
        option("low", "config.platform.password_complexity.low"),
        option("medium", "config.platform.password_complexity.medium"),
        option("high", "config.platform.password_complexity.high"),
    ],
    sort_order=20,
)

# 密码过期天数（0 表示永不过期）
PASSWORD_EXPIRY_DAYS = ConfigMeta(
    key="password_expiry_days",
    name_key="config.platform.password_expiry_days.name",
    description_key="config.platform.password_expiry_days.desc",
    scope=ConfigScope.PLATFORM,
    value_type=ConfigValueType.NUMBER,
    default_value=0,
    validation_rules=[
        min_value(0, "validation.min_value"),
        max_value(365, "validation.max_value"),
    ],
    sort_order=30,
)


# ==========================================
# 登录安全
# ==========================================

# 登录失败锁定次数
LOGIN_MAX_ATTEMPTS = ConfigMeta(
    key="login_max_attempts",
    name_key="config.platform.login_max_attempts.name",
    description_key="config.platform.login_max_attempts.desc",
    scope=ConfigScope.PLATFORM,
    value_type=ConfigValueType.NUMBER,
    default_value=5,
    is_required=True,
    validation_rules=[
        min_value(3, "validation.min_value"),
        max_value(20, "validation.max_value"),
    ],
    sort_order=40,
)

# 账户锁定时长（分钟）
LOGIN_LOCKOUT_MINUTES = ConfigMeta(
    key="login_lockout_minutes",
    name_key="config.platform.login_lockout_minutes.name",
    description_key="config.platform.login_lockout_minutes.desc",
    scope=ConfigScope.PLATFORM,
    value_type=ConfigValueType.NUMBER,
    default_value=30,
    is_required=True,
    validation_rules=[
        min_value(5, "validation.min_value"),
        max_value(1440, "validation.max_value"),
    ],
    sort_order=50,
)

# 启用验证码
LOGIN_CAPTCHA_ENABLED = ConfigMeta(
    key="login_captcha_enabled",
    name_key="config.platform.login_captcha_enabled.name",
    description_key="config.platform.login_captcha_enabled.desc",
    scope=ConfigScope.PLATFORM,
    value_type=ConfigValueType.BOOLEAN,
    default_value=True,
    sort_order=60,
)


# ==========================================
# 会话设置
# ==========================================

# 会话超时时间（分钟）
SESSION_TIMEOUT_MINUTES = ConfigMeta(
    key="session_timeout_minutes",
    name_key="config.platform.session_timeout_minutes.name",
    description_key="config.platform.session_timeout_minutes.desc",
    scope=ConfigScope.PLATFORM,
    value_type=ConfigValueType.NUMBER,
    default_value=120,
    is_required=True,
    validation_rules=[
        min_value(15, "validation.min_value"),
        max_value(1440, "validation.max_value"),
    ],
    sort_order=70,
)

# 允许同时登录的设备数（0 表示不限制）
SESSION_MAX_DEVICES = ConfigMeta(
    key="session_max_devices",
    name_key="config.platform.session_max_devices.name",
    description_key="config.platform.session_max_devices.desc",
    scope=ConfigScope.PLATFORM,
    value_type=ConfigValueType.NUMBER,
    default_value=0,
    validation_rules=[
        min_value(0, "validation.min_value"),
        max_value(10, "validation.max_value"),
    ],
    sort_order=80,
)


# ==========================================
# 注册配置到分组
# ==========================================

PLATFORM_SECURITY_GROUP.configs = [
    PASSWORD_MIN_LENGTH,
    PASSWORD_COMPLEXITY,
    PASSWORD_EXPIRY_DAYS,
    LOGIN_MAX_ATTEMPTS,
    LOGIN_LOCKOUT_MINUTES,
    LOGIN_CAPTCHA_ENABLED,
    SESSION_TIMEOUT_MINUTES,
    SESSION_MAX_DEVICES,
]


__all__ = [
    "PASSWORD_MIN_LENGTH",
    "PASSWORD_COMPLEXITY",
    "PASSWORD_EXPIRY_DAYS",
    "LOGIN_MAX_ATTEMPTS",
    "LOGIN_LOCKOUT_MINUTES",
    "LOGIN_CAPTCHA_ENABLED",
    "SESSION_TIMEOUT_MINUTES",
    "SESSION_MAX_DEVICES",
]
