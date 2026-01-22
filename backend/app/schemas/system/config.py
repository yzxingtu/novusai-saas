"""
系统配置相关 Schema

定义配置管理的请求和响应数据结构
"""

from typing import Any

from pydantic import Field

from app.core.base_schema import BaseSchema


# ==========================================
# 配置选项
# ==========================================

class ConfigOptionSchema(BaseSchema):
    """配置选项"""
    
    value: Any = Field(..., description="选项值")
    label: str = Field(..., description="选项标签")


class ValidationRuleSchema(BaseSchema):
    """验证规则"""
    
    type: str = Field(..., description="规则类型")
    value: Any = Field(..., description="规则值")
    message: str = Field("", description="错误消息")


# ==========================================
# 配置项响应
# ==========================================

class ConfigItemResponse(BaseSchema):
    """配置项响应"""
    
    key: str = Field(..., description="配置键名")
    name: str = Field(..., description="配置名称")
    description: str | None = Field(None, description="配置描述")
    value_type: str = Field(..., description="值类型")
    value: Any = Field(None, description="当前值")
    default_value: Any = Field(None, description="默认值")
    options: list[ConfigOptionSchema] = Field(default_factory=list, description="选项列表")
    validation_rules: list[ValidationRuleSchema] = Field(default_factory=list, description="验证规则")
    is_required: bool = Field(False, description="是否必填")
    is_encrypted: bool = Field(False, description="是否加密")
    sort_order: int = Field(0, description="排序顺序")


# ==========================================
# 配置分组响应
# ==========================================

class ConfigGroupResponse(BaseSchema):
    """配置分组响应"""
    
    code: str = Field(..., description="分组代码")
    name: str = Field(..., description="分组名称")
    description: str | None = Field(None, description="分组描述")
    icon: str | None = Field(None, description="分组图标")
    sort_order: int = Field(0, description="排序顺序")
    configs: list[ConfigItemResponse] = Field(default_factory=list, description="配置项列表")


class ConfigGroupListResponse(BaseSchema):
    """配置分组列表响应（不含配置项）"""
    
    code: str = Field(..., description="分组代码")
    name: str = Field(..., description="分组名称")
    description: str | None = Field(None, description="分组描述")
    icon: str | None = Field(None, description="分组图标")
    sort_order: int = Field(0, description="排序顺序")
    config_count: int = Field(0, description="配置项数量")


# ==========================================
# 配置更新请求
# ==========================================

class ConfigUpdateRequest(BaseSchema):
    """配置更新请求"""
    
    configs: dict[str, Any] = Field(..., description="配置键值对")


class ConfigUpdateItem(BaseSchema):
    """单个配置更新项"""
    
    key: str = Field(..., description="配置键名")
    value: Any = Field(..., description="配置值")


# ==========================================
# 批量配置更新请求
# ==========================================

class BatchConfigUpdateRequest(BaseSchema):
    """批量配置更新请求"""
    
    items: list[ConfigUpdateItem] = Field(..., description="配置更新列表")


__all__ = [
    "ConfigOptionSchema",
    "ValidationRuleSchema",
    "ConfigItemResponse",
    "ConfigGroupResponse",
    "ConfigGroupListResponse",
    "ConfigUpdateRequest",
    "ConfigUpdateItem",
    "BatchConfigUpdateRequest",
]
