"""
AI 供应商模型

定义 AI 供应商的信息和配置
"""

from sqlalchemy import Boolean, Column, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING

from app.core.base_model import BaseModel
from app.core.deletion import DeletionDep, DeletionStrategy
from app.core.i18n import _
from app.enums.ai import ProviderTypeEnum


class AIProvider(BaseModel):
    """
    AI 供应商模型
    
    存储 AI 服务供应商的配置信息，如 OpenAI、国产大模型等
    """
    
    __tablename__ = "ai_providers"

    __delete_deps__ = [
        DeletionDep("AIModel", "provider_id", DeletionStrategy.BLOCK,
                    label_field="name", i18n_key="ai_model"),
        DeletionDep("ProviderApiKey", "provider_id", DeletionStrategy.CASCADE_SOFT,
                    label_field="id", i18n_key="provider_api_key"),
    ]
    
    # 允许前端筛选的字段
    __filterable__ = {
        "id": "id",
        "name": "name",
        "code": "code",
        "type": "type",
        "is_active": "is_active",
        "created_at": "created_at",
    }
    
    # 允许排序的字段（用于前端排序）
    __sortable__ = {
        "id": "id",
        "name": "name",
        "code": "code",
        "type": "type",
        "sort_order": "sort_order",
        "created_at": "created_at",
    }
    
    # 基本信息
    name: Mapped[str] = mapped_column(
        String(100),
        index=True,
        comment=_("enum.ai_provider.name")
    )
    code: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        comment=_("enum.ai_provider.code")
    )
    
    # 供应商类型
    type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=ProviderTypeEnum.OPENAI_COMPATIBLE.value,
        comment=_("enum.ai_provider.type")
    )
    
    # API 基础地址
    base_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment=_("enum.ai_provider.base_url")
    )
    
    # 描述信息
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment=_("enum.ai_provider.description")
    )
    
    # 图标（URL 或 icon name）
    icon: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment=_("enum.ai_provider.icon")
    )
    
    # 是否启用
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        index=True,
        comment=_("enum.ai_provider.is_active")
    )
    
    # 排序
    sort_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment=_("enum.ai_provider.sort_order")
    )
    
    # 供应商特定配置（JSON 格式）
    # 例如：超时时间、重试次数、特殊请求头等
    config: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment=_("enum.ai_provider.config")
    )
    
    # ==================== 关系 ====================
    
    # 关联的模型列表
    # noload 避免与 AIModel.provider(selectin) 形成双向 selectin 死循环
    models = relationship(
        "AIModel",
        back_populates="provider",
        lazy="noload",
        cascade="all, delete-orphan",
    )
    
    # 关联的 API Key 列表
    # noload 避免与 ProviderApiKey.provider(selectin) 形成双向 selectin 死循环
    api_keys = relationship(
        "ProviderApiKey",
        back_populates="provider",
        lazy="noload",
        cascade="all, delete-orphan",
    )

    @property
    def model_count(self) -> int:
        """关联模型数量（从 models 关系计算，noload 时返回 0）"""
        from sqlalchemy.orm import attributes
        state = attributes.instance_state(self)
        # 仅在 models 已被显式加载时计算，避免触发懒加载
        if "models" in state.dict:
            return len(self.models) if self.models else 0
        return 0
    
    def __repr__(self) -> str:
        return f"<AIProvider(id={self.id}, code={self.code}, name={self.name})>"


if TYPE_CHECKING:
    from app.models.ai.model import AIModel
    from app.models.ai.api_key import ProviderApiKey


__all__ = ["AIProvider"]
