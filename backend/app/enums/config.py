"""
配置模块枚举

定义配置系统相关的枚举类型
"""

from app.enums.base import StrEnum


class ConfigScope(StrEnum):
    """配置作用域枚举"""
    
    PLATFORM = ("platform", "enum.config_scope.platform")  # 平台级配置
    TENANT = ("tenant", "enum.config_scope.tenant")  # 租户级配置


class ConfigValueType(StrEnum):
    """配置值类型枚举"""
    
    STRING = ("string", "enum.config_value_type.string")  # 字符串
    NUMBER = ("number", "enum.config_value_type.number")  # 数字
    BOOLEAN = ("boolean", "enum.config_value_type.boolean")  # 布尔值
    SELECT = ("select", "enum.config_value_type.select")  # 下拉选择
    MULTI_SELECT = ("multi_select", "enum.config_value_type.multi_select")  # 多选
    JSON = ("json", "enum.config_value_type.json")  # JSON 对象
    TEXT = ("text", "enum.config_value_type.text")  # 多行文本
    PASSWORD = ("password", "enum.config_value_type.password")  # 密码（加密存储）
    COLOR = ("color", "enum.config_value_type.color")  # 颜色选择器
    IMAGE = ("image", "enum.config_value_type.image")  # 图片上传


__all__ = [
    "ConfigScope",
    "ConfigValueType",
]
