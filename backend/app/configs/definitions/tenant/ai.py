"""Tenant AI capability awareness config items / 企业 AI 能力感知配置项

Controls whether runtime capability descriptions are injected into the LLM
system prompt and how verbose they should be.
控制是否将运行时能力描述注入到 LLM system prompt，以及描述的详细程度。
"""

from app.configs.definitions.groups import TENANT_AI_GROUP
from app.configs.meta import ConfigMeta, max_value, min_value, option
from app.enums.config import ConfigScope, ConfigValueType

# ==========================================
# Capability awareness switches / 能力感知开关
# ==========================================

TENANT_AI_ENABLE_DYNAMIC_CAPABILITY_AWARENESS = ConfigMeta(
    key="tenant_ai_enable_dynamic_capability_awareness",
    name_key="config.tenant.enable_dynamic_capability_awareness.name",
    description_key="config.tenant.enable_dynamic_capability_awareness.desc",
    scope=ConfigScope.ALL_TENANTS,
    value_type=ConfigValueType.BOOLEAN,
    default_value=True,
    sort_order=10,
)

TENANT_AI_CAPABILITY_DESCRIPTION_STYLE = ConfigMeta(
    key="tenant_ai_capability_description_style",
    name_key="config.tenant.capability_description_style.name",
    description_key="config.tenant.capability_description_style.desc",
    scope=ConfigScope.ALL_TENANTS,
    value_type=ConfigValueType.SELECT,
    default_value="detailed",
    options=[
        option("detailed", "config.tenant.capability_description_style.detailed"),
        option("concise", "config.tenant.capability_description_style.concise"),
    ],
    sort_order=20,
)

TENANT_AI_MAX_CAPABILITY_ITEMS_PER_CATEGORY = ConfigMeta(
    key="tenant_ai_max_capability_items_per_category",
    name_key="config.tenant.max_capability_items_per_category.name",
    description_key="config.tenant.max_capability_items_per_category.desc",
    scope=ConfigScope.ALL_TENANTS,
    value_type=ConfigValueType.NUMBER,
    default_value=20,
    validation_rules=[
        min_value(1, "validation.min_value"),
        max_value(100, "validation.max_value"),
    ],
    sort_order=30,
)


# ==========================================
# Register configs to group / 注册配置到分组
# ==========================================

TENANT_AI_GROUP.configs = [
    TENANT_AI_ENABLE_DYNAMIC_CAPABILITY_AWARENESS,
    TENANT_AI_CAPABILITY_DESCRIPTION_STYLE,
    TENANT_AI_MAX_CAPABILITY_ITEMS_PER_CATEGORY,
]


__all__ = [
    "TENANT_AI_ENABLE_DYNAMIC_CAPABILITY_AWARENESS",
    "TENANT_AI_CAPABILITY_DESCRIPTION_STYLE",
    "TENANT_AI_MAX_CAPABILITY_ITEMS_PER_CATEGORY",
]
