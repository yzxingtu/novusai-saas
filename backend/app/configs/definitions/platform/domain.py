"""Platform domain settings config items / 平台域名设置配置项

Includes tenant subdomain suffix and domain verification settings.
包含企业子域名后缀与域名验证配置
"""

from app.configs.definitions.groups import PLATFORM_DOMAIN_GROUP
from app.configs.meta import ConfigMeta, max_length, min_length
from app.enums.config import ConfigScope, ConfigValueType

# Tenant default domain suffix / 企业默认域名后缀
TENANT_DOMAIN_SUFFIX = ConfigMeta(
    key="tenant_domain_suffix",
    name_key="config.platform.tenant_domain_suffix.name",
    description_key="config.platform.tenant_domain_suffix.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.STRING,
    default_value=".app.novusai.com",
    is_required=True,
    validation_rules=[
        min_length(3, "validation.min_length"),
        max_length(100, "validation.max_length"),
    ],
    sort_order=10,
)

# Domain verification DNS prefix / 域名验证 DNS 前缀
DOMAIN_VERIFICATION_PREFIX = ConfigMeta(
    key="domain_verification_prefix",
    name_key="config.platform.domain_verification_prefix.name",
    description_key="config.platform.domain_verification_prefix.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.STRING,
    default_value="_novusai-verification",
    validation_rules=[
        min_length(1, "validation.min_length"),
        max_length(50, "validation.max_length"),
    ],
    sort_order=20,
)

PLATFORM_DOMAIN_GROUP.configs = [
    TENANT_DOMAIN_SUFFIX,
    DOMAIN_VERIFICATION_PREFIX,
]

__all__ = [
    "TENANT_DOMAIN_SUFFIX",
    "DOMAIN_VERIFICATION_PREFIX",
]
