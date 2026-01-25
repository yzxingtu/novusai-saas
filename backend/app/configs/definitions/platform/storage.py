from app.configs.meta import ConfigMeta, ConfigOption, DisplayRule
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
    default_value="",
    display_rules=[
        DisplayRule(
            field="platform_storage_driver",
            operator="in",
            value=["s3", "aliyun-oss"],
        )
    ],
    sort_order=20,
)

PLATFORM_STORAGE_BASE_URL = ConfigMeta(
    key="platform_storage_base_url",
    name_key="config.platform.storage_base_url.name",
    description_key="config.platform.storage_base_url.desc",
    scope=ConfigScope.PLATFORM,
    value_type=ConfigValueType.STRING,
    default_value="",
    # 所有驱动都需要设置访问域名，本地存储用于构建文件 URL
    sort_order=30,
)

PLATFORM_STORAGE_OPTIONS = ConfigMeta(
    key="platform_storage_options",
    name_key="config.platform.storage_options.name",
    description_key="config.platform.storage_options.desc",
    scope=ConfigScope.PLATFORM,
    value_type=ConfigValueType.JSON,
    default_value={},
    display_rules=[
        DisplayRule(
            field="platform_storage_driver",
            operator="in",
            value=["s3", "aliyun-oss"],
        )
    ],
    children=[
        ConfigMeta(
            key="storage_options.access_key_id",
            name_key="config.storage.option.access_key_id.name",
            description_key="config.storage.option.access_key_id.desc",
            scope=ConfigScope.PLATFORM,
            value_type=ConfigValueType.STRING,
            value_path="access_key_id",
            display_rules=[
                DisplayRule(
                    field="platform_storage_driver",
                    operator="in",
                    value=["s3", "aliyun-oss"],
                )
            ],
            sort_order=10,
        ),
        ConfigMeta(
            key="storage_options.secret_access_key",
            name_key="config.storage.option.secret_access_key.name",
            description_key="config.storage.option.secret_access_key.desc",
            scope=ConfigScope.PLATFORM,
            value_type=ConfigValueType.PASSWORD,
            value_path="secret_access_key",
            display_rules=[
                DisplayRule(
                    field="platform_storage_driver",
                    operator="equals",
                    value="s3",
                )
            ],
            sort_order=20,
        ),
        ConfigMeta(
            key="storage_options.access_key_secret",
            name_key="config.storage.option.access_key_secret.name",
            description_key="config.storage.option.access_key_secret.desc",
            scope=ConfigScope.PLATFORM,
            value_type=ConfigValueType.PASSWORD,
            value_path="access_key_secret",
            display_rules=[
                DisplayRule(
                    field="platform_storage_driver",
                    operator="equals",
                    value="aliyun-oss",
                )
            ],
            sort_order=30,
        ),
        ConfigMeta(
            key="storage_options.region",
            name_key="config.storage.option.region.name",
            description_key="config.storage.option.region.desc",
            scope=ConfigScope.PLATFORM,
            value_type=ConfigValueType.STRING,
            value_path="region",
            display_rules=[
                DisplayRule(
                    field="platform_storage_driver",
                    operator="equals",
                    value="s3",
                )
            ],
            sort_order=40,
        ),
        ConfigMeta(
            key="storage_options.endpoint_url",
            name_key="config.storage.option.endpoint_url.name",
            description_key="config.storage.option.endpoint_url.desc",
            scope=ConfigScope.PLATFORM,
            value_type=ConfigValueType.STRING,
            value_path="endpoint_url",
            display_rules=[
                DisplayRule(
                    field="platform_storage_driver",
                    operator="equals",
                    value="s3",
                )
            ],
            sort_order=50,
        ),
        ConfigMeta(
            key="storage_options.endpoint",
            name_key="config.storage.option.endpoint.name",
            description_key="config.storage.option.endpoint.desc",
            scope=ConfigScope.PLATFORM,
            value_type=ConfigValueType.STRING,
            value_path="endpoint",
            display_rules=[
                DisplayRule(
                    field="platform_storage_driver",
                    operator="equals",
                    value="aliyun-oss",
                )
            ],
            sort_order=60,
        ),
        ConfigMeta(
            key="storage_options.prefix",
            name_key="config.storage.option.prefix.name",
            description_key="config.storage.option.prefix.desc",
            scope=ConfigScope.PLATFORM,
            value_type=ConfigValueType.STRING,
            value_path="prefix",
            display_rules=[
                DisplayRule(
                    field="platform_storage_driver",
                    operator="in",
                    value=["s3", "aliyun-oss"],
                )
            ],
            sort_order=70,
        ),
    ],
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

PLATFORM_STORAGE_MAX_FILE_SIZE_MB = ConfigMeta(
    key="platform_storage_max_file_size_mb",
    name_key="config.platform.storage_max_file_size_mb.name",
    description_key="config.platform.storage_max_file_size_mb.desc",
    scope=ConfigScope.PLATFORM,
    value_type=ConfigValueType.NUMBER,
    default_value=100,
    sort_order=70,
)

PLATFORM_STORAGE_ALLOWED_EXTENSIONS = ConfigMeta(
    key="platform_storage_allowed_extensions",
    name_key="config.platform.storage_allowed_extensions.name",
    description_key="config.platform.storage_allowed_extensions.desc",
    scope=ConfigScope.PLATFORM,
    value_type=ConfigValueType.TAG,
    default_value="jpg,jpeg,png,gif,webp,svg,ico,bmp,pdf,doc,docx,xls,xlsx,ppt,pptx,txt,csv,json,xml,zip,rar,7z,mp3,mp4,avi,mov,webm",
    tag_separator=",",
    sort_order=80,
)

PLATFORM_STORAGE_DENIED_EXTENSIONS = ConfigMeta(
    key="platform_storage_denied_extensions",
    name_key="config.platform.storage_denied_extensions.name",
    description_key="config.platform.storage_denied_extensions.desc",
    scope=ConfigScope.PLATFORM,
    value_type=ConfigValueType.TAG,
    default_value="exe,bat,cmd,sh,php,asp,aspx,jsp,py,rb,pl,cgi,htaccess,dll,so",
    tag_separator=",",
    sort_order=90,
)

# ==========================================
# 图片处理配置
# ==========================================

PLATFORM_IMAGE_PROCESS_ENABLED = ConfigMeta(
    key="platform_image_process_enabled",
    name_key="config.platform.image_process_enabled.name",
    description_key="config.platform.image_process_enabled.desc",
    scope=ConfigScope.PLATFORM,
    value_type=ConfigValueType.BOOLEAN,
    default_value=True,
    sort_order=100,
)

PLATFORM_IMAGE_CACHE_DRIVER = ConfigMeta(
    key="platform_image_cache_driver",
    name_key="config.platform.image_cache_driver.name",
    description_key="config.platform.image_cache_driver.desc",
    scope=ConfigScope.PLATFORM,
    value_type=ConfigValueType.SELECT,
    default_value="filesystem",
    options=[
        ConfigOption("filesystem", "config.platform.image_cache_driver.filesystem"),
        ConfigOption("redis", "config.platform.image_cache_driver.redis"),
    ],
    display_rules=[
        DisplayRule(
            field="platform_image_process_enabled",
            operator="equals",
            value=True,
        )
    ],
    sort_order=110,
)

# 图片缓存路径已硬编码，不再作为配置项

PLATFORM_IMAGE_CACHE_TTL_DAYS = ConfigMeta(
    key="platform_image_cache_ttl_days",
    name_key="config.platform.image_cache_ttl_days.name",
    description_key="config.platform.image_cache_ttl_days.desc",
    scope=ConfigScope.PLATFORM,
    value_type=ConfigValueType.NUMBER,
    default_value=7,
    display_rules=[
        DisplayRule(
            field="platform_image_process_enabled",
            operator="equals",
            value=True,
        )
    ],
    sort_order=130,
)

PLATFORM_IMAGE_MAX_WIDTH = ConfigMeta(
    key="platform_image_max_width",
    name_key="config.platform.image_max_width.name",
    description_key="config.platform.image_max_width.desc",
    scope=ConfigScope.PLATFORM,
    value_type=ConfigValueType.NUMBER,
    default_value=4096,
    display_rules=[
        DisplayRule(
            field="platform_image_process_enabled",
            operator="equals",
            value=True,
        )
    ],
    sort_order=140,
)

PLATFORM_IMAGE_MAX_HEIGHT = ConfigMeta(
    key="platform_image_max_height",
    name_key="config.platform.image_max_height.name",
    description_key="config.platform.image_max_height.desc",
    scope=ConfigScope.PLATFORM,
    value_type=ConfigValueType.NUMBER,
    default_value=4096,
    display_rules=[
        DisplayRule(
            field="platform_image_process_enabled",
            operator="equals",
            value=True,
        )
    ],
    sort_order=150,
)

PLATFORM_IMAGE_DEFAULT_QUALITY = ConfigMeta(
    key="platform_image_default_quality",
    name_key="config.platform.image_default_quality.name",
    description_key="config.platform.image_default_quality.desc",
    scope=ConfigScope.PLATFORM,
    value_type=ConfigValueType.NUMBER,
    default_value=85,
    display_rules=[
        DisplayRule(
            field="platform_image_process_enabled",
            operator="equals",
            value=True,
        )
    ],
    sort_order=160,
)

PLATFORM_STORAGE_GROUP.configs = [
    PLATFORM_STORAGE_DRIVER,
    PLATFORM_STORAGE_ROOT_PATH,
    PLATFORM_STORAGE_BASE_URL,
    PLATFORM_STORAGE_OPTIONS,
    PLATFORM_STORAGE_DEFAULT_VISIBILITY,
    PLATFORM_STORAGE_CHUNK_SIZE_MB,
    PLATFORM_STORAGE_MAX_FILE_SIZE_MB,
    PLATFORM_STORAGE_ALLOWED_EXTENSIONS,
    PLATFORM_STORAGE_DENIED_EXTENSIONS,
    # 图片处理配置
    PLATFORM_IMAGE_PROCESS_ENABLED,
    PLATFORM_IMAGE_CACHE_DRIVER,
    PLATFORM_IMAGE_CACHE_TTL_DAYS,
    PLATFORM_IMAGE_MAX_WIDTH,
    PLATFORM_IMAGE_MAX_HEIGHT,
    PLATFORM_IMAGE_DEFAULT_QUALITY,
]


__all__ = [
    "PLATFORM_STORAGE_DRIVER",
    "PLATFORM_STORAGE_ROOT_PATH",
    "PLATFORM_STORAGE_BASE_URL",
    "PLATFORM_STORAGE_OPTIONS",
    "PLATFORM_STORAGE_DEFAULT_VISIBILITY",
    "PLATFORM_STORAGE_CHUNK_SIZE_MB",
    "PLATFORM_STORAGE_MAX_FILE_SIZE_MB",
    "PLATFORM_STORAGE_ALLOWED_EXTENSIONS",
    "PLATFORM_STORAGE_DENIED_EXTENSIONS",
    # 图片处理配置
    "PLATFORM_IMAGE_PROCESS_ENABLED",
    "PLATFORM_IMAGE_CACHE_DRIVER",
    "PLATFORM_IMAGE_CACHE_TTL_DAYS",
    "PLATFORM_IMAGE_MAX_WIDTH",
    "PLATFORM_IMAGE_MAX_HEIGHT",
    "PLATFORM_IMAGE_DEFAULT_QUALITY",
]
