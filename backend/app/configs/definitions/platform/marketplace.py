"""Marketplace config items / 市场配置项

Plugin marketplace and skill registry GitHub settings.
插件市场与技能市场的 GitHub 配置。
"""

from app.configs.definitions.groups import PLATFORM_GENERAL_GROUP
from app.configs.meta import ConfigMeta, max_value, min_value
from app.enums.config import ConfigScope, ConfigValueType

MARKETPLACE_GITHUB_URL = ConfigMeta(
    key="marketplace_github_url",
    name_key="config.platform.marketplace_github_url.name",
    description_key="config.platform.marketplace_github_url.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.STRING,
    default_value="https://raw.githubusercontent.com/novusai/plugin-marketplace/main",
    sort_order=210,
)

MARKETPLACE_CACHE_TTL = ConfigMeta(
    key="marketplace_cache_ttl",
    name_key="config.platform.marketplace_cache_ttl.name",
    description_key="config.platform.marketplace_cache_ttl.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.NUMBER,
    default_value=3600,
    validation_rules=[
        min_value(60, "validation.min_value"),
        max_value(86400, "validation.max_value"),
    ],
    sort_order=211,
)

SKILL_REGISTRY_GITHUB_URL = ConfigMeta(
    key="skill_registry_github_url",
    name_key="config.platform.skill_registry_github_url.name",
    description_key="config.platform.skill_registry_github_url.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.STRING,
    default_value="https://raw.githubusercontent.com/novusai/skill-marketplace/main",
    sort_order=214,
)

SKILL_REGISTRY_CACHE_TTL = ConfigMeta(
    key="skill_registry_cache_ttl",
    name_key="config.platform.skill_registry_cache_ttl.name",
    description_key="config.platform.skill_registry_cache_ttl.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.NUMBER,
    default_value=3600,
    validation_rules=[
        min_value(60, "validation.min_value"),
        max_value(86400, "validation.max_value"),
    ],
    sort_order=215,
)

PLATFORM_GENERAL_GROUP.configs.extend(
    [
        MARKETPLACE_GITHUB_URL,
        MARKETPLACE_CACHE_TTL,
        SKILL_REGISTRY_GITHUB_URL,
        SKILL_REGISTRY_CACHE_TTL,
    ]
)


__all__ = [
    "MARKETPLACE_GITHUB_URL",
    "MARKETPLACE_CACHE_TTL",
    "SKILL_REGISTRY_GITHUB_URL",
    "SKILL_REGISTRY_CACHE_TTL",
]
