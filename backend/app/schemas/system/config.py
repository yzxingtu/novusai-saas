"""
系统配置相关 Schema / System Config Schema

定义配置管理的请求和响应数据结构
Defines config management request and response data structures.
"""

from typing import Any

from pydantic import Field

from app.core.base_schema import BaseSchema

# ==========================================
# 配置选项 / Config options
# ==========================================


class ConfigOptionSchema(BaseSchema):
    """配置选项 / Config option schema."""

    value: Any = Field(..., description="选项值")
    label: str = Field(..., description="选项标签")


class ValidationRuleSchema(BaseSchema):
    """验证规则 / Validation rule schema."""

    type: str = Field(..., description="规则类型")
    value: Any = Field(..., description="规则值")
    message: str = Field("", description="错误消息")


class DisplayRuleSchema(BaseSchema):
    """显示规则 / Display rule schema."""

    field: str = Field(..., description="依赖字段的 key")
    operator: str = Field("equals", description="规则类型: equals / in")
    value: Any = Field(None, description="目标值或数组")
    action: str = Field("show", description="动作: show")


class ConfigItemResponse(BaseSchema):
    """配置项响应 / Config item response."""

    key: str = Field(..., description="配置键名")
    name: str = Field(..., description="配置名称")
    description: str | None = Field(None, description="配置描述")
    value_type: str = Field(..., description="值类型")
    value: Any = Field(None, description="当前值")
    default_value: Any = Field(None, description="默认值")
    options: list[ConfigOptionSchema] = Field(
        default_factory=list, description="选项列表"
    )
    validation_rules: list[ValidationRuleSchema] = Field(
        default_factory=list, description="验证规则"
    )
    is_required: bool = Field(False, description="是否必填")
    is_encrypted: bool = Field(False, description="是否加密")
    sort_order: int = Field(0, description="排序顺序")
    display_rules: list[DisplayRuleSchema] = Field(
        default_factory=list, description="显示/隐藏规则"
    )
    value_path: str = Field("", description="子字段映射到父 JSON 的路径")
    children: list["ConfigItemResponse"] = Field(
        default_factory=list, description="子字段配置"
    )
    tag_separator: str = Field(",", description="标签分隔符（TAG 类型专用）")
    file_accept: str = Field("", description="文件接受类型（FILE 类型专用）")


# ==========================================
# 配置分组响应 / Config group response
# ==========================================


class ConfigGroupResponse(BaseSchema):
    """配置分组响应 / Config group response."""

    code: str = Field(..., description="分组代码")
    name: str = Field(..., description="分组名称")
    description: str | None = Field(None, description="分组描述")
    icon: str | None = Field(None, description="分组图标")
    sort_order: int = Field(0, description="排序顺序")
    configs: list[ConfigItemResponse] = Field(
        default_factory=list, description="配置项列表"
    )


class ConfigGroupListResponse(BaseSchema):
    """配置分组列表响应（不含配置项） / Config group list response (no config items)."""

    code: str = Field(..., description="分组代码")
    name: str = Field(..., description="分组名称")
    description: str | None = Field(None, description="分组描述")
    icon: str | None = Field(None, description="分组图标")
    sort_order: int = Field(0, description="排序顺序")
    config_count: int = Field(0, description="配置项数量")


# ==========================================
# 配置更新请求 / Config update request
# ==========================================


class ConfigUpdateRequest(BaseSchema):
    """配置更新请求 / Config update request"""

    configs: dict[str, Any] = Field(..., description="配置键值对")


class ConfigUpdateItem(BaseSchema):
    """单个配置更新项 / Single config update item."""

    key: str = Field(..., description="配置键名")
    value: Any = Field(..., description="配置值")


# ==========================================
# 批量配置更新请求 / Batch config update
# ==========================================


class BatchConfigUpdateRequest(BaseSchema):
    """批量配置更新请求 / Batch config update request."""

    items: list[ConfigUpdateItem] = Field(..., description="配置更新列表")


__all__ = [
    "ConfigOptionSchema",
    "ValidationRuleSchema",
    "DisplayRuleSchema",
    "ConfigItemResponse",
    "ConfigGroupResponse",
    "ConfigGroupListResponse",
    "ConfigUpdateRequest",
    "ConfigUpdateItem",
    "BatchConfigUpdateRequest",
]
