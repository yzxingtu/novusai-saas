"""Platform AI memory config items / 平台 AI 记忆配置项

Controls platform-level conversation memory default toggle.
控制平台层面的会话记忆默认开关。
"""

from app.configs.definitions.groups import PLATFORM_AI_MEMORY_GROUP
from app.configs.meta import ConfigMeta
from app.enums.config import ConfigScope, ConfigValueType

PLATFORM_DEFAULT_MEMORY_ENABLED = ConfigMeta(
    key="platform_default_memory_enabled",
    name_key="config.platform.platform_default_memory_enabled.name",
    description_key="config.platform.platform_default_memory_enabled.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.BOOLEAN,
    default_value=True,
    sort_order=10,
)

MEMORY_EXTRACTION_PROVIDER = ConfigMeta(
    key="memory_extraction_provider",
    name_key="config.platform.memory_extraction_provider.name",
    description_key="config.platform.memory_extraction_provider.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.STRING,
    default_value="",
    sort_order=20,
)

MEMORY_EXTRACTION_MODEL = ConfigMeta(
    key="memory_extraction_model",
    name_key="config.platform.memory_extraction_model.name",
    description_key="config.platform.memory_extraction_model.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.STRING,
    default_value="",
    sort_order=30,
)


PLATFORM_AI_MEMORY_GROUP.configs = [
    PLATFORM_DEFAULT_MEMORY_ENABLED,
    MEMORY_EXTRACTION_PROVIDER,
    MEMORY_EXTRACTION_MODEL,
]


__all__ = [
    "PLATFORM_DEFAULT_MEMORY_ENABLED",
    "MEMORY_EXTRACTION_PROVIDER",
    "MEMORY_EXTRACTION_MODEL",
]
