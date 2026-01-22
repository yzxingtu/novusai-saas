"""
系统配置模型

定义配置分组和配置项的数据模型，支持平台级和租户级配置
"""

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import BaseModel, TenantModel
from app.enums.config import ConfigScope, ConfigValueType


class SystemConfigGroup(BaseModel):
    """
    配置分组模型
    
    用于组织和分类配置项，支持嵌套分组
    """
    
    __tablename__ = "system_config_groups"
    
    # 可过滤字段声明
    __filterable__ = {
        "id": "id",
        "code": "code",
        "scope": "scope",
        "parent_id": "parent_id",
        "is_active": "is_active",
        "sort_order": "sort_order",
        "created_at": "created_at",
        "updated_at": "updated_at",
    }
    
    # 下拉选项配置
    __selectable__ = {
        "label": "name_key",
        "value": "id",
        "search": ["code", "name_key"],
        "extra": ["scope", "icon"],
    }
    
    # 分组标识
    code: Mapped[str] = mapped_column(
        String(100), unique=True, index=True, comment="分组代码（唯一标识）"
    )
    
    # 国际化名称键
    name_key: Mapped[str] = mapped_column(
        String(200), comment="名称的 i18n 键"
    )
    description_key: Mapped[str | None] = mapped_column(
        String(200), nullable=True, comment="描述的 i18n 键"
    )
    
    # 作用域
    scope: Mapped[str] = mapped_column(
        String(20), default=ConfigScope.PLATFORM.value, index=True,
        comment="作用域: platform/tenant"
    )
    
    # 层级关系
    parent_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("system_config_groups.id"), nullable=True,
        index=True, comment="父分组 ID"
    )
    
    # 显示设置
    icon: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="分组图标"
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, default=0, comment="排序顺序"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, comment="是否启用"
    )
    
    # 关系
    parent: Mapped["SystemConfigGroup | None"] = relationship(
        "SystemConfigGroup",
        remote_side="SystemConfigGroup.id",
        back_populates="children",
        lazy="selectin",
    )
    children: Mapped[list["SystemConfigGroup"]] = relationship(
        "SystemConfigGroup",
        back_populates="parent",
        lazy="selectin",
    )
    configs: Mapped[list["SystemConfig"]] = relationship(
        "SystemConfig",
        back_populates="group",
        lazy="selectin",
    )
    
    def __repr__(self) -> str:
        return f"<SystemConfigGroup(id={self.id}, code={self.code})>"


class SystemConfig(BaseModel):
    """
    系统配置项模型（配置元数据定义）
    
    定义配置项的元数据，包括键名、类型、默认值等
    实际配置值存储在 SystemConfigValue 中
    """
    
    __tablename__ = "system_configs"
    
    # 复合唯一索引
    __table_args__ = (
        Index("ix_system_configs_group_key", "group_id", "key", unique=True),
    )
    
    # 可过滤字段声明
    __filterable__ = {
        "id": "id",
        "key": "key",
        "group_id": "group_id",
        "scope": "scope",
        "value_type": "value_type",
        "is_required": "is_required",
        "is_visible": "is_visible",
        "is_encrypted": "is_encrypted",
        "sort_order": "sort_order",
        "created_at": "created_at",
        "updated_at": "updated_at",
    }
    
    # 下拉选项配置
    __selectable__ = {
        "label": "name_key",
        "value": "id",
        "search": ["key", "name_key"],
        "extra": ["scope", "value_type"],
    }
    
    # 配置键（组内唯一）
    key: Mapped[str] = mapped_column(
        String(100), index=True, comment="配置键名"
    )
    
    # 所属分组
    group_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("system_config_groups.id"), index=True,
        comment="所属分组 ID"
    )
    
    # 国际化名称键
    name_key: Mapped[str] = mapped_column(
        String(200), comment="名称的 i18n 键"
    )
    description_key: Mapped[str | None] = mapped_column(
        String(200), nullable=True, comment="描述的 i18n 键"
    )
    
    # 作用域
    scope: Mapped[str] = mapped_column(
        String(20), default=ConfigScope.PLATFORM.value, index=True,
        comment="作用域: platform/tenant"
    )
    
    # 值类型和默认值
    value_type: Mapped[str] = mapped_column(
        String(20), default=ConfigValueType.STRING.value,
        comment="值类型: string/number/boolean/select/multi_select/json/text/password/color/image"
    )
    default_value: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="默认值（JSON 字符串存储）"
    )
    
    # 验证规则
    validation_rules: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="验证规则（JSON 格式）"
    )
    options: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="选项列表（用于 select/multi_select，JSON 格式）"
    )
    
    # 配置属性
    is_required: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="是否必填"
    )
    is_visible: Mapped[bool] = mapped_column(
        Boolean, default=True, comment="是否在配置界面显示"
    )
    is_encrypted: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="是否加密存储"
    )
    
    # 显示设置
    sort_order: Mapped[int] = mapped_column(
        Integer, default=0, comment="排序顺序"
    )
    
    # 关系
    group: Mapped["SystemConfigGroup"] = relationship(
        "SystemConfigGroup",
        back_populates="configs",
        lazy="selectin",
    )
    values: Mapped[list["SystemConfigValue"]] = relationship(
        "SystemConfigValue",
        back_populates="config",
        lazy="selectin",
    )
    
    def __repr__(self) -> str:
        return f"<SystemConfig(id={self.id}, key={self.key})>"


class SystemConfigValue(TenantModel):
    """
    系统配置值模型
    
    存储实际的配置值，支持：
    - 平台级配置：tenant_id = 0
    - 租户级配置：tenant_id > 0
    """
    
    __tablename__ = "system_config_values"
    
    # 复合唯一索引：同一配置项在同一租户下只能有一个值
    __table_args__ = (
        Index("ix_system_config_values_config_tenant", "config_id", "tenant_id", unique=True),
    )
    
    # 可过滤字段声明
    __filterable__ = {
        "id": "id",
        "config_id": "config_id",
        "tenant_id": "tenant_id",
        "created_at": "created_at",
        "updated_at": "updated_at",
    }
    
    # 关联的配置项
    config_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("system_configs.id"), index=True,
        comment="配置项 ID"
    )
    
    # 配置值（JSON 字符串存储，支持各种类型）
    value: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="配置值（JSON 字符串存储）"
    )
    
    # 关系
    config: Mapped["SystemConfig"] = relationship(
        "SystemConfig",
        back_populates="values",
        lazy="selectin",
    )
    
    def __repr__(self) -> str:
        return f"<SystemConfigValue(id={self.id}, config_id={self.config_id}, tenant_id={self.tenant_id})>"


__all__ = [
    "SystemConfigGroup",
    "SystemConfig",
    "SystemConfigValue",
]
