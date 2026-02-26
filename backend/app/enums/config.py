"""
配置模块枚举

定义配置系统相关的枚举类型
"""

from app.enums.base import StrEnum
from app.enums.common import ResourceScopeEnum


# [DEPRECATED] ConfigScope 已统一为 ResourceScopeEnum，保留别名兼容旧代码引用
# 旧值映射: PLATFORM→ADMIN_ONLY, TENANT→ALL_TENANTS
ConfigScope = ResourceScopeEnum


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
    TAG = ("tag", "enum.config_value_type.tag")  # 标签选择
    FILE = ("file", "enum.config_value_type.file")  # 文件上传


__all__ = [
    "ConfigScope",
    "ConfigValueType",
]
