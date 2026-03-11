"""Platform AI Toolkit security config items / 平台 AI Toolkit 安全配置项

Controls user-uploaded Toolkit security policy: security level, memory limit, timeout.
控制用户上传 Toolkit 的安全策略：安全等级、内存限制、超时上限
"""

from app.configs.definitions.groups import PLATFORM_AI_TOOLKIT_GROUP
from app.configs.meta import ConfigMeta, max_value, min_value, option
from app.enums.config import ConfigScope, ConfigValueType

# ==========================================
# Toolkit security level / Toolkit 安全等级
# ==========================================

# Security level / 安全等级
# strict: only safe modules (math/date/JSON) / 仅允许安全模块
# normal: allow network libs, block os/subprocess (default) / 允许网络库，禁止系统模块
# permissive: block only most dangerous modules / 仅禁止最危险模块
TOOLKIT_SECURITY_LEVEL = ConfigMeta(
    key="toolkit_security_level",
    name_key="config.platform.toolkit_security_level.name",
    description_key="config.platform.toolkit_security_level.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.SELECT,
    default_value="normal",
    options=[
        option("strict", "config.platform.toolkit_security_level.strict"),
        option("normal", "config.platform.toolkit_security_level.normal"),
        option("permissive", "config.platform.toolkit_security_level.permissive"),
    ],
    sort_order=10,
)


# ==========================================
# Resource limits / 资源限制
# ==========================================

# Memory limit (MB) / 内存限制 (MB)
TOOLKIT_MEMORY_LIMIT_MB = ConfigMeta(
    key="toolkit_memory_limit_mb",
    name_key="config.platform.toolkit_memory_limit_mb.name",
    description_key="config.platform.toolkit_memory_limit_mb.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.NUMBER,
    default_value=256,
    validation_rules=[
        min_value(64, "validation.min_value"),
        max_value(2048, "validation.max_value"),
    ],
    sort_order=20,
)

# Max execution timeout (seconds) / 最大执行超时 (秒)
TOOLKIT_MAX_TIMEOUT = ConfigMeta(
    key="toolkit_max_timeout",
    name_key="config.platform.toolkit_max_timeout.name",
    description_key="config.platform.toolkit_max_timeout.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.NUMBER,
    default_value=120,
    validation_rules=[
        min_value(5, "validation.min_value"),
        max_value(600, "validation.max_value"),
    ],
    sort_order=30,
)

# Static analysis on upload / 上传时静态分析
TOOLKIT_SCAN_ON_UPLOAD = ConfigMeta(
    key="toolkit_scan_on_upload",
    name_key="config.platform.toolkit_scan_on_upload.name",
    description_key="config.platform.toolkit_scan_on_upload.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.BOOLEAN,
    default_value=True,
    sort_order=40,
)


# ==========================================
# Register configs to group / 注册配置到分组
# ==========================================

PLATFORM_AI_TOOLKIT_GROUP.configs = [
    TOOLKIT_SECURITY_LEVEL,
    TOOLKIT_MEMORY_LIMIT_MB,
    TOOLKIT_MAX_TIMEOUT,
    TOOLKIT_SCAN_ON_UPLOAD,
]
