"""Configuration metadata definitions / 配置元数据定义

Defines metadata classes for config items and config groups, used for declarative config definitions.
定义配置项和配置分组的元数据类，用于声明式配置定义
"""

from dataclasses import dataclass, field
from typing import Any

# Import directly from submodule to avoid circular dependency / 直接从子模块导入，避免循环依赖
from app.enums.config import ConfigScope, ConfigValueType


@dataclass
class ConfigOption:
    """Config option (for select/multi_select types) / 配置选项（用于 select/multi_select 类型）"""

    value: Any
    """Option value / 选项值"""

    label_key: str
    """Option label i18n key / 选项标签的 i18n 键"""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict / 转换为字典"""
        return {
            "value": self.value,
            "label_key": self.label_key,
        }


@dataclass
class ValidationRule:
    """Validation rule / 验证规则"""

    type: str
    """Rule type: min/max/min_length/max_length/pattern/custom / 规则类型"""

    value: Any
    """Rule value / 规则值"""

    message_key: str = ""
    """Error message i18n key / 错误消息的 i18n 键"""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict / 转换为字典"""
        return {
            "type": self.type,
            "value": self.value,
            "message_key": self.message_key,
        }


@dataclass
class DisplayRule:
    field: str
    operator: str = "equals"
    value: Any = None
    action: str = "show"

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "operator": self.operator,
            "value": self.value,
            "action": self.action,
        }


