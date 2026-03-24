"""
企业 AI 配额配置模型 / Tenant AI Quota Model

存储企业的 Token 配额、预算和超额策略
Stores tenant token quota, budget and overage policy.
"""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import TenantModel
from app.core.i18n import _
from app.enums.ai import QuotaPeriodEnum, QuotaTypeEnum


class TenantQuota(TenantModel):
    """
    企业 AI 配额配置 / Tenant AI quota config.

    为每个企业配置 Token 使用配额和超额策略
    支持按模型配置，也支持全局配置（model_id 为 NULL）
    """

    __tablename__ = "tenant_quotas"

    __ai_policy__ = {
        "label": "企业配额",
        "keywords": ["配额", "quota"],
        "allow_read": True,
    }

    # 允许前端筛选的字段 / Fields exposed for list filtering
    __filterable__ = {
        "id": "id",
        "tenant_id": "tenant_id",
        "model_id": "model_id",
        "period": "period",
        "quota_type": "quota_type",
        "is_active": "is_active",
        "created_at": "created_at",
    }

    # 允许排序的字段 / Sortable columns for UI
    __sortable__ = {
        "id": "id",
        "limit": "limit",
        "created_at": "created_at",
    }

    # 外键：关联的 AI 模型（NULL 表示全局配额）
    model_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("ai_models.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment=_("enum.tenant_quota.model_id")
    )

    # 配额周期：daily/monthly
    period: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=QuotaPeriodEnum.MONTHLY.value,
        index=True,
        comment=_("enum.tenant_quota.period")
    )

    # 配额限制（Token 数量）
    limit: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment=_("enum.tenant_quota.limit")
    )

    # 配额类型：soft（软限制，允许超额）或 hard（硬限制，直接拒绝）
    quota_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=QuotaTypeEnum.SOFT.value,
        index=True,
        comment=_("enum.tenant_quota.quota_type")
    )

    # 预警阈值（百分比，如 80 表示 80%） / Warning threshold (percent; e.g. 80 = 80%)
    warning_threshold: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        default=80,
        comment=_("enum.tenant_quota.warning_threshold")
    )

    # 是否启用 / Enabled flag
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        index=True,
        comment=_("enum.tenant_quota.is_active")
    )

    # 备注说明 / Notes
    description: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment=_("enum.tenant_quota.description")
    )

    # ==================== 关系 ==================== / Relationships

    # 关联的 AI 模型
    model = relationship(
        "AIModel",
        lazy="selectin",
    )

    # 关联的企业 / Linked tenant
    tenant = relationship(
        "Tenant",
        lazy="selectin",
        primaryjoin="TenantQuota.tenant_id == Tenant.id",
        foreign_keys="[TenantQuota.tenant_id]",
        viewonly=True,
    )

    def __repr__(self) -> str:
        return f"<TenantQuota(id={self.id}, tenant_id={self.tenant_id}, model_id={self.model_id}, period={self.period})>"


if TYPE_CHECKING:
    pass


__all__ = ["TenantQuota"]
