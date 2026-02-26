"""
WebSocket & 通知设置配置项

包含 Socket.IO 连接参数和通知系统配置
"""

from app.configs.meta import ConfigMeta, DisplayRule
from app.configs.definitions.groups import PLATFORM_WEBSOCKET_GROUP
from app.enums.config import ConfigScope, ConfigValueType


# ==========================================
# Socket.IO 连接配置
# ==========================================

# Socket.IO 总开关
WS_ENABLED = ConfigMeta(
    key="ws_enabled",
    name_key="config.platform.ws_enabled.name",
    description_key="config.platform.ws_enabled.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.BOOLEAN,
    default_value=True,
    sort_order=10,
)

# ping 间隔（秒）
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

# ping 超时（秒）
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

# 单用户最大连接数
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
# 通知系统配置
# ==========================================

# 通知系统总开关
NOTIFICATION_ENABLED = ConfigMeta(
    key="notification_enabled",
    name_key="config.platform.notification_enabled.name",
    description_key="config.platform.notification_enabled.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.BOOLEAN,
    default_value=True,
    sort_order=100,
)

# 通知保留天数
NOTIFICATION_RETENTION_DAYS = ConfigMeta(
    key="notification_retention_days",
    name_key="config.platform.notification_retention_days.name",
    description_key="config.platform.notification_retention_days.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.NUMBER,
    default_value=90,
    sort_order=110,
    display_rules=[
        DisplayRule(field="notification_enabled", operator="equals", value=True, action="show"),
    ],
)

# 每用户最大通知存储条数
NOTIFICATION_MAX_PER_USER = ConfigMeta(
    key="notification_max_per_user",
    name_key="config.platform.notification_max_per_user.name",
    description_key="config.platform.notification_max_per_user.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.NUMBER,
    default_value=500,
    sort_order=120,
    display_rules=[
        DisplayRule(field="notification_enabled", operator="equals", value=True, action="show"),
    ],
)


# ==========================================
# 注册配置到分组
# ==========================================

PLATFORM_WEBSOCKET_GROUP.configs = [
    WS_ENABLED,
    WS_PING_INTERVAL,
    WS_PING_TIMEOUT,
    WS_MAX_CONNECTIONS_PER_USER,
    NOTIFICATION_ENABLED,
    NOTIFICATION_RETENTION_DAYS,
    NOTIFICATION_MAX_PER_USER,
]


__all__ = [
    "WS_ENABLED",
    "WS_PING_INTERVAL",
    "WS_PING_TIMEOUT",
    "WS_MAX_CONNECTIONS_PER_USER",
    "NOTIFICATION_ENABLED",
    "NOTIFICATION_RETENTION_DAYS",
    "NOTIFICATION_MAX_PER_USER",
]
