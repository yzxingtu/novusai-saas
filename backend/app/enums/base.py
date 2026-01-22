"""
枚举基类模块

提供带标签的枚举基类，支持国际化
"""

from enum import Enum
from typing import Any, TypeVar

T = TypeVar("T", bound="LabeledEnum")


class LabeledEnum(Enum):
    """
    带标签的枚举基类
    
    支持 (value, label_key) 元组形式定义，label_key 用于国际化
    
    Example:
        class StatusEnum(LabeledIntEnum):
            ACTIVE = (1, "status.active")
            INACTIVE = (0, "status.inactive")
        
        StatusEnum.ACTIVE.value  # 1
        StatusEnum.ACTIVE.label  # "启用" (根据当前语言)
        StatusEnum.choices()  # [(1, "启用"), (0, "禁用")]
    """
    
    def __new__(cls, value: Any, label_key: str = "") -> "LabeledEnum":
        """
        创建枚举实例
        
        Args:
            value: 枚举值
            label_key: 国际化 key（可选）
        """
        obj = object.__new__(cls)
        obj._value_ = value
        obj._label_key = label_key  # type: ignore
        return obj
    
    @property
    def label(self) -> str:
        """获取国际化标签"""
        # 延迟导入以避免循环依赖
        from app.core.i18n import _
        
        label_key = getattr(self, "_label_key", "")
        if label_key:
            return _(label_key)
        return self.name
    
    @property
    def label_key(self) -> str:
        """获取标签 key"""
        return getattr(self, "_label_key", "")
    
    @classmethod
    def choices(cls) -> list[tuple[Any, str]]:
        """
        获取选项列表（用于表单下拉框等）
        
        Returns:
            [(value, label), ...]
        """
        return [(member.value, member.label) for member in cls]
    
    @classmethod
    def values(cls) -> list[Any]:
        """获取所有枚举值"""
        return [member.value for member in cls]
    
    @classmethod
    def from_value(cls: type[T], value: Any) -> T | None:
        """
        根据值获取枚举实例
        
        Args:
            value: 枚举值
            
        Returns:
            枚举实例或 None
        """
        for member in cls:
            if member.value == value:
                return member
        return None
    
    @classmethod
    def has_value(cls, value: Any) -> bool:
        """判断值是否存在"""
        return value in cls.values()
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "value": self.value,
            "label": self.label,
            "name": self.name,
        }
    
    @classmethod
    def to_list(cls) -> list[dict[str, Any]]:
        """转换为字典列表"""
        return [member.to_dict() for member in cls]


class LabeledIntEnum(LabeledEnum):
    """带标签的整数枚举基类"""
    
    def __new__(cls, value: int, label_key: str = "") -> "LabeledIntEnum":
        if not isinstance(value, int):
            raise TypeError(f"LabeledIntEnum value must be int, got {type(value)}")
        obj = object.__new__(cls)
        obj._value_ = value
        obj._label_key = label_key  # type: ignore
        return obj


class LabeledStrEnum(LabeledEnum):
    """带标签的字符串枚举基类"""
    
    def __new__(cls, value: str, label_key: str = "") -> "LabeledStrEnum":
        if not isinstance(value, str):
            raise TypeError(f"LabeledStrEnum value must be str, got {type(value)}")
        obj = object.__new__(cls)
        obj._value_ = value
        obj._label_key = label_key  # type: ignore
        return obj


# 别名（兼容旧代码）
BaseEnum = LabeledEnum
IntEnum = LabeledIntEnum
StrEnum = LabeledStrEnum


__all__ = [
    "LabeledEnum",
    "LabeledIntEnum",
    "LabeledStrEnum",
    # 别名
    "BaseEnum",
    "IntEnum",
    "StrEnum",
]
