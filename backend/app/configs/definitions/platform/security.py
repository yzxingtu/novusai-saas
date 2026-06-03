"""Platform security settings config items / 平台安全设置配置项

Includes password policy, login security, session settings, etc.
包含密码策略、登录安全、会话设置等配置

Security config notes / 安全配置说明：
1. Password policy: controls password strength requirements / 密码策略：控制密码安全强度
2. Login security: prevents brute force and account theft / 登录安全：防止暴力破解
3. Session settings: controls login state and concurrent access / 会话设置：控制登录状态和并发

Config change notes / 配置变更说明：
- Most configs take effect immediately / 大部分配置修改后即时生效
- Password policy changes only affect new passwords / 密码策略变更仅对新密码生效
- Session config changes affect all active sessions / 会话配置变更影响所有活跃会话

Recommended security settings / 推荐安全配置：
- Min password length / 密码最小长度：8-12
- Password complexity / 密码复杂度：medium or high
- Login failure lockout / 登录失败锁定：3-5 attempts
- Lockout duration / 锁定时长：15-30 minutes
- Session timeout / 会话超时：60-120 minutes
"""

from app.configs.definitions.groups import PLATFORM_SECURITY_GROUP
from app.configs.meta import ConfigMeta, DisplayRule, max_value, min_value, option
from app.enums.config import ConfigScope, ConfigValueType

# ==========================================
# Password policy / 密码策略
# ==========================================

# Min password length / 密码最小长度
# Controls minimum characters for user passwords / 控制密码最小字符数
# Recommended: 8-12 / 推荐值：8-12位
# Affects: new password setting, password change / 影响：新密码设置、密码修改
PASSWORD_MIN_LENGTH = ConfigMeta(
    key="password_min_length",
    name_key="config.platform.password_min_length.name",
    description_key="config.platform.password_min_length.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.NUMBER,
    default_value=8,
    is_required=True,
    validation_rules=[
        min_value(6, "validation.min_value"),
        max_value(32, "validation.max_value"),
    ],
    sort_order=10,
)

# Password complexity / 密码复杂度要求
# Controls required character type combinations / 控制密码字符类型组合
# low: length only / 仅限制长度
# medium: letters + digits / 必须包含字母和数字
# high: letters + digits + special chars / 必须包含字母、数字和特殊字符
# Recommended: medium (balance security & UX) / 推荐：medium
# Affects: new password setting, password change / 影响：新密码设置、密码修改
PASSWORD_COMPLEXITY = ConfigMeta(
    key="password_complexity",
    name_key="config.platform.password_complexity.name",
    description_key="config.platform.password_complexity.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.SELECT,
    default_value="medium",
    options=[
        option("low", "config.platform.password_complexity.low"),
        option("medium", "config.platform.password_complexity.medium"),
        option("high", "config.platform.password_complexity.high"),
    ],
    sort_order=20,
)

# Password expiry days (0 = never expires) / 密码过期天数（0 = 永不过期）
PASSWORD_EXPIRY_DAYS = ConfigMeta(
    key="password_expiry_days",
    name_key="config.platform.password_expiry_days.name",
    description_key="config.platform.password_expiry_days.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.NUMBER,
    default_value=0,
    validation_rules=[
        min_value(0, "validation.min_value"),
        max_value(365, "validation.max_value"),
    ],
    sort_order=30,
)


# ==========================================
# Login security / 登录安全
# ==========================================

# Login failure lockout attempts / 登录失败锁定次数
# Account locked after this many consecutive failures / 连续失败达此次数后锁定
# Prevents brute force attacks / 防止暴力破解
# Recommended: 3-5 (balance security & UX) / 推荐：3-5次
# Affects: all login endpoints / 影响：所有登录接口
LOGIN_MAX_ATTEMPTS = ConfigMeta(
    key="login_max_attempts",
    name_key="config.platform.login_max_attempts.name",
    description_key="config.platform.login_max_attempts.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.NUMBER,
    default_value=5,
    is_required=True,
    validation_rules=[
        min_value(3, "validation.min_value"),
        max_value(20, "validation.max_value"),
    ],
    sort_order=40,
)

# Account lockout duration (minutes) / 账户锁定时长（分钟）
# Wait time before retrying login after lockout / 锁定后重试等待时间
# Cannot login during lockout even with correct password / 锁定期间无法登录
# Recommended: 15-30 minutes / 推荐：15-30分钟
# Affects: account lockout mechanism / 影响：账户锁定机制
LOGIN_LOCKOUT_MINUTES = ConfigMeta(
    key="login_lockout_minutes",
    name_key="config.platform.login_lockout_minutes.name",
    description_key="config.platform.login_lockout_minutes.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.NUMBER,
    default_value=30,
    is_required=True,
    validation_rules=[
        min_value(5, "validation.min_value"),
        max_value(1440, "validation.max_value"),
    ],
    sort_order=50,
)

