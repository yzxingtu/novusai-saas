"""
配置元数据定义

定义配置项和配置分组的元数据类，用于声明式配置定义
"""

from dataclasses import dataclass, field
from typing import Any, Callable

# 直接从子模块导入，避免循环依赖
from app.enums.config import ConfigScope, ConfigValueType


@dataclass
class ConfigOption:
    """配置选项（用于 select/multi_select 类型）"""
    
    value: Any
    """选项值"""
    
    label_key: str
    """选项标签的 i18n 键"""
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "value": self.value,
            "label_key": self.label_key,
        }


@dataclass
class ValidationRule:
    """验证规则"""
    
    type: str
    """规则类型: min/max/min_length/max_length/pattern/custom"""
    
    value: Any
    """规则值"""
    
    message_key: str = ""
    """错误消息的 i18n 键"""
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "type": self.type,
            "value": self.value,
            "message_key": self.message_key,
        }


@dataclass
class ConfigMeta:
    """
    配置项元数据
    
    定义单个配置项的完整元数据信息
    
    Example:
        site_name = ConfigMeta(
            key="site_name",
            name_key="config.platform.site_name",
            description_key="config.platform.site_name.desc",
            scope=ConfigScope.PLATFORM,
            value_type=ConfigValueType.STRING,
            default_value="NovusAI SaaS",
            is_required=True,
        )
    """
    
    key: str
    """配置键名（组内唯一）"""
    
    name_key: str
    """名称的 i18n 键"""
    
    scope: ConfigScope = ConfigScope.PLATFORM
    """作用域：platform/tenant"""
    
    value_type: ConfigValueType = ConfigValueType.STRING
    """值类型"""
    
    default_value: Any = None
    """默认值"""
    
    description_key: str = ""
    """描述的 i18n 键"""
    
    options: list[ConfigOption] = field(default_factory=list)
    """选项列表（用于 select/multi_select）"""
    
    validation_rules: list[ValidationRule] = field(default_factory=list)
    """验证规则列表"""
    
    is_required: bool = False
    """是否必填"""
    
    is_visible: bool = True
    """是否在配置界面显示"""
    
    is_encrypted: bool = False
    """是否加密存储（用于敏感配置如密码、API Key）"""
    
    sort_order: int = 0
    """排序顺序"""
    
    # 运行时属性
    group_code: str = ""
    """所属分组代码（由注册中心设置）"""
    
    def __post_init__(self) -> None:
        """初始化后处理"""
        # 密码类型默认加密
        if self.value_type == ConfigValueType.PASSWORD:
            self.is_encrypted = True
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典（用于序列化）"""
        return {
            "key": self.key,
            "name_key": self.name_key,
            "description_key": self.description_key,
            "scope": self.scope.value,
            "value_type": self.value_type.value,
            "default_value": self.default_value,
            "options": [opt.to_dict() for opt in self.options],
            "validation_rules": [rule.to_dict() for rule in self.validation_rules],
            "is_required": self.is_required,
            "is_visible": self.is_visible,
            "is_encrypted": self.is_encrypted,
            "sort_order": self.sort_order,
            "group_code": self.group_code,
        }


class ConfigGroupMeta:
    """
    配置分组元数据
    
    定义配置分组的元数据信息
    
    Example:
        platform_basic = ConfigGroupMeta(
            code="platform_basic",
            name_key="config.group.platform_basic",
            scope=ConfigScope.PLATFORM,
            icon="settings",
            configs=[site_name, site_description],
        )
    """
    
    def __init__(
        self,
        code: str,
        name_key: str,
        scope: ConfigScope = ConfigScope.PLATFORM,
        description_key: str = "",
        icon: str = "",
        parent_code: str = "",
        sort_order: int = 0,
        is_active: bool = True,
        configs: list[ConfigMeta] | None = None,
        children: list["ConfigGroupMeta"] | None = None,
    ):
        self.code = code
        self.name_key = name_key
        self.scope = scope
        self.description_key = description_key
        self.icon = icon
        self.parent_code = parent_code
        self.sort_order = sort_order
        self.is_active = is_active
        self._configs: list[ConfigMeta] = []
        self.children: list["ConfigGroupMeta"] = children or []
        
        # 设置配置项（通过 property setter）
        if configs:
            self.configs = configs
    
    @property
    def configs(self) -> list[ConfigMeta]:
        """分组下的配置项列表"""
        return self._configs
    
    @configs.setter
    def configs(self, value: list[ConfigMeta]) -> None:
        """设置配置项列表，同时更新每个配置项的 group_code"""
        self._configs = value
        for config in self._configs:
            config.group_code = self.code
            # 继承分组的作用域
            if config.scope != self.scope:
                config.scope = self.scope
    
    def add_config(self, config: ConfigMeta) -> "ConfigGroupMeta":
        """添加配置项"""
        config.group_code = self.code
        config.scope = self.scope
        self.configs.append(config)
        return self
    
    def add_child(self, child: "ConfigGroupMeta") -> "ConfigGroupMeta":
        """添加子分组"""
        child.parent_code = self.code
        self.children.append(child)
        return self
    
    def get_all_configs(self) -> list[ConfigMeta]:
        """获取所有配置项（包括子分组的）"""
        configs = list(self.configs)
        for child in self.children:
            configs.extend(child.get_all_configs())
        return configs
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典（用于序列化）"""
        return {
            "code": self.code,
            "name_key": self.name_key,
            "description_key": self.description_key,
            "scope": self.scope.value,
            "icon": self.icon,
            "parent_code": self.parent_code,
            "sort_order": self.sort_order,
            "is_active": self.is_active,
            "configs": [config.to_dict() for config in self.configs],
            "children": [child.to_dict() for child in self.children],
        }


# 便捷函数：创建验证规则
def min_value(value: int | float, message_key: str = "") -> ValidationRule:
    """最小值验证"""
    return ValidationRule(type="min", value=value, message_key=message_key)


def max_value(value: int | float, message_key: str = "") -> ValidationRule:
    """最大值验证"""
    return ValidationRule(type="max", value=value, message_key=message_key)


def min_length(value: int, message_key: str = "") -> ValidationRule:
    """最小长度验证"""
    return ValidationRule(type="min_length", value=value, message_key=message_key)


def max_length(value: int, message_key: str = "") -> ValidationRule:
    """最大长度验证"""
    return ValidationRule(type="max_length", value=value, message_key=message_key)


def pattern(regex: str, message_key: str = "") -> ValidationRule:
    """正则表达式验证"""
    return ValidationRule(type="pattern", value=regex, message_key=message_key)


def option(value: Any, label_key: str) -> ConfigOption:
    """创建选项"""
    return ConfigOption(value=value, label_key=label_key)


__all__ = [
    "ConfigMeta",
    "ConfigGroupMeta",
    "ConfigOption",
    "ValidationRule",
    # 便捷函数
    "min_value",
    "max_value",
    "min_length",
    "max_length",
    "pattern",
    "option",
]
