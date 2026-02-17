"""
模型基类模块

提供所有数据库模型的基类，包括：
- BaseModel: 通用模型基类
- TenantModel: 租户级模型基类
"""

import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, Column, DateTime, Integer, String, inspect

from app.enums.common import DeleteLevelEnum
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import DeclarativeBase


def utc_now() -> datetime:
    """Return current UTC time as a naive datetime.

    Replacement for deprecated ``datetime.utcnow()`` that is compatible
    with ``TIMESTAMP WITHOUT TIME ZONE`` columns used throughout the project.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    """SQLAlchemy 声明基类"""
    pass


class BaseModel(Base):
    """
    模型基类
    
    提供所有模型的通用字段和方法：
    - id: 主键
    - created_at: 创建时间
    - updated_at: 更新时间
    - is_deleted: 软删除标记
    """
    
    __abstract__ = True
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    created_at = Column(
        DateTime,
        default=lambda: utc_now(),
        nullable=False,
        comment="创建时间"
    )
    updated_at = Column(
        DateTime,
        default=lambda: utc_now(),
        onupdate=lambda: utc_now(),
        nullable=False,
        comment="更新时间"
    )
    is_deleted = Column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        comment="软删除标记"
    )
    deleted_at = Column(
        DateTime,
        nullable=True,
        default=None,
        comment="删除时间"
    )
    delete_level = Column(
        String(20),
        nullable=True,
        default=None,
        comment="删除层级: tenant=租户回收站, admin=管理端回收站"
    )
    
    @declared_attr
    def __tablename__(cls) -> str:
        """
        自动生成表名
        
        将类名从 PascalCase 转换为 snake_case
        例如：UserProfile -> user_profile
        """
        name = cls.__name__
        # 在大写字母前插入下划线，然后转小写
        return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
    
    def to_dict(self, exclude: set[str] | None = None) -> dict[str, Any]:
        """
        转换为字典
        
        通过 mapper.column_attrs 遍历，正确处理属性名与列名不同的情况
        （如 metadata_ = mapped_column("metadata", ...)）
        
        Args:
            exclude: 要排除的字段集合（使用数据库列名）
        
        Returns:
            模型数据字典
        """
        exclude = exclude or set()
        result = {}
        for attr in inspect(self.__class__).mapper.column_attrs:
            col_name = attr.columns[0].name
            if col_name not in exclude:
                result[col_name] = getattr(self, attr.key)
        return result
    
    def soft_delete(self, level: str = "admin") -> None:
        """
        软删除
        
        Args:
            level: 删除层级 ('tenant' 或 'admin')
        """
        self.is_deleted = True
        self.deleted_at = utc_now()
        self.delete_level = level
        self.updated_at = utc_now()
    
    def restore(self) -> None:
        """恢复软删除"""
        self.is_deleted = False
        self.deleted_at = None
        self.delete_level = None
        self.updated_at = utc_now()
    
    def escalate_delete(self) -> None:
        """升级删除层级（tenant → admin），重置删除时间"""
        self.delete_level = DeleteLevelEnum.ADMIN.value
        self.deleted_at = utc_now()
        self.updated_at = utc_now()
    
    def update_from_dict(self, data: dict[str, Any]) -> None:
        """
        从字典更新模型字段
        
        Args:
            data: 更新数据字典
        """
        for key, value in data.items():
            if hasattr(self, key) and key not in ("id", "created_at"):
                setattr(self, key, value)
        self.updated_at = utc_now()
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(id={self.id})>"


class TenantModel(BaseModel):
    """
    租户模型基类
    
    继承自 BaseModel，添加 tenant_id 字段用于多租户数据隔离
    """
    
    __abstract__ = True
    
    tenant_id = Column(
        Integer,
        nullable=False,
        index=True,
        comment="租户ID"
    )
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(id={self.id}, tenant_id={self.tenant_id})>"


# 导出
__all__ = ["Base", "BaseModel", "TenantModel", "utc_now"]
