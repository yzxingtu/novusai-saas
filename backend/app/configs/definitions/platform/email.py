"""
平台邮件设置配置项

包含 SMTP 服务器配置、发件人信息等配置
"""

from app.configs.meta import ConfigMeta, min_value, max_value, max_length, option
from app.configs.definitions.groups import PLATFORM_EMAIL_GROUP
from app.enums.config import ConfigScope, ConfigValueType


# ==========================================
# SMTP 服务器配置
# ==========================================

# SMTP 服务器地址
EMAIL_SMTP_HOST = ConfigMeta(
    key="email_smtp_host",
    name_key="config.platform.email_smtp_host.name",
    description_key="config.platform.email_smtp_host.desc",
    scope=ConfigScope.PLATFORM,
    value_type=ConfigValueType.STRING,
    default_value="",
    validation_rules=[
        max_length(255, "validation.max_length"),
    ],
    sort_order=10,
)

# SMTP 端口
EMAIL_SMTP_PORT = ConfigMeta(
    key="email_smtp_port",
    name_key="config.platform.email_smtp_port.name",
    description_key="config.platform.email_smtp_port.desc",
    scope=ConfigScope.PLATFORM,
    value_type=ConfigValueType.NUMBER,
    default_value=587,
    validation_rules=[
        min_value(1, "validation.min_value"),
        max_value(65535, "validation.max_value"),
    ],
    sort_order=20,
)

# SMTP 加密方式
EMAIL_SMTP_ENCRYPTION = ConfigMeta(
    key="email_smtp_encryption",
    name_key="config.platform.email_smtp_encryption.name",
    description_key="config.platform.email_smtp_encryption.desc",
    scope=ConfigScope.PLATFORM,
    value_type=ConfigValueType.SELECT,
    default_value="tls",
    options=[
        option("none", "config.platform.email_smtp_encryption.none"),
        option("ssl", "config.platform.email_smtp_encryption.ssl"),
        option("tls", "config.platform.email_smtp_encryption.tls"),
    ],
    sort_order=30,
)

# SMTP 用户名
EMAIL_SMTP_USERNAME = ConfigMeta(
    key="email_smtp_username",
    name_key="config.platform.email_smtp_username.name",
    description_key="config.platform.email_smtp_username.desc",
    scope=ConfigScope.PLATFORM,
    value_type=ConfigValueType.STRING,
    default_value="",
    validation_rules=[
        max_length(255, "validation.max_length"),
    ],
    sort_order=40,
)

# SMTP 密码
EMAIL_SMTP_PASSWORD = ConfigMeta(
    key="email_smtp_password",
    name_key="config.platform.email_smtp_password.name",
    description_key="config.platform.email_smtp_password.desc",
    scope=ConfigScope.PLATFORM,
    value_type=ConfigValueType.PASSWORD,
    default_value="",
    is_encrypted=True,
    sort_order=50,
)


# ==========================================
# 发件人配置
# ==========================================

# 发件人邮箱
EMAIL_FROM_ADDRESS = ConfigMeta(
    key="email_from_address",
    name_key="config.platform.email_from_address.name",
    description_key="config.platform.email_from_address.desc",
    scope=ConfigScope.PLATFORM,
    value_type=ConfigValueType.STRING,
    default_value="",
    validation_rules=[
        max_length(255, "validation.max_length"),
    ],
    sort_order=60,
)

# 发件人名称
EMAIL_FROM_NAME = ConfigMeta(
    key="email_from_name",
    name_key="config.platform.email_from_name.name",
    description_key="config.platform.email_from_name.desc",
    scope=ConfigScope.PLATFORM,
    value_type=ConfigValueType.STRING,
    default_value="NovusAI SaaS",
    validation_rules=[
        max_length(100, "validation.max_length"),
    ],
    sort_order=70,
)


# ==========================================
# 邮件功能开关
# ==========================================

# 启用邮件发送
EMAIL_ENABLED = ConfigMeta(
    key="email_enabled",
    name_key="config.platform.email_enabled.name",
    description_key="config.platform.email_enabled.desc",
    scope=ConfigScope.PLATFORM,
    value_type=ConfigValueType.BOOLEAN,
    default_value=False,
    sort_order=80,
)


# ==========================================
# 注册配置到分组
# ==========================================

PLATFORM_EMAIL_GROUP.configs = [
    EMAIL_SMTP_HOST,
    EMAIL_SMTP_PORT,
    EMAIL_SMTP_ENCRYPTION,
    EMAIL_SMTP_USERNAME,
    EMAIL_SMTP_PASSWORD,
    EMAIL_FROM_ADDRESS,
    EMAIL_FROM_NAME,
    EMAIL_ENABLED,
]


__all__ = [
    "EMAIL_SMTP_HOST",
    "EMAIL_SMTP_PORT",
    "EMAIL_SMTP_ENCRYPTION",
    "EMAIL_SMTP_USERNAME",
    "EMAIL_SMTP_PASSWORD",
    "EMAIL_FROM_ADDRESS",
    "EMAIL_FROM_NAME",
    "EMAIL_ENABLED",
]
