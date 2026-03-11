"""
配置模块枚举 / Configuration Enum Module

定义配置系统相关的枚举类型
Defines configuration system related enum types.
"""

from app.enums.base import StrEnum
from app.enums.common import ResourceScopeEnum

# [DEPRECATED] ConfigScope unified to ResourceScopeEnum, alias kept for backward compat / ConfigScope 已统一为 ResourceScopeEnum，保留别名兼容旧代码引用
# Old value mapping / 旧值映射: PLATFORM→ADMIN_ONLY, TENANT→ALL_TENANTS
ConfigScope = ResourceScopeEnum


class ConfigValueType(StrEnum):
    """Config Value Type Enum / 配置值类型枚举"""

    STRING = ("string", "enum.config_value_type.string")  # String / 字符串
    NUMBER = ("number", "enum.config_value_type.number")  # Number / 数字
    BOOLEAN = ("boolean", "enum.config_value_type.boolean")  # Boolean / 布尔值
    SELECT = ("select", "enum.config_value_type.select")  # Dropdown / 下拉选择
    MULTI_SELECT = ("multi_select", "enum.config_value_type.multi_select")  # Multi-select / 多选
    JSON = ("json", "enum.config_value_type.json")  # JSON object / JSON 对象
    TEXT = ("text", "enum.config_value_type.text")  # Multiline text / 多行文本
    PASSWORD = ("password", "enum.config_value_type.password")  # Password (encrypted) / 密码（加密存储）
    COLOR = ("color", "enum.config_value_type.color")  # Color picker / 颜色选择器
    IMAGE = ("image", "enum.config_value_type.image")  # Image upload / 图片上传
    TAG = ("tag", "enum.config_value_type.tag")  # Tag selector / 标签选择
    FILE = ("file", "enum.config_value_type.file")  # File upload / 文件上传


__all__ = [
    "ConfigScope",
    "ConfigValueType",
]
