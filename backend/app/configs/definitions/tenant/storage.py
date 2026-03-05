from app.configs.definitions.groups import TENANT_STORAGE_GROUP
from app.configs.meta import ConfigMeta, ConfigOption, DisplayRule
from app.enums.config import ConfigScope, ConfigValueType

TENANT_STORAGE_MODE = ConfigMeta(
    key="tenant_storage_mode",
    name_key="config.tenant.storage_mode.name",
    description_key="config.tenant.storage_mode.desc",
    scope=ConfigScope.ALL_TENANTS,
    value_type=ConfigValueType.SELECT,
    default_value="platform",
    options=[
        ConfigOption("platform", "config.storage.mode.platform"),
        ConfigOption("admin_override", "config.storage.mode.admin_override"),
        ConfigOption("custom", "config.storage.mode.custom"),
    ],
    sort_order=10,
)

TENANT_STORAGE_SELF_CONFIG_ENABLED = ConfigMeta(
    key="tenant_storage_self_config_enabled",
    name_key="config.tenant.storage_self_config_enabled.name",
    description_key="config.tenant.storage_self_config_enabled.desc",
    scope=ConfigScope.ALL_TENANTS,
    value_type=ConfigValueType.BOOLEAN,
    default_value=False,
    sort_order=15,
)

TENANT_STORAGE_DRIVER = ConfigMeta(
    key="tenant_storage_driver",
    name_key="config.tenant.storage_driver.name",
    description_key="config.tenant.storage_driver.desc",
    scope=ConfigScope.ALL_TENANTS,
    value_type=ConfigValueType.SELECT,
    default_value="s3",
    options=[
        ConfigOption("s3", "config.storage.driver.s3"),
        ConfigOption("aliyun-oss", "config.storage.driver.aliyun_oss"),
        ConfigOption("qiniu-kodo", "config.storage.driver.qiniu_kodo"),
        ConfigOption("tencent-cos", "config.storage.driver.tencent_cos"),
    ],
    display_rules=[
        DisplayRule(
            field="tenant_storage_mode",
            operator="in",
            value=["custom", "admin_override"],
        )
    ],
    sort_order=20,
)

TENANT_STORAGE_ROOT_PATH = ConfigMeta(
    key="tenant_storage_root_path",
    name_key="config.tenant.storage_root_path.name",
    description_key="config.tenant.storage_root_path.desc",
    scope=ConfigScope.ALL_TENANTS,
    value_type=ConfigValueType.STRING,
    default_value="",
    display_rules=[
        DisplayRule(
            field="tenant_storage_mode",
            operator="in",
            value=["custom", "admin_override"],
        )
    ],
    sort_order=30,
)

TENANT_STORAGE_BASE_URL = ConfigMeta(
    key="tenant_storage_base_url",
    name_key="config.tenant.storage_base_url.name",
    description_key="config.tenant.storage_base_url.desc",
    scope=ConfigScope.ALL_TENANTS,
    value_type=ConfigValueType.STRING,
    default_value="",
    display_rules=[
        DisplayRule(
            field="tenant_storage_mode",
            operator="in",
            value=["custom", "admin_override"],
        )
    ],
    sort_order=40,
)

