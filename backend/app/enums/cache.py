"""
缓存管理相关枚举 / Cache Management Enums
"""

from app.enums.base import LabeledStrEnum


class CacheCategoryEnum(LabeledStrEnum):
    """Cache Category Enum / 缓存分类枚举"""

    AI_RESPONSE = ("ai_response", "enum.cache.category.ai_response")
    AI_SCHEMA = ("ai_schema", "enum.cache.category.ai_schema")
    AI_SQL_RESULT = ("ai_sql_result", "enum.cache.category.ai_sql_result")
    AI_ACTION_RATE = ("ai_action_rate", "enum.cache.category.ai_action_rate")
    AI_ACTION_CONFIRM = ("ai_action_confirm", "enum.cache.category.ai_action_confirm")
    KB_SEARCH = ("kb_search", "enum.cache.category.kb_search")
    WS_CONFIG = ("ws_config", "enum.cache.category.ws_config")
    MARKETPLACE = ("marketplace", "enum.cache.category.marketplace")
    AI_PROVIDER_HEALTH = ("ai_provider_health", "enum.cache.category.ai_provider_health")
    IMAGE_CACHE = ("image_cache", "enum.cache.category.image_cache")
    CONFIG_MEMORY = ("config_memory", "enum.cache.category.config_memory")
    AI_RATE_LIMIT = ("ai_rate_limit", "enum.cache.category.ai_rate_limit")
    CELERY_RESULTS = ("celery_results", "enum.cache.category.celery_results")
    CAPTCHA = ("captcha", "enum.cache.category.captcha")
    PLUGIN_UPDATE = ("plugin_update", "enum.cache.category.plugin_update")


__all__ = [
    "CacheCategoryEnum",
]
