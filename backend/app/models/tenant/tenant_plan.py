"""
企业套餐模型 / Tenant Plan Model

定义企业订阅套餐，控制企业可用的功能模块和配额
Defines tenant subscription plans, controls available features and quotas.
"""

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import Base, BaseModel
from app.core.deletion import DeletionDep, DeletionStrategy

# 套餐-权限关联表（多对多）
tenant_plan_permissions = Table(
    "tenant_plan_permissions",
    Base.metadata,
    Column("plan_id", Integer, ForeignKey("tenant_plans.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", Integer, ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)


class TenantPlan(BaseModel):
    """
    企业套餐模型

    - 定义不同等级的订阅套餐
    - 控制企业可用的功能模块（通过关联权限）
    - 设置资源配额（存储、用户数、域名数等）
    """

    __tablename__ = "tenant_plans"

    __delete_deps__ = [
        DeletionDep("Tenant", "plan_id", DeletionStrategy.BLOCK,
                    label_field="name", i18n_key="tenant"),
    ]

    # 允许前端筛选的字段
    __filterable__ = {
        "id": "id",
        "code": "code",
        "name": "name",
        "billing_cycle": "billing_cycle",
        "is_active": "is_active",
        "sort_order": "sort_order",
        "created_at": "created_at",
        "updated_at": "updated_at",
    }

    # 允许排序的字段（用于前端排序）
    __sortable_fields__ = {
        "id": "id",
        "code": "code",
        "name": "name",
        "price": "price",
        "billing_cycle": "billing_cycle",
        "sort_order": "sort_order",
        "created_at": "created_at",
    }

    # 排序配置（用于自动计算 sort_order）
    __sortable__ = {
        "field": "sort_order",      # 排序字段名
        "step": 1000,               # 排序步长
        "scope_fields": [],         # 全局排序（套餐无作用域）
    }

    # 下拉选项配置
    __selectable__ = {
        "label": "name",
        "value": "id",
        "search": ["name", "code"],
        "extra": ["code", "billing_cycle"],
    }

    # ==================== 基本信息 ====================

    # 套餐代码（唯一标识）
    code: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, comment="套餐代码（如 free/pro/enterprise）"
    )

    # 套餐名称
    name: Mapped[str] = mapped_column(
        String(100), comment="套餐名称"
    )

    # 套餐描述
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="套餐描述"
    )

    # ==================== 计费信息 ====================

    # 价格（支持小数）
    price: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True, comment="价格"
    )

    # 计费周期
    billing_cycle: Mapped[str] = mapped_column(
        String(20), default="monthly", index=True, comment="计费周期: monthly/yearly/lifetime/custom"
    )

    # ==================== 状态与排序 ====================

    # 是否启用
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, index=True, comment="是否启用"
    )

    # 排序顺序
    sort_order: Mapped[int] = mapped_column(
        Integer, default=0, comment="排序顺序"
    )

    # ==================== 配额与特性 ====================

    # 配额配置（JSON）
    # 结构示例：
    # {
    #     "storage_limit_gb": 10,
    #     "max_users": 50,
    #     "max_admins": 5,
    #     "max_custom_domains": 3,
    #     "allow_custom_domain": true,
    #     "api_calls_per_month": 100000,
    #     "max_file_size_mb": 100
    # }
    quota: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="配额配置"
    )

    # 特性标记（JSON，可选）
    # 用于存储额外的特性开关
    # 结构示例：
    # {
    #     "ai_enabled": true,
    #     "advanced_analytics": false,
    #     "white_label": false
    # }
    features: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="特性标记"
    )

    # ==================== 关联关系 ====================

    # 关联权限（多对多）- 套餐允许的功能模块
    permissions: Mapped[list["Permission"]] = relationship(
        "Permission",
        secondary=tenant_plan_permissions,
        lazy="selectin",
    )

    # 使用该套餐的企业（一对多）
    # lazy="noload": 不自动加载，避免列表查询时加载全部企业对象
    # 需要时通过 get_with_tenants() 显式加载
    tenants: Mapped[list["Tenant"]] = relationship(
        "Tenant",
        back_populates="tenant_plan",
        lazy="noload",
    )

    # ==================== 辅助属性 ====================

    @property
    def permissions_count(self) -> int:
        """获取权限数量"""
        return len(self.permissions)

    # 企业数量缓存（由查询端注入，避免加载全部企业对象）
    # 注意：不使用类型注解，避免 SQLAlchemy MappedAnnotationError
    _tenants_count_cache = None

    @property
    def tenants_count(self) -> int:
        """获取使用该套餐的企业数量"""
        if self._tenants_count_cache is not None:
            return self._tenants_count_cache
        # 如果 tenants 已显式加载（如 get_with_tenants），用列表计数
        try:
            return len([t for t in self.tenants if not t.is_deleted])
        except Exception:
            return 0

    @tenants_count.setter
    def tenants_count(self, value: int) -> None:
        """设置企业数量缓存"""
        self._tenants_count_cache = value

    @property
    def has_tenants(self) -> bool:
        """是否有企业使用该套餐"""
        return self.tenants_count > 0

    def get_quota_value(self, key: str, default: int | bool | None = None):
        """
        获取配额值

        Args:
            key: 配额键名
            default: 默认值

        Returns:
            配额值
        """
        if self.quota is None:
            return default
        return self.quota.get(key, default)

    def get_feature(self, key: str, default: bool = False) -> bool:
        """
        获取特性开关

        Args:
            key: 特性键名
            default: 默认值

        Returns:
            特性是否启用
        """
        if self.features is None:
            return default
        return self.features.get(key, default)

    def __repr__(self) -> str:
        return f"<TenantPlan(id={self.id}, code={self.code}, name={self.name})>"

if TYPE_CHECKING:
    from app.models.auth.permission import Permission
    from app.models.tenant.tenant import Tenant


__all__ = ["TenantPlan", "tenant_plan_permissions"]