# Enable captcha / 启用验证码
# Whether captcha is required on login / 登录时是否需要验证码
# Effectively prevents automated attacks / 有效防止自动化攻击
# Recommended: enabled (for production) / 推荐：启用
# Affects: captcha display on login page / 影响：登录页验证码显示
LOGIN_CAPTCHA_ENABLED = ConfigMeta(
    key="login_captcha_enabled",
    name_key="config.platform.login_captcha_enabled.name",
    description_key="config.platform.login_captcha_enabled.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.BOOLEAN,
    default_value=True,
    sort_order=60,
)

# Captcha driver / 验证码驱动
# Choose captcha implementation / 选择验证码实现方式
# image: local image captcha / 本地图形验证码
CAPTCHA_PROVIDER = ConfigMeta(
    key="captcha_provider",
    name_key="config.platform.captcha_provider.name",
    description_key="config.platform.captcha_provider.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.SELECT,
    default_value="image",
    options=[
        option("image", "config.platform.captcha_provider.image"),
    ],
    sort_order=62,
    display_rules=[
        DisplayRule(
            field="login_captcha_enabled", operator="equals", value=True, action="show"
        ),
    ],
)

# Captcha difficulty / 验证码难度
# Controls image captcha complexity (easy/medium/hard) / 控制图形验证码复杂度
# Adjusts character length, interference lines, noise, etc. / 调整字符长度、干扰线、噪点等
CAPTCHA_DIFFICULTY = ConfigMeta(
    key="captcha_difficulty",
    name_key="config.platform.captcha_difficulty.name",
    description_key="config.platform.captcha_difficulty.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.SELECT,
    default_value="medium",
    options=[
        option("easy", "config.platform.captcha_difficulty.easy"),
        option("medium", "config.platform.captcha_difficulty.medium"),
        option("hard", "config.platform.captcha_difficulty.hard"),
    ],
    sort_order=65,
    display_rules=[
        DisplayRule(
            field="login_captcha_enabled", operator="equals", value=True, action="show"
        ),
    ],
)

# Captcha enable threshold (admin) / 验证码启用阈值（管理员端）
# Enable captcha after this many login failures / 登录失败达此阈值后启用
# 0 = follow toggle; >=1 = force after failures / 0=根据开关；>=1=失败后强制启用
CAPTCHA_ENABLE_THRESHOLD_ADMIN = ConfigMeta(
    key="captcha_enable_threshold_admin",
    name_key="config.platform.captcha_enable_threshold_admin.name",
    description_key="config.platform.captcha_enable_threshold_admin.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.NUMBER,
    default_value=2,
    validation_rules=[
        min_value(0, "validation.min_value"),
        max_value(10, "validation.max_value"),
    ],
    sort_order=66,
    display_rules=[
        DisplayRule(
            field="login_captcha_enabled", operator="equals", value=True, action="show"
        ),
    ],
)

# ==========================================
# Session settings / 会话设置
# ==========================================

# Session timeout (minutes) / 会话超时时间（分钟）
# Auto-logout after inactivity / 无操作后自动退出
# Prevents unattended session abuse / 防止无人值守会话被滥用
# Recommended: 60-120 min / 推荐：60-120分钟
# Affects: JWT token expiry, all active sessions / 影响：JWT 过期时间、所有活跃会话
SESSION_TIMEOUT_MINUTES = ConfigMeta(
    key="session_timeout_minutes",
    name_key="config.platform.session_timeout_minutes.name",
    description_key="config.platform.session_timeout_minutes.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.NUMBER,
    default_value=120,
    is_required=True,
    validation_rules=[
        min_value(15, "validation.min_value"),
        max_value(1440, "validation.max_value"),
    ],
    sort_order=70,
)

# Max concurrent login devices (0 = unlimited) / 允许同时登录设备数（0=不限制）
# Max devices a single user can be logged in on / 单用户最多同时登录设备数
# 0=unlimited; recommend 1-3 for production / 0=不限制，推荐生产环境 1-3
# New login kicks out the oldest when limit exceeded / 超出限制时新登录踢出最早登录
# Recommended: 1-3 devices / 推荐：1-3个设备
# Affects: device count check on login / 影响：登录时设备数检查
SESSION_MAX_DEVICES = ConfigMeta(
    key="session_max_devices",
    name_key="config.platform.session_max_devices.name",
    description_key="config.platform.session_max_devices.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.NUMBER,
    default_value=0,
    validation_rules=[
        min_value(0, "validation.min_value"),
        max_value(10, "validation.max_value"),
    ],
    sort_order=80,
)


# ==========================================
# Register configs to group / 注册配置到分组
# ==========================================

PLATFORM_SECURITY_GROUP.configs = [
    PASSWORD_MIN_LENGTH,
    PASSWORD_COMPLEXITY,
    PASSWORD_EXPIRY_DAYS,
    LOGIN_MAX_ATTEMPTS,
    LOGIN_LOCKOUT_MINUTES,
    LOGIN_CAPTCHA_ENABLED,
    CAPTCHA_PROVIDER,
    CAPTCHA_DIFFICULTY,
    CAPTCHA_ENABLE_THRESHOLD_ADMIN,
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
    "CAPTCHA_PROVIDER",
    "CAPTCHA_DIFFICULTY",
    "CAPTCHA_ENABLE_THRESHOLD_ADMIN",
    "SESSION_TIMEOUT_MINUTES",
    "SESSION_MAX_DEVICES",
]
