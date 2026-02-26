"""
平台 SSL 证书管理配置项

包含 ACME/Let's Encrypt 连接配置、自动续期策略等
"""

from app.configs.meta import ConfigMeta, ConfigOption, DisplayRule
from app.configs.definitions.groups import PLATFORM_SSL_GROUP
from app.enums.config import ConfigScope, ConfigValueType


# ==========================================
# ACME 服务配置
# ==========================================

# ACME 账户邮箱
ACME_ACCOUNT_EMAIL = ConfigMeta(
    key="acme_account_email",
    name_key="config.platform.acme_account_email.name",
    description_key="config.platform.acme_account_email.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.STRING,
    default_value="",
    is_required=True,
    sort_order=10,
)

# ACME 环境模式
ACME_USE_STAGING = ConfigMeta(
    key="acme_use_staging",
    name_key="config.platform.acme_use_staging.name",
    description_key="config.platform.acme_use_staging.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.BOOLEAN,
    default_value=True,
    sort_order=20,
)

# ACME 生产环境目录 URL
ACME_DIRECTORY_URL = ConfigMeta(
    key="acme_directory_url",
    name_key="config.platform.acme_directory_url.name",
    description_key="config.platform.acme_directory_url.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.STRING,
    default_value="https://acme-v02.api.letsencrypt.org/directory",
    sort_order=30,
)

# ACME 测试环境目录 URL
ACME_STAGING_URL = ConfigMeta(
    key="acme_staging_url",
    name_key="config.platform.acme_staging_url.name",
    description_key="config.platform.acme_staging_url.desc",
    scope=ConfigScope.ADMIN_ONLY,
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
    name_key="config.platform.ssl_private_key_encryption_key.name",
    description_key="config.platform.ssl_private_key_encryption_key.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.PASSWORD,
    default_value="",
    is_required=True,
    is_encrypted=True,
    sort_order=50,
)

# 自动续期提前天数
SSL_AUTO_RENEW_DAYS = ConfigMeta(
    key="ssl_auto_renew_days",
    name_key="config.platform.ssl_auto_renew_days.name",
    description_key="config.platform.ssl_auto_renew_days.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.NUMBER,
    default_value=30,
    sort_order=60,
)

# 是否允许租户上传自定义证书
SSL_ALLOW_CUSTOM_CERT = ConfigMeta(
    key="ssl_allow_custom_cert",
    name_key="config.platform.ssl_allow_custom_cert.name",
    description_key="config.platform.ssl_allow_custom_cert.desc",
    scope=ConfigScope.ADMIN_ONLY,
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
    name_key="config.platform.dns_provider.name",
    description_key="config.platform.dns_provider.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.SELECT,
    default_value="manual",
    options=[
        ConfigOption(value="manual", label_key="config.platform.dns_provider.manual"),
        ConfigOption(value="cloudflare", label_key="config.platform.dns_provider.cloudflare"),
        ConfigOption(value="aliyun", label_key="config.platform.dns_provider.aliyun"),
        ConfigOption(value="dnspod", label_key="config.platform.dns_provider.dnspod"),
    ],
    sort_order=80,
)

# ---- Cloudflare ----

DNS_CLOUDFLARE_API_TOKEN = ConfigMeta(
    key="dns_cloudflare_api_token",
    name_key="config.platform.dns_cloudflare_api_token.name",
    description_key="config.platform.dns_cloudflare_api_token.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.PASSWORD,
    default_value="",
    is_encrypted=True,
    display_rules=[
        DisplayRule(field="dns_provider", operator="equals", value="cloudflare")
    ],
    sort_order=81,
)

DNS_CLOUDFLARE_ZONE_ID = ConfigMeta(
    key="dns_cloudflare_zone_id",
    name_key="config.platform.dns_cloudflare_zone_id.name",
    description_key="config.platform.dns_cloudflare_zone_id.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.STRING,
    default_value="",
    display_rules=[
        DisplayRule(field="dns_provider", operator="equals", value="cloudflare")
    ],
    sort_order=82,
)

# ---- Aliyun DNS ----

DNS_ALIYUN_ACCESS_KEY_ID = ConfigMeta(
    key="dns_aliyun_access_key_id",
    name_key="config.platform.dns_aliyun_access_key_id.name",
    description_key="config.platform.dns_aliyun_access_key_id.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.PASSWORD,
    default_value="",
    is_encrypted=True,
    display_rules=[
        DisplayRule(field="dns_provider", operator="equals", value="aliyun")
    ],
    sort_order=83,
)

DNS_ALIYUN_ACCESS_KEY_SECRET = ConfigMeta(
    key="dns_aliyun_access_key_secret",
    name_key="config.platform.dns_aliyun_access_key_secret.name",
    description_key="config.platform.dns_aliyun_access_key_secret.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.PASSWORD,
    default_value="",
    is_encrypted=True,
    display_rules=[
        DisplayRule(field="dns_provider", operator="equals", value="aliyun")
    ],
    sort_order=84,
)

# ---- DNSPod (Tencent Cloud) ----

DNS_DNSPOD_SECRET_ID = ConfigMeta(
    key="dns_dnspod_secret_id",
    name_key="config.platform.dns_dnspod_secret_id.name",
    description_key="config.platform.dns_dnspod_secret_id.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.PASSWORD,
    default_value="",
    is_encrypted=True,
    display_rules=[
        DisplayRule(field="dns_provider", operator="equals", value="dnspod")
    ],
    sort_order=85,
)

DNS_DNSPOD_SECRET_KEY = ConfigMeta(
    key="dns_dnspod_secret_key",
    name_key="config.platform.dns_dnspod_secret_key.name",
    description_key="config.platform.dns_dnspod_secret_key.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.PASSWORD,
    default_value="",
    is_encrypted=True,
    display_rules=[
        DisplayRule(field="dns_provider", operator="equals", value="dnspod")
    ],
    sort_order=86,
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
    DNS_ALIYUN_ACCESS_KEY_ID,
    DNS_ALIYUN_ACCESS_KEY_SECRET,
    DNS_DNSPOD_SECRET_ID,
    DNS_DNSPOD_SECRET_KEY,
]
