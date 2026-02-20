"""
平台 SSL 证书管理配置项

包含 ACME/Let's Encrypt 连接配置、自动续期策略等
"""

from app.configs.meta import ConfigMeta, ConfigOption
from app.configs.definitions.groups import PLATFORM_SSL_GROUP
from app.enums.config import ConfigScope, ConfigValueType


# ==========================================
# ACME 服务配置
# ==========================================

# ACME 账户邮箱
ACME_ACCOUNT_EMAIL = ConfigMeta(
    key="acme_account_email",
    name_key="config.platform.ssl.acme_account_email.name",
    description_key="config.platform.ssl.acme_account_email.desc",
    scope=ConfigScope.PLATFORM,
    value_type=ConfigValueType.STRING,
    default_value="",
    is_required=True,
    sort_order=10,
)

# ACME 环境模式
ACME_USE_STAGING = ConfigMeta(
    key="acme_use_staging",
    name_key="config.platform.ssl.acme_use_staging.name",
    description_key="config.platform.ssl.acme_use_staging.desc",
    scope=ConfigScope.PLATFORM,
    value_type=ConfigValueType.BOOLEAN,
    default_value=True,
    sort_order=20,
)

# ACME 生产环境目录 URL
ACME_DIRECTORY_URL = ConfigMeta(
    key="acme_directory_url",
    name_key="config.platform.ssl.acme_directory_url.name",
    description_key="config.platform.ssl.acme_directory_url.desc",
    scope=ConfigScope.PLATFORM,
    value_type=ConfigValueType.STRING,
    default_value="https://acme-v02.api.letsencrypt.org/directory",
    sort_order=30,
)

# ACME 测试环境目录 URL
ACME_STAGING_URL = ConfigMeta(
    key="acme_staging_url",
    name_key="config.platform.ssl.acme_staging_url.name",
    description_key="config.platform.ssl.acme_staging_url.desc",
    scope=ConfigScope.PLATFORM,
    value_type=ConfigValueType.STRING,
    default_value="https://acme-staging-v02.api.letsencrypt.org/directory",
    sort_order=40,
)

# ==========================================
# 证书管理策略
# ==========================================

# 私钥加密密钥（Fernet key）
SSL_PRIVATE_KEY_ENCRYPTION_KEY = ConfigMeta(
    key="ssl_private_key_encryption_key",
    name_key="config.platform.ssl.encryption_key.name",
    description_key="config.platform.ssl.encryption_key.desc",
    scope=ConfigScope.PLATFORM,
    value_type=ConfigValueType.PASSWORD,
    default_value="",
    is_required=True,
    is_encrypted=True,
    sort_order=50,
)

# 自动续期提前天数
SSL_AUTO_RENEW_DAYS = ConfigMeta(
    key="ssl_auto_renew_days",
    name_key="config.platform.ssl.auto_renew_days.name",
    description_key="config.platform.ssl.auto_renew_days.desc",
    scope=ConfigScope.PLATFORM,
    value_type=ConfigValueType.NUMBER,
    default_value=30,
    sort_order=60,
)

# 是否允许租户上传自定义证书
SSL_ALLOW_CUSTOM_CERT = ConfigMeta(
    key="ssl_allow_custom_cert",
    name_key="config.platform.ssl.allow_custom_cert.name",
    description_key="config.platform.ssl.allow_custom_cert.desc",
    scope=ConfigScope.PLATFORM,
    value_type=ConfigValueType.BOOLEAN,
    default_value=True,
    sort_order=70,
)


# ==========================================
# DNS 提供商配置（用于 ACME DNS-01 验证）
# ==========================================

# DNS 提供商类型
DNS_PROVIDER = ConfigMeta(
    key="dns_provider",
    name_key="config.platform.ssl.dns_provider.name",
    description_key="config.platform.ssl.dns_provider.desc",
    scope=ConfigScope.PLATFORM,
    value_type=ConfigValueType.STRING,
    default_value="manual",
    options=[
        ConfigOption(value="manual", label_key="config.platform.ssl.dns_provider.manual"),
        ConfigOption(value="cloudflare", label_key="config.platform.ssl.dns_provider.cloudflare"),
    ],
    sort_order=80,
)

# Cloudflare API Token
DNS_CLOUDFLARE_API_TOKEN = ConfigMeta(
    key="dns_cloudflare_api_token",
    name_key="config.platform.ssl.dns_cloudflare_api_token.name",
    description_key="config.platform.ssl.dns_cloudflare_api_token.desc",
    scope=ConfigScope.PLATFORM,
    value_type=ConfigValueType.PASSWORD,
    default_value="",
    is_encrypted=True,
    sort_order=90,
)

# Cloudflare Zone ID
DNS_CLOUDFLARE_ZONE_ID = ConfigMeta(
    key="dns_cloudflare_zone_id",
    name_key="config.platform.ssl.dns_cloudflare_zone_id.name",
    description_key="config.platform.ssl.dns_cloudflare_zone_id.desc",
    scope=ConfigScope.PLATFORM,
    value_type=ConfigValueType.STRING,
    default_value="",
    sort_order=100,
)


# ==========================================
# 注册配置项到分组
# ==========================================

PLATFORM_SSL_GROUP.configs = [
    ACME_ACCOUNT_EMAIL,
    ACME_USE_STAGING,
    ACME_DIRECTORY_URL,
    ACME_STAGING_URL,
    SSL_PRIVATE_KEY_ENCRYPTION_KEY,
    SSL_AUTO_RENEW_DAYS,
    SSL_ALLOW_CUSTOM_CERT,
    DNS_PROVIDER,
    DNS_CLOUDFLARE_API_TOKEN,
    DNS_CLOUDFLARE_ZONE_ID,
]
