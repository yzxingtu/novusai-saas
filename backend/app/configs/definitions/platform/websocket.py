"""WebSocket & notification settings config items / WebSocket & 通知设置配置项

Includes Socket.IO connection params and notification system config.
包含 Socket.IO 连接参数和通知系统配置
"""

from app.configs.definitions.groups import PLATFORM_WEBSOCKET_GROUP
from app.configs.meta import ConfigMeta, DisplayRule, max_length
from app.enums.config import ConfigScope, ConfigValueType

# ==========================================
# Socket.IO connection config / Socket.IO 连接配置
# ==========================================

# Socket.IO master toggle / Socket.IO 总开关
WS_ENABLED = ConfigMeta(
    key="ws_enabled",
    name_key="config.platform.ws_enabled.name",
    description_key="config.platform.ws_enabled.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.BOOLEAN,
    default_value=True,
    sort_order=10,
)

# Ping interval (seconds) / ping 间隔（秒）
WS_PING_INTERVAL = ConfigMeta(
    key="ws_ping_interval",
    name_key="config.platform.ws_ping_interval.name",
    description_key="config.platform.ws_ping_interval.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.NUMBER,
    default_value=25,
    sort_order=20,
    display_rules=[
        DisplayRule(field="ws_enabled", operator="equals", value=True, action="show"),
    ],
)

# Ping timeout (seconds) / ping 超时（秒）
WS_PING_TIMEOUT = ConfigMeta(
    key="ws_ping_timeout",
    name_key="config.platform.ws_ping_timeout.name",
    description_key="config.platform.ws_ping_timeout.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.NUMBER,
    default_value=20,
    sort_order=30,
    display_rules=[
        DisplayRule(field="ws_enabled", operator="equals", value=True, action="show"),
    ],
)

# Max connections per user / 单用户最大连接数
WS_MAX_CONNECTIONS_PER_USER = ConfigMeta(
    key="ws_max_connections_per_user",
    name_key="config.platform.ws_max_connections_per_user.name",
    description_key="config.platform.ws_max_connections_per_user.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.NUMBER,
    default_value=5,
    sort_order=40,
    display_rules=[
        DisplayRule(field="ws_enabled", operator="equals", value=True, action="show"),
    ],
)


# ==========================================
# Notification system config / 通知系统配置
# ==========================================

# Notification system toggle / 通知系统总开关
NOTIFICATION_ENABLED = ConfigMeta(
    key="notification_enabled",
    name_key="config.platform.notification_enabled.name",
    description_key="config.platform.notification_enabled.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.BOOLEAN,
    default_value=True,
    sort_order=100,
)

# Notification retention days / 通知保留天数
NOTIFICATION_RETENTION_DAYS = ConfigMeta(
    key="notification_retention_days",
    name_key="config.platform.notification_retention_days.name",
    description_key="config.platform.notification_retention_days.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.NUMBER,
    default_value=90,
    sort_order=110,
    display_rules=[
        DisplayRule(
            field="notification_enabled", operator="equals", value=True, action="show"
        ),
    ],
)

# Max notifications stored per user / 每用户最大通知存储条数
NOTIFICATION_MAX_PER_USER = ConfigMeta(
    key="notification_max_per_user",
    name_key="config.platform.notification_max_per_user.name",
    description_key="config.platform.notification_max_per_user.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.NUMBER,
    default_value=500,
    sort_order=120,
    display_rules=[
        DisplayRule(
            field="notification_enabled", operator="equals", value=True, action="show"
        ),
    ],
)

# Webhook notification toggle / Webhook 通知开关
WEBHOOK_ENABLED = ConfigMeta(
    key="webhook_enabled",
    name_key="config.platform.webhook_enabled.name",
    description_key="config.platform.webhook_enabled.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.BOOLEAN,
    default_value=False,
    sort_order=130,
)

# Webhook URL / Webhook 地址
WEBHOOK_URL = ConfigMeta(
    key="webhook_url",
    name_key="config.platform.webhook_url.name",
    description_key="config.platform.webhook_url.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.STRING,
    default_value="",
    validation_rules=[max_length(500, "validation.max_length")],
    sort_order=140,
    display_rules=[
        DisplayRule(
            field="webhook_enabled", operator="equals", value=True, action="show"
        ),
    ],
)


# ==========================================
# Register configs to group / 注册配置到分组
# ==========================================

PLATFORM_WEBSOCKET_GROUP.configs = [
    WS_ENABLED,
    WS_PING_INTERVAL,
    WS_PING_TIMEOUT,
    WS_MAX_CONNECTIONS_PER_USER,
    NOTIFICATION_ENABLED,
    NOTIFICATION_RETENTION_DAYS,
    NOTIFICATION_MAX_PER_USER,
    WEBHOOK_ENABLED,
    WEBHOOK_URL,
]


__all__ = [
    "WS_ENABLED",
    "WS_PING_INTERVAL",
    "WS_PING_TIMEOUT",
    "WS_MAX_CONNECTIONS_PER_USER",
    "NOTIFICATION_ENABLED",
    "NOTIFICATION_RETENTION_DAYS",
    "NOTIFICATION_MAX_PER_USER",
    "WEBHOOK_ENABLED",
    "WEBHOOK_URL",
]
