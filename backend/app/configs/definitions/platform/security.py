"""
平台安全设置配置项

包含密码策略、登录安全、会话设置等配置

安全配置说明：
1. 密码策略：控制用户密码的安全强度要求
2. 登录安全：防止暴力破解和账户被盗
3. 会话设置：控制用户登录状态和并发访问

配置变更说明：
- 大部分配置修改后即时生效
- 密码策略变更仅对新设置的密码生效，不影响现有密码
- 会话配置变更会影响所有活跃会话

推荐安全配置：
- 密码最小长度：8-12位
- 密码复杂度：medium 或 high
- 登录失败锁定：3-5次
- 锁定时长：15-30分钟
- 会话超时：60-120分钟
"""

from app.configs.meta import ConfigMeta, DisplayRule, min_value, max_value, option
from app.configs.definitions.groups import PLATFORM_SECURITY_GROUP
from app.enums.config import ConfigScope, ConfigValueType


# ==========================================
# 密码策略
# ==========================================

# 密码最小长度
# 控制用户密码的最小字符数，提高密码安全性
# 推荐值：8-12位
# 影响：新密码设置、密码修改
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
# 控制密码必须包含的字符类型组合
# low: 仅限制长度
# medium: 必须包含字母和数字
# high: 必须包含字母、数字和特殊字符
# 推荐值：medium（平衡安全性和用户体验）
# 影响：新密码设置、密码修改
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
# 连续登录失败达到此次数后，账户将被锁定
# 用于防止暴力破解攻击
# 推荐值：3-5次（平衡安全性和用户体验）
# 影响：所有登录接口（平台管理员、租户管理员、租户用户）
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
# 账户被锁定时，需要等待的时间才能重新尝试登录
# 锁定期间无法登录，即使输入正确密码
# 推荐值：15-30分钟
# 影响：登录失败后的账户锁定机制
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
# 登录时是否需要输入验证码
# 可以有效防止自动化攻击
# 推荐值：启用（生产环境建议开启）
# 影响：登录页面的验证码显示
LOGIN_CAPTCHA_ENABLED = ConfigMeta(
    key="login_captcha_enabled",
    name_key="config.platform.login_captcha_enabled.name",
    description_key="config.platform.login_captcha_enabled.desc",
    scope=ConfigScope.PLATFORM,
    value_type=ConfigValueType.BOOLEAN,
    default_value=True,
    sort_order=60,
)

# 验证码难度
# 控制图形验证码的复杂度（示例：easy/medium/hard）
# 可用于调整字符长度、干扰线、噪点等参数
CAPTCHA_DIFFICULTY = ConfigMeta(
    key="captcha_difficulty",
    name_key="config.platform.captcha_difficulty.name",
    description_key="config.platform.captcha_difficulty.desc",
    scope=ConfigScope.PLATFORM,
    value_type=ConfigValueType.SELECT,
    default_value="medium",
    options=[
        option("easy", "config.platform.captcha_difficulty.easy"),
        option("medium", "config.platform.captcha_difficulty.medium"),
        option("hard", "config.platform.captcha_difficulty.hard"),
    ],
    sort_order=65,
    display_rules=[
        DisplayRule(field="login_captcha_enabled", operator="equals", value=True, action="show"),
    ],
)

# 验证码启用阈值（管理员端）
# 当登录失败计数达到此阈值后启用验证码
# 0 表示始终根据开关决定是否启用；>=1 表示达到失败次数后强制启用
CAPTCHA_ENABLE_THRESHOLD_ADMIN = ConfigMeta(
    key="captcha_enable_threshold_admin",
    name_key="config.platform.captcha_enable_threshold_admin.name",
    description_key="config.platform.captcha_enable_threshold_admin.desc",
    scope=ConfigScope.PLATFORM,
    value_type=ConfigValueType.NUMBER,
    default_value=2,
    validation_rules=[
        min_value(0, "validation.min_value"),
        max_value(10, "validation.max_value"),
    ],
    sort_order=66,
    display_rules=[
        DisplayRule(field="login_captcha_enabled", operator="equals", value=True, action="show"),
    ],
)

# ==========================================
# 会话设置
# ==========================================

# 会话超时时间（分钟）
# 用户无操作后自动退出登录的时间
# 防止无人值守的会话被滥用
# 推荐值：60-120分钟（平衡安全性和用户体验）
# 影响：JWT token过期时间，所有用户的活跃会话
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
# 单个用户最多可以同时在多少个设备上登录
# 0表示不限制，推荐生产环境设置1-3个
# 超过限制时，新登录会踢出最早的登录
# 推荐值：1-3个设备（根据业务需求调整）
# 影响：用户登录时的设备数量检查
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
    "CAPTCHA_DIFFICULTY",
    "CAPTCHA_ENABLE_THRESHOLD_ADMIN",
    "SESSION_TIMEOUT_MINUTES",
    "SESSION_MAX_DEVICES",
]
