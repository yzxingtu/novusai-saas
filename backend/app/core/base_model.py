"""
模型基类模块 / Model Base Module

提供所有数据库模型的基类，包括：
Provides base classes for all database models, including:
- BaseModel: 通用模型基类 / Generic model base class
- TenantModel: 企业级模型基类 / Tenant-scoped model base class
"""

import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, Column, DateTime, Integer, String, inspect
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import DeclarativeBase

from app.enums.common import DeleteLevelEnum


def utc_now() -> datetime:
    """
    返回当前 UTC 时间（无时区的 datetime）。 / Return current UTC time as a naive datetime.

    替代已废弃的 ``datetime.utcnow()``，兼容项目中使用的 ``TIMESTAMP WITHOUT TIME ZONE`` 列。
    Replacement for deprecated ``datetime.utcnow()`` that is compatible
    with ``TIMESTAMP WITHOUT TIME ZONE`` columns used throughout the project.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    """SQLAlchemy 声明基类 / SQLAlchemy declarative base class"""
    pass


class BaseModel(Base):
    """
    模型基类 / Model Base Class

    提供所有模型的通用字段和方法：
    Provides common fields and methods for all models:
    - id: 主键 / Primary key
    - created_at: 创建时间 / Creation timestamp
    - updated_at: 更新时间 / Last update timestamp
    - is_deleted: 软删除标记 / Soft-delete flag
    """

    __abstract__ = True

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    created_at = Column(
        DateTime,
        default=lambda: utc_now(),
        nullable=False,
        comment="创建时间 / Created at"
    )
    updated_at = Column(
        DateTime,
        default=lambda: utc_now(),
        onupdate=lambda: utc_now(),
        nullable=False,
        comment="更新时间 / Updated at"
    )
    is_deleted = Column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        comment="软删除标记 / Soft-delete flag"
    )
    deleted_at = Column(
        DateTime,
        nullable=True,
        default=None,
        comment="删除时间 / Deleted at"
    )
    delete_level = Column(
        String(20),
        nullable=True,
        default=None,
        comment="删除层级 / Delete level: tenant=tenant recycle bin, admin=admin recycle bin"
    )

    @declared_attr
    def __tablename__(cls) -> str:
        """
        自动生成表名 / Auto-generate table name

        将类名从 PascalCase 转换为 snake_case
        Convert class name from PascalCase to snake_case.
        e.g. UserProfile -> user_profile
        """
        name = cls.__name__
        # 在大写字母前插入下划线，然后转小写 / Insert underscore before uppercase letters, then lowercase
        return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()

    def to_dict(self, exclude: set[str] | None = None) -> dict[str, Any]:
        """
        转换为字典 / Convert to dictionary

        通过 mapper.column_attrs 遍历，正确处理属性名与列名不同的情况
        Iterates via mapper.column_attrs to correctly handle cases where
        attribute names differ from column names (e.g. metadata_ = mapped_column("metadata", ...))

        Args:
            exclude: 要排除的字段集合（使用数据库列名） / Fields to exclude (using DB column names)

        Returns:
            模型数据字典 / Model data dictionary
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
        软删除 / Soft delete

        Args:
            level: 删除层级 / Delete level ('tenant' or 'admin')
        """
        self.is_deleted = True
        self.deleted_at = utc_now()
        self.delete_level = level
        self.updated_at = utc_now()

    def restore(self) -> None:
        """恢复软删除 / Restore soft-deleted record"""
        self.is_deleted = False
        self.deleted_at = None
        self.delete_level = None
        self.updated_at = utc_now()

    def escalate_delete(self) -> None:
        """升级删除层级 / Escalate delete level (tenant → admin), reset deleted_at"""
        self.delete_level = DeleteLevelEnum.ADMIN.value
        self.deleted_at = utc_now()
        self.updated_at = utc_now()

    def update_from_dict(self, data: dict[str, Any]) -> None:
        """
        从字典更新模型字段 / Update model fields from dictionary

        Args:
            data: 更新数据字典 / Update data dictionary
        """
        for key, value in data.items():
            if hasattr(self, key) and key not in ("id", "created_at"):
                setattr(self, key, value)
        self.updated_at = utc_now()

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(id={self.id})>"


class TenantModel(BaseModel):
    """
    企业模型基类 / Tenant Model Base Class

    继承自 BaseModel，添加 tenant_id 字段用于多企业数据隔离
    Extends BaseModel with tenant_id field for multi-tenant data isolation.
    """

    __abstract__ = True

    tenant_id = Column(
        Integer,
        nullable=False,
        index=True,
        comment="企业ID / Tenant ID"
    )

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(id={self.id}, tenant_id={self.tenant_id})>"


# 导出 / Exports
__all__ = ["Base", "BaseModel", "TenantModel", "utc_now"]