@dataclass
class ConfigMeta:
    """
    Config item metadata / 配置项元数据

    Defines complete metadata for a single config item.
    定义单个配置项的完整元数据信息

    Example:
        site_name = ConfigMeta(
            key="site_name",
            name_key="config.platform.site_name",
            description_key="config.platform.site_name.desc",
            scope=ConfigScope.ADMIN_ONLY,
            value_type=ConfigValueType.STRING,
            default_value="NovusAI SaaS",
            is_required=True,
        )
    """

    key: str
    """Config key (unique within group) / 配置键名（组内唯一）"""

    name_key: str
    """Name i18n key / 名称的 i18n 键"""

    scope: ConfigScope = ConfigScope.ADMIN_ONLY
    """Scope: platform/tenant / 作用域"""

    value_type: ConfigValueType = ConfigValueType.STRING
    """Value type / 值类型"""

    default_value: Any = None
    """Default value / 默认值"""

    description_key: str = ""
    """Description i18n key / 描述的 i18n 键"""

    options: list[ConfigOption] = field(default_factory=list)
    """Options list (for select/multi_select) / 选项列表"""

    validation_rules: list[ValidationRule] = field(default_factory=list)
    """Validation rules list / 验证规则列表"""

    is_required: bool = False
    """Whether required / 是否必填"""

    is_visible: bool = True
    """Whether visible in config UI / 是否在配置界面显示"""

    is_encrypted: bool = False
    """Whether encrypted (for sensitive configs like passwords, API keys) / 是否加密存储"""

    sort_order: int = 0
    """Sort order / 排序顺序"""

    display_rules: list[DisplayRule] = field(default_factory=list)
    """Display/hide rules / 显示/隐藏规则"""

    value_path: str = ""
    """Path for mapping child fields to parent JSON / 用于子字段映射到父 JSON 的路径"""

    children: list["ConfigMeta"] = field(default_factory=list)
    """Child field configs / 子字段配置"""

    # TAG type specific params / TAG 类型专用参数
    tag_separator: str = ","
    """Tag separator (for TAG type, default comma) / 标签分隔符"""

    # FILE type specific params / FILE 类型专用参数
    file_accept: str = ""
    """File accept types (for FILE type, e.g. '.pdf,.doc' or 'image/*') / 文件接受类型"""

    # Runtime properties / 运行时属性
    group_code: str = ""
    """Group code (set by registry) / 所属分组代码"""

    def __post_init__(self) -> None:
        """Post-init processing / 初始化后处理"""
        # Password type defaults to encrypted / 密码类型默认加密
        if self.value_type == ConfigValueType.PASSWORD:
            self.is_encrypted = True
        for child in self.children:
            if child.scope != self.scope:
                child.scope = self.scope

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict (for serialization) / 转换为字典（用于序列化）"""
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
            "display_rules": [rule.to_dict() for rule in self.display_rules],
            "value_path": self.value_path,
            "children": [child.to_dict() for child in self.children],
            "tag_separator": self.tag_separator,
            "file_accept": self.file_accept,
        }

    def set_group_code(self, group_code: str) -> None:
        self.group_code = group_code
        for child in self.children:
            child.group_code = group_code


class ConfigGroupMeta:
    """
    Config group metadata / 配置分组元数据

    Defines metadata for config groups.
    定义配置分组的元数据信息

    Example:
        platform_basic = ConfigGroupMeta(
            code="platform_basic",
            name_key="config.group.platform_basic",
            scope=ConfigScope.ADMIN_ONLY,
            icon="settings",
            configs=[site_name, site_description],
        )
    """

    def __init__(
        self,
        code: str,
        name_key: str,
        scope: ConfigScope = ConfigScope.ADMIN_ONLY,
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
        self.children: list[ConfigGroupMeta] = children or []

        # Set configs (via property setter) / 设置配置项（通过 property setter）
        if configs:
            self.configs = configs

    @property
    def configs(self) -> list[ConfigMeta]:
        """Config items list under this group / 分组下的配置项列表"""
        return self._configs

    @configs.setter
    def configs(self, value: list[ConfigMeta]) -> None:
        """Set config items list, also updates each config's group_code / 设置配置项列表，同时更新 group_code"""
        self._configs = value
        for config in self._configs:
            config.set_group_code(self.code)
            # Inherit group scope / 继承分组的作用域
            if config.scope != self.scope:
                config.scope = self.scope

    def add_config(self, config: ConfigMeta) -> "ConfigGroupMeta":
        """Add config item / 添加配置项"""
        config.group_code = self.code
        config.scope = self.scope
        self.configs.append(config)
        return self

    def add_child(self, child: "ConfigGroupMeta") -> "ConfigGroupMeta":
        """Add child group / 添加子分组"""
        child.parent_code = self.code
        self.children.append(child)
        return self

    def get_all_configs(self) -> list[ConfigMeta]:
        """Get all config items (including child groups) / 获取所有配置项（包括子分组的）"""
        configs = list(self.configs)
        for child in self.children:
            configs.extend(child.get_all_configs())
        return configs

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict (for serialization) / 转换为字典（用于序列化）"""
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


# Convenience functions: create validation rules / 便捷函数：创建验证规则
def min_value(value: int | float, message_key: str = "") -> ValidationRule:
    """Min value validation / 最小值验证"""
    return ValidationRule(type="min", value=value, message_key=message_key)


def max_value(value: int | float, message_key: str = "") -> ValidationRule:
    """Max value validation / 最大值验证"""
    return ValidationRule(type="max", value=value, message_key=message_key)


def min_length(value: int, message_key: str = "") -> ValidationRule:
    """Min length validation / 最小长度验证"""
    return ValidationRule(type="min_length", value=value, message_key=message_key)


def max_length(value: int, message_key: str = "") -> ValidationRule:
    """Max length validation / 最大长度验证"""
    return ValidationRule(type="max_length", value=value, message_key=message_key)


def pattern(regex: str, message_key: str = "") -> ValidationRule:
    """Regex pattern validation / 正则表达式验证"""
    return ValidationRule(type="pattern", value=regex, message_key=message_key)


def option(value: Any, label_key: str) -> ConfigOption:
    """Create option / 创建选项"""
    return ConfigOption(value=value, label_key=label_key)


__all__ = [
    "ConfigMeta",
    "ConfigGroupMeta",
    "ConfigOption",
    "ValidationRule",
    # Convenience functions / 便捷函数
    "min_value",
    "max_value",
    "min_length",
    "max_length",
    "pattern",
    "option",
]
