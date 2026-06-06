"""
企业模型 / Tenant Model

多企业 SaaS 的企业实体
Multi-tenant SaaS tenant entity.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.core.base_model import BaseModel
from app.core.deletion import DeletionDep, DeletionStrategy


class Tenant(BaseModel):
    """
    企业模型 / Tenant model.

    - 每个企业是一个独立的商户/组织
    - 企业数据完全隔离
    """

    __tablename__ = "tenants"

    __delete_deps__ = [
        DeletionDep(
            "TenantAdmin",
            "tenant_id",
            DeletionStrategy.CASCADE_SOFT,
            label_field="username",
            i18n_key="tenant_admin",
        ),
        DeletionDep(
            "TenantUser",
            "tenant_id",
            DeletionStrategy.CASCADE_SOFT,
            label_field="username",
            i18n_key="tenant_user",
        ),
        DeletionDep(
            "TenantDomain",
            "tenant_id",
            DeletionStrategy.CASCADE_SOFT,
            label_field="domain",
            i18n_key="tenant_domain",
        ),
        DeletionDep(
            "SystemAgentAssignment",
            "tenant_id",
            DeletionStrategy.CASCADE_DELETE,
            label_field="id",
            i18n_key="system_agent_assignment",
        ),
    ]

    # 允许前端筛选的字段 / Fields exposed for list filtering
    __filterable__ = {
        "id": "id",
        "name": "name",
        "code": "code",
        "contact_name": "contact_name",
        "contact_phone": "contact_phone",
        "contact_email": "contact_email",
        "is_active": "is_active",
        "plan_id": "plan_id",
        "expires_at": "expires_at",
        "created_at": "created_at",
        "updated_at": "updated_at",
    }

    __sortable__ = [
        "id",
        "name",
        "code",
        "is_active",
        "plan_id",
        "expires_at",
        "created_at",
        "updated_at",
    ]

    # 下拉选项配置 / Select dropdown config
    __selectable__ = {
        "label": "name",
        "value": "id",
        "search": ["name", "code"],
        "extra": ["code"],
    }

    # 基本信息 / Basic info
    name: Mapped[str] = mapped_column(
        String(100),
        index=True,
        comment="企业名称 / Tenant name",
    )
    code: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        comment="企业编码（唯一标识） / Tenant code",
    )

    # 联系信息 / Contact
    contact_name: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="联系人姓名 / Contact name",
    )
    contact_phone: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="联系人电话 / Contact phone",
    )
    contact_email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="联系人邮箱 / Contact email",
    )

    # 企业状态 / Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        comment="是否启用 / Active",
    )

    # 退役存储列：仅映射现有库表形态，应用写入会拒绝 /
    # Retired storage column: mapped for the existing table shape; app writes are rejected.
    plan: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        default=None,
        comment="退役套餐文本列 / Retired plan text column",
    )

    # 套餐外键关联 / FK to TenantPlan
    plan_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("tenant_plans.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="关联套餐ID / Plan id",
    )

    # 企业级配额覆盖（可覆盖套餐默认配额） / Tenant quota overrides
    quota: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="配额配置(可覆盖套餐默认值) / Quota JSON overrides",
    )

    # 有效期 / Expiry
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="到期时间 / Expires at",
    )

    # 备注 / Remark
    remark: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="备注 / Remark",
    )

    # 退役存储列：配置读取统一走 ConfigService /
    # Retired storage column: config reads go through ConfigService.
    settings: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="退役企业设置列 / Retired tenant settings column",
    )

    # ==================== 关系 ==================== / Relationships

    # 关联套餐 / Linked plan
    tenant_plan: Mapped["TenantPlan | None"] = relationship(
        "TenantPlan",
        back_populates="tenants",
        lazy="selectin",
    )

    # 企业绑定的域名列表 / Bound domains
    domains = relationship(
        "TenantDomain",
        back_populates="tenant",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    # ==================== 辅助属性 ==================== / Helpers

    @property
    def subdomain(self) -> str:
        """获取企业子域名 / Get tenant subdomain."""
        return self.code

    @property
    def has_active_plan(self) -> bool:
        """Whether this active tenant is linked to an active plan."""
        plan = self.tenant_plan
        return (
            bool(self.is_active)
            and not bool(self.is_deleted)
            and self.plan_id is not None
            and plan is not None
            and bool(getattr(plan, "is_active", False))
        )

    @validates("plan", "settings")
    def _reject_retired_storage_write(self, key: str, value: Any) -> Any:
        """中文: 退役列只允许清空，新写入必须走 plan_id 或 ConfigService。

        EN: Retired columns may only be cleared; new writes must use plan_id or
        ConfigService.
        """
        if value is None:
            return None
        raise ValueError(f"tenants.{key} is retired; use plan_id or ConfigService")

    @property
    def max_custom_domains(self) -> int:
        """获取最大自定义域名数量（由套餐决定） / Max custom domains (from plan quota)."""
        if not self.has_active_plan:
            return 0
        # 优先从企业级 quota 获取，其次从套餐获取 /
        # Prefer tenant quota, then plan defaults
        if self.quota and "max_custom_domains" in self.quota:
            return self.quota.get("max_custom_domains", 0)
        if self.tenant_plan:
            return self.tenant_plan.get_quota_value("max_custom_domains", 0)
        return 0

    def get_quota_value(self, key: str, default: int | bool | None = None):
        """
        获取配额值（优先企业级覆盖，其次套餐默认值）/ Get quota value (tenant override first, then plan default).

        Args:
            key: 配额键名
            default: 默认值

        Returns:
            配额值
        """
        if not self.has_active_plan:
            return default
        # 优先从企业级 quota 获取 / Prefer tenant-level quota
        if self.quota and key in self.quota:
            return self.quota.get(key, default)
        # 其次从套餐获取 / Else plan defaults
        if self.tenant_plan:
            return self.tenant_plan.get_quota_value(key, default)
        return default

    def __repr__(self) -> str:
        return f"<Tenant(id={self.id}, code={self.code}, name={self.name})>"


if TYPE_CHECKING:
    from app.models.tenant.tenant_plan import TenantPlan


__all__ = ["Tenant"]
