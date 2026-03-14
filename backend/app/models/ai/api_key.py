"""
AI 供应商 API Key 模型 / AI Provider API Key Model

存储 AI 供应商的 API Key，支持平台级和企业级 Key
Stores AI provider API keys, supports platform-level and tenant-level keys.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import BaseModel, utc_now
from app.core.i18n import _
from app.core.security import decrypt_data, encrypt_data
from app.enums.common import ResourceScopeEnum


class ProviderApiKey(BaseModel):
    """
    AI 供应商 API Key 模型

    存储平台级或企业级的 API Key，支持加密存储
    - admin_only + tenant_id=None：仅管理端 AI 调用可用 / Admin-only key
    - all_tenants + tenant_id=None：平台级 Key，所有企业共享 / Platform-wide key
    - all_tenants + tenant_id=X：企业 X 专用 Key / Tenant-specific key
    """

    __tablename__ = "ai_api_keys"

    # 允许前端筛选的字段
    __filterable__ = {
        "id": "id",
        "provider_id": "provider_id",
        "tenant_id": "tenant_id",
        "scope": "scope",
        "name": "name",
        "is_active": "is_active",
        "created_at": "created_at",
    }

    # 允许排序的字段（用于前端排序）
    __sortable__ = {
        "id": "id",
        "name": "name",
        "scope": "scope",
        "created_at": "created_at",
        "usage_count": "usage_count",
        "last_used_at": "last_used_at",
        "is_active": "is_active",
    }

    # 作用域 / Scope (admin_only / all_tenants)
    scope: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ResourceScopeEnum.ALL_TENANTS.value,
        index=True,
        comment=_("enum.ai_api_key.scope"),
    )

    # 外键：所属供应商
    provider_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("ai_providers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment=_("enum.ai_api_key.provider_id")
    )

    # 企业 ID（平台级 Key 为 NULL）
    tenant_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment=_("enum.ai_api_key.tenant_id")
    )

    # Key 名称（便于识别）
    name: Mapped[str] = mapped_column(
        String(100),
        comment=_("enum.ai_api_key.name")
    )

    # 加密存储的 API Key
    encrypted_key: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment=_("enum.ai_api_key.encrypted_key")
    )

    # 是否启用
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        index=True,
        comment=_("enum.ai_api_key.is_active")
    )

    # 使用限制（可选，NULL 表示无限制）
    usage_limit: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment=_("enum.ai_api_key.usage_limit")
    )

    # 已使用次数
    usage_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment=_("enum.ai_api_key.usage_count")
    )

    # 最后使用时间
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment=_("enum.ai_api_key.last_used_at")
    )

    # 过期时间（可选）
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment=_("enum.ai_api_key.expires_at")
    )

    # ==================== 关系 ====================

    # 所属供应商
    provider = relationship(
        "AIProvider",
        back_populates="api_keys",
        lazy="selectin",
    )

    # ==================== 方法 ====================

    def encrypt_key(self, plain_key: str) -> None:
        """
        加密并设置 API Key

        Args:
            plain_key: 明文 API Key
        """
        self.encrypted_key = encrypt_data(plain_key)

    def decrypt_key(self) -> str:
        """
        解密 API Key

        Returns:
            明文 API Key
        """
        return decrypt_data(self.encrypted_key)

    def increment_usage(self) -> None:
        """增加使用次数"""
        self.usage_count += 1
        self.last_used_at = utc_now()

    def is_expired(self) -> bool:
        """
        检查是否过期

        Returns:
            是否过期
        """
        if self.expires_at is None:
            return False
        return utc_now() > self.expires_at

    def is_usage_limit_reached(self) -> bool:
        """
        检查是否达到使用限制

        Returns:
            是否达到限制
        """
        if self.usage_limit is None:
            return False
        return self.usage_count >= self.usage_limit

    def is_available(self) -> bool:
        """
        检查 Key 是否可用

        Returns:
            是否可用
        """
        return (
            self.is_active and
            not self.is_deleted and
            not self.is_expired() and
            not self.is_usage_limit_reached()
        )

    def __repr__(self) -> str:
        return f"<ProviderApiKey(id={self.id}, name={self.name}, scope={self.scope}, tenant_id={self.tenant_id})>"


if TYPE_CHECKING:
    pass


__all__ = ["ProviderApiKey"]
