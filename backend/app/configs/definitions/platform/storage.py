from app.configs.meta import ConfigMeta, ConfigOption
from app.configs.definitions.groups import PLATFORM_STORAGE_GROUP
from app.enums.config import ConfigScope, ConfigValueType


PLATFORM_STORAGE_DRIVER = ConfigMeta(
    key="platform_storage_driver",
    name_key="config.platform.storage_driver.name",
    description_key="config.platform.storage_driver.desc",
    scope=ConfigScope.PLATFORM,
    value_type=ConfigValueType.SELECT,
    default_value="local",
    options=[
        ConfigOption("local", "config.storage.driver.local"),
        ConfigOption("s3", "config.storage.driver.s3"),
        ConfigOption("aliyun-oss", "config.storage.driver.aliyun_oss"),
    ],
    sort_order=10,
)

PLATFORM_STORAGE_ROOT_PATH = ConfigMeta(
    key="platform_storage_root_path",
    name_key="config.platform.storage_root_path.name",
    description_key="config.platform.storage_root_path.desc",
    scope=ConfigScope.PLATFORM,
    value_type=ConfigValueType.STRING,
    default_value="/data/uploads",
    sort_order=20,
)

PLATFORM_STORAGE_BASE_URL = ConfigMeta(
    key="platform_storage_base_url",
    name_key="config.platform.storage_base_url.name",
    description_key="config.platform.storage_base_url.desc",
    scope=ConfigScope.PLATFORM,
    value_type=ConfigValueType.STRING,
    default_value="",
    sort_order=30,
)

PLATFORM_STORAGE_OPTIONS = ConfigMeta(
    key="platform_storage_options",
    name_key="config.platform.storage_options.name",
    description_key="config.platform.storage_options.desc",
    scope=ConfigScope.PLATFORM,
    value_type=ConfigValueType.JSON,
    default_value={},
    sort_order=40,
)

PLATFORM_STORAGE_DEFAULT_VISIBILITY = ConfigMeta(
    key="platform_storage_default_visibility",
    name_key="config.platform.storage_default_visibility.name",
    description_key="config.platform.storage_default_visibility.desc",
    scope=ConfigScope.PLATFORM,
    value_type=ConfigValueType.SELECT,
    default_value="private",
    options=[
        ConfigOption("private", "config.storage.visibility.private"),
        ConfigOption("public", "config.storage.visibility.public"),
    ],
    sort_order=50,
)

PLATFORM_STORAGE_CHUNK_SIZE_MB = ConfigMeta(
    key="platform_storage_chunk_size_mb",
    name_key="config.platform.storage_chunk_size_mb.name",
    description_key="config.platform.storage_chunk_size_mb.desc",
    scope=ConfigScope.PLATFORM,
    value_type=ConfigValueType.NUMBER,
    default_value=5,
    sort_order=60,
)

PLATFORM_STORAGE_GROUP.configs = [
    PLATFORM_STORAGE_DRIVER,
    PLATFORM_STORAGE_ROOT_PATH,
    PLATFORM_STORAGE_BASE_URL,
    PLATFORM_STORAGE_OPTIONS,
    PLATFORM_STORAGE_DEFAULT_VISIBILITY,
    PLATFORM_STORAGE_CHUNK_SIZE_MB,
]


__all__ = [
    "PLATFORM_STORAGE_DRIVER",
    "PLATFORM_STORAGE_ROOT_PATH",
    "PLATFORM_STORAGE_BASE_URL",
    "PLATFORM_STORAGE_OPTIONS",
    "PLATFORM_STORAGE_DEFAULT_VISIBILITY",
    "PLATFORM_STORAGE_CHUNK_SIZE_MB",
]