TENANT_STORAGE_OPTIONS = ConfigMeta(
    key="tenant_storage_options",
    name_key="config.tenant.storage_options.name",
    description_key="config.tenant.storage_options.desc",
    scope=ConfigScope.ALL_TENANTS,
    value_type=ConfigValueType.JSON,
    default_value={},
    display_rules=[
        DisplayRule(
            field="tenant_storage_mode",
            operator="in",
            value=["custom", "admin_override"],
        )
    ],
    children=[
        ConfigMeta(
            key="storage_options.access_key_id",
            name_key="config.storage.option.access_key_id.name",
            description_key="config.storage.option.access_key_id.desc",
            scope=ConfigScope.ALL_TENANTS,
            value_type=ConfigValueType.STRING,
            value_path="access_key_id",
            display_rules=[
                DisplayRule(
                    field="tenant_storage_driver",
                    operator="in",
                    value=["s3", "aliyun-oss", "qiniu-kodo"],
                ),
                DisplayRule(
                    field="tenant_storage_mode",
                    operator="in",
                    value=["custom", "admin_override"],
                )
            ],
            sort_order=10,
        ),
        ConfigMeta(
            key="storage_options.secret_access_key",
            name_key="config.storage.option.secret_access_key.name",
            description_key="config.storage.option.secret_access_key.desc",
            scope=ConfigScope.ALL_TENANTS,
            value_type=ConfigValueType.PASSWORD,
            value_path="secret_access_key",
            display_rules=[
                DisplayRule(
                    field="tenant_storage_driver",
                    operator="equals",
                    value="s3",
                ),
                DisplayRule(
                    field="tenant_storage_mode",
                    operator="in",
                    value=["custom", "admin_override"],
                )
            ],
            sort_order=20,
        ),
        ConfigMeta(
            key="storage_options.access_key_secret",
            name_key="config.storage.option.access_key_secret.name",
            description_key="config.storage.option.access_key_secret.desc",
            scope=ConfigScope.ALL_TENANTS,
            value_type=ConfigValueType.PASSWORD,
            value_path="access_key_secret",
            display_rules=[
                DisplayRule(
                    field="tenant_storage_driver",
                    operator="equals",
                    value="aliyun-oss",
                ),
                DisplayRule(
                    field="tenant_storage_mode",
                    operator="in",
                    value=["custom", "admin_override"],
                )
            ],
            sort_order=30,
        ),
        ConfigMeta(
            key="storage_options.region",
            name_key="config.storage.option.region.name",
            description_key="config.storage.option.region.desc",
            scope=ConfigScope.ALL_TENANTS,
            value_type=ConfigValueType.STRING,
            value_path="region",
            display_rules=[
                DisplayRule(
                    field="tenant_storage_driver",
                    operator="equals",
                    value="s3",
                ),
                DisplayRule(
                    field="tenant_storage_mode",
                    operator="in",
                    value=["custom", "admin_override"],
                )
            ],
            sort_order=40,
        ),
        ConfigMeta(
            key="storage_options.endpoint_url",
            name_key="config.storage.option.endpoint_url.name",
            description_key="config.storage.option.endpoint_url.desc",
            scope=ConfigScope.ALL_TENANTS,
            value_type=ConfigValueType.STRING,
            value_path="endpoint_url",
            display_rules=[
                DisplayRule(
                    field="tenant_storage_driver",
                    operator="equals",
                    value="s3",
                ),
                DisplayRule(
                    field="tenant_storage_mode",
                    operator="in",
                    value=["custom", "admin_override"],
                )
            ],
            sort_order=50,
        ),
        ConfigMeta(
            key="storage_options.endpoint",
            name_key="config.storage.option.endpoint.name",
            description_key="config.storage.option.endpoint.desc",
            scope=ConfigScope.ALL_TENANTS,
            value_type=ConfigValueType.STRING,
            value_path="endpoint",
            display_rules=[
                DisplayRule(
                    field="tenant_storage_driver",
                    operator="equals",
                    value="aliyun-oss",
                ),
                DisplayRule(
                    field="tenant_storage_mode",
                    operator="in",
                    value=["custom", "admin_override"],
                )
            ],
            sort_order=60,
        ),
        ConfigMeta(
            key="storage_options.prefix",
            name_key="config.storage.option.prefix.name",
            description_key="config.storage.option.prefix.desc",
            scope=ConfigScope.ALL_TENANTS,
            value_type=ConfigValueType.STRING,
            value_path="prefix",
            display_rules=[
                DisplayRule(
                    field="tenant_storage_driver",
                    operator="in",
                    value=["s3", "aliyun-oss", "qiniu-kodo", "tencent-cos"],
                ),
                DisplayRule(
                    field="tenant_storage_mode",
                    operator="in",
                    value=["custom", "admin_override"],
                )
            ],
            sort_order=70,
        ),
        ConfigMeta(
            key="storage_options.secret_id",
            name_key="config.storage.option.secret_id.name",
            description_key="config.storage.option.secret_id.desc",
            scope=ConfigScope.ALL_TENANTS,
            value_type=ConfigValueType.STRING,
            value_path="secret_id",
            display_rules=[
                DisplayRule(
                    field="tenant_storage_driver",
                    operator="equals",
                    value="tencent-cos",
                ),
                DisplayRule(
                    field="tenant_storage_mode",
                    operator="in",
                    value=["custom", "admin_override"],
                )
            ],
            sort_order=80,
        ),
        ConfigMeta(
            key="storage_options.cos_secret_key",
            name_key="config.storage.option.cos_secret_key.name",
            description_key="config.storage.option.cos_secret_key.desc",
            scope=ConfigScope.ALL_TENANTS,
            value_type=ConfigValueType.PASSWORD,
            value_path="secret_key",
            display_rules=[
                DisplayRule(
                    field="tenant_storage_driver",
                    operator="equals",
                    value="tencent-cos",
                ),
                DisplayRule(
                    field="tenant_storage_mode",
                    operator="in",
                    value=["custom", "admin_override"],
                )
            ],
            sort_order=90,
        ),
        ConfigMeta(
            key="storage_options.kodo_secret_key",
            name_key="config.storage.option.kodo_secret_key.name",
            description_key="config.storage.option.kodo_secret_key.desc",
            scope=ConfigScope.ALL_TENANTS,
            value_type=ConfigValueType.PASSWORD,
            value_path="secret_key",
            display_rules=[
                DisplayRule(
                    field="tenant_storage_driver",
                    operator="equals",
                    value="qiniu-kodo",
                ),
                DisplayRule(
                    field="tenant_storage_mode",
                    operator="in",
                    value=["custom", "admin_override"],
                )
            ],
            sort_order=100,
        ),
        ConfigMeta(
            key="storage_options.cos_region",
            name_key="config.storage.option.cos_region.name",
            description_key="config.storage.option.cos_region.desc",
            scope=ConfigScope.ALL_TENANTS,
            value_type=ConfigValueType.STRING,
            value_path="region",
            display_rules=[
                DisplayRule(
                    field="tenant_storage_driver",
                    operator="equals",
                    value="tencent-cos",
                ),
                DisplayRule(
                    field="tenant_storage_mode",
                    operator="in",
                    value=["custom", "admin_override"],
                )
            ],
            sort_order=110,
        ),
        ConfigMeta(
            key="storage_options.domain",
            name_key="config.storage.option.domain.name",
            description_key="config.storage.option.domain.desc",
            scope=ConfigScope.ALL_TENANTS,
            value_type=ConfigValueType.STRING,
            value_path="domain",
            display_rules=[
                DisplayRule(
                    field="tenant_storage_driver",
                    operator="equals",
                    value="qiniu-kodo",
                ),
                DisplayRule(
                    field="tenant_storage_mode",
                    operator="in",
                    value=["custom", "admin_override"],
                )
            ],
            sort_order=120,
        ),
    ],
    sort_order=50,
)

