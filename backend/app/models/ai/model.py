"""
AI 模型模型 / AI Model Model

定义 AI 供应商提供的具体模型信息
Defines specific model information provided by AI providers.
"""

from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import BaseModel
from app.core.deletion import DeletionDep, DeletionStrategy
from app.core.i18n import _
from app.enums.ai import ModelTypeEnum


class AIModel(BaseModel):
    """
    AI 模型模型

    存储 AI 供应商提供的具体模型信息，如 GPT-4、Claude-3 等
    """

    __tablename__ = "ai_models"

    __delete_deps__ = [
        DeletionDep("Agent", "model_id", DeletionStrategy.BLOCK,
                    label_field="name", i18n_key="agent"),
        DeletionDep("KnowledgeBase", "embedding_model_id", DeletionStrategy.BLOCK,
                    label_field="name", i18n_key="knowledge_base"),
        DeletionDep("TenantQuota", "model_id", DeletionStrategy.CASCADE_SOFT,
                    label_field="id", i18n_key="tenant_quota"),
        DeletionDep("TenantModelRateLimit", "model_id", DeletionStrategy.CASCADE_SOFT,
                    label_field="id", i18n_key="tenant_rate_limit"),
        DeletionDep("AIModel", "fallback_model_id", DeletionStrategy.NULLIFY,
                    label_field="name", i18n_key="ai_model"),
        DeletionDep("KnowledgeBase", "vision_model_id", DeletionStrategy.NULLIFY,
                    label_field="name", i18n_key="knowledge_base_vision"),
    ]

    # 允许前端筛选的字段
    __filterable__ = {
        "id": "id",
        "provider_id": "provider_id",
        "name": "name",
        "code": "code",
        "type": "type",
        "tier": "tier",
        "is_active": "is_active",
        "supports_vision": "supports_vision",
        "supports_function_calling": "supports_function_calling",
        "supports_streaming": "supports_streaming",
        "created_at": "created_at",
    }

    # 允许排序的字段
    __sortable__ = {
        "id": "id",
        "name": "name",
        "input_price_per_1k": "input_price_per_1k",
        "output_price_per_1k": "output_price_per_1k",
        "created_at": "created_at",
    }

    # 外键：所属供应商
    provider_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("ai_providers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment=_("enum.ai_model.provider_id")
    )

    # 基本信息
    name: Mapped[str] = mapped_column(
        String(100),
        index=True,
        comment=_("enum.ai_model.name")
    )
    code: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        comment=_("enum.ai_model.code")
    )

    # 模型类型
    type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=ModelTypeEnum.CHAT.value,
        comment=_("enum.ai_model.type")
    )

    # 上下文窗口大小（tokens）
    context_window: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment=_("enum.ai_model.context_window")
    )

    # 最大输出 tokens
    max_output_tokens: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment=_("enum.ai_model.max_output_tokens")
    )

    # 价格信息（每 1k tokens，单位：美元）
    input_price_per_1k: Mapped[float | None] = mapped_column(
        Numeric(10, 6),
        nullable=True,
        comment=_("enum.ai_model.input_price_per_1k")
    )
    output_price_per_1k: Mapped[float | None] = mapped_column(
        Numeric(10, 6),
        nullable=True,
        comment=_("enum.ai_model.output_price_per_1k")
    )

    # 速率限制 (每分钟请求数/Token 数)
    rpm_limit: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment=_("enum.ai_model.rpm_limit")
    )
    tpm_limit: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment=_("enum.ai_model.tpm_limit")
    )

    # 能力标记
    supports_function_calling: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment=_("enum.ai_model.supports_function_calling")
    )
    supports_vision: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment=_("enum.ai_model.supports_vision")
    )
    supports_streaming: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        comment=_("enum.ai_model.supports_streaming")
    )

    # 图片限制（仅 supports_vision=True 时有效）
    max_image_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        default=5,
        comment=_("enum.ai_model.max_image_count")
    )
    max_image_size_mb: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        default=10,
        comment=_("enum.ai_model.max_image_size_mb")
    )

    # 是否启用
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        index=True,
        comment=_("enum.ai_model.is_active")
    )

    # 模型特定配置（JSON 格式）
    # 例如：默认参数、特殊能力标记等
    config: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment=_("enum.ai_model.config")
    )

    # 模型级别（用于多模型路由策略）
    tier: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        index=True,
        comment=_("enum.ai_model.tier"),
    )

    # 备用模型（故障转移链）
    fallback_model_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("ai_models.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment=_("enum.ai_model.fallback_model_id")
    )

    # ==================== 关系 ====================

    # 所属供应商
    provider = relationship(
        "AIProvider",
        back_populates="models",
        lazy="selectin",
    )

    # 备用模型关系
    fallback_model = relationship(
        "AIModel",
        remote_side="AIModel.id",
        foreign_keys=[fallback_model_id],
        lazy="selectin",
    )

    @property
    def provider_name(self) -> str | None:
        return self.provider.name if self.provider else None

    @property
    def fallback_model_name(self) -> str | None:
        return self.fallback_model.name if self.fallback_model else None

    def __repr__(self) -> str:
        return f"<AIModel(id={self.id}, code={self.code}, name={self.name})>"


if TYPE_CHECKING:
    pass


__all__ = ["AIModel"]
