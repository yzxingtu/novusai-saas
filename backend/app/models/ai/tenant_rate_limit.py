"""
企业 AI 模型速率限制配置模型 / Tenant AI Model Rate Limit Model

存储每个企业对每个模型的速率限制配置
Stores per-tenant per-model rate limit configuration.
"""

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import TenantModel
from app.core.i18n import _


class TenantModelRateLimit(TenantModel):
    """
    企业 AI 模型速率限制配置 / Tenant model rate limit config.

    为每个企业配置对每个 AI 模型的速率限制
    如果未配置，则使用模型的默认限制
    """

    __tablename__ = "tenant_model_rate_limits"

    # 允许前端筛选的字段 / Fields exposed for list filtering
    __filterable__ = {
        "id": "id",
        "tenant_id": "tenant_id",
        "model_id": "model_id",
        "is_active": "is_active",
        "created_at": "created_at",
    }

    # 允许排序的字段 / Sortable columns for UI
    __sortable__ = {
        "id": "id",
        "created_at": "created_at",
    }

    # 外键：关联的 AI 模型
    model_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("ai_models.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment=_("enum.tenant_rate_limit.model_id"),
    )

    # RPM 限制（每分钟请求数）
    # None 表示使用模型默认限制
    rpm_limit: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment=_("enum.tenant_rate_limit.rpm_limit")
    )

    # TPM 限制（每分钟 Token 数）
    # None 表示使用模型默认限制
    tpm_limit: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment=_("enum.tenant_rate_limit.tpm_limit")
    )

    # 是否启用 / Enabled flag
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, index=True, comment=_("enum.tenant_rate_limit.is_active")
    )

    # 备注说明 / Notes
    description: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment=_("enum.tenant_rate_limit.description")
    )

    # ==================== 关系 ==================== / Relationships

    # 关联的 AI 模型
    model = relationship(
        "AIModel",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<TenantModelRateLimit(id={self.id}, tenant_id={self.tenant_id}, model_id={self.model_id})>"


__all__ = ["TenantModelRateLimit"]