TENANT_STORAGE_DEFAULT_VISIBILITY = ConfigMeta(
    key="tenant_storage_default_visibility",
    name_key="config.tenant.storage_default_visibility.name",
    description_key="config.tenant.storage_default_visibility.desc",
    scope=ConfigScope.ALL_TENANTS,
    value_type=ConfigValueType.SELECT,
    default_value="private",
    options=[
        ConfigOption("private", "config.storage.visibility.private"),
        ConfigOption("public", "config.storage.visibility.public"),
    ],
    display_rules=[
        DisplayRule(
            field="tenant_storage_mode",
            operator="in",
            value=["custom", "admin_override"],
        )
    ],
    sort_order=60,
)

TENANT_STORAGE_ALLOWED_EXTENSIONS = ConfigMeta(
    key="tenant_storage_allowed_extensions",
    name_key="config.tenant.storage_allowed_extensions.name",
    description_key="config.tenant.storage_allowed_extensions.desc",
    scope=ConfigScope.ALL_TENANTS,
    value_type=ConfigValueType.TAG,
    default_value="",
    tag_separator=",",
    sort_order=70,
)

TENANT_STORAGE_DENIED_EXTENSIONS = ConfigMeta(
    key="tenant_storage_denied_extensions",
    name_key="config.tenant.storage_denied_extensions.name",
    description_key="config.tenant.storage_denied_extensions.desc",
    scope=ConfigScope.ALL_TENANTS,
    value_type=ConfigValueType.TAG,
    default_value="",
    tag_separator=",",
    sort_order=80,
)

TENANT_STORAGE_GROUP.configs = [
    TENANT_STORAGE_MODE,
    TENANT_STORAGE_SELF_CONFIG_ENABLED,
    TENANT_STORAGE_DRIVER,
    TENANT_STORAGE_ROOT_PATH,
    TENANT_STORAGE_BASE_URL,
    TENANT_STORAGE_OPTIONS,
    TENANT_STORAGE_DEFAULT_VISIBILITY,
    TENANT_STORAGE_ALLOWED_EXTENSIONS,
    TENANT_STORAGE_DENIED_EXTENSIONS,
]


__all__ = [
    "TENANT_STORAGE_MODE",
    "TENANT_STORAGE_SELF_CONFIG_ENABLED",
    "TENANT_STORAGE_DRIVER",
    "TENANT_STORAGE_ROOT_PATH",
    "TENANT_STORAGE_BASE_URL",
    "TENANT_STORAGE_OPTIONS",
    "TENANT_STORAGE_DEFAULT_VISIBILITY",
    "TENANT_STORAGE_ALLOWED_EXTENSIONS",
    "TENANT_STORAGE_DENIED_EXTENSIONS",
]
