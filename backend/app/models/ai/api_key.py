"""
AI 供应商 API Key 模型 / AI Provider API Key Model

存储 AI 供应商的 API Key，支持平台级和企业级 Key
Stores AI provider API keys, supports platform-level and tenant-level keys.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from app.core.base_model import BaseModel, utc_now
from app.core.i18n import _
from app.core.security import decrypt_data, encrypt_data
from app.enums.common import ResourceScopeEnum


class ProviderApiKey(BaseModel):
    """
    AI 供应商 API Key 模型 / AI provider API key model.

    存储平台级或企业级的 API Key，支持加密存储。
    归属与投放面由 ResourceScopeEnum + owner_tenant_id 表达（与迁移后列名一致）：
    - admin_only + owner_tenant_id=NULL：仅管理端可用 / Admin-only key
    - global_shared + owner_tenant_id=NULL：管理端 + 全部企业可用 / Platform shared
    - selected_tenants + owner_tenant_id=X：仅企业 X 可用（可有 RTA 行对齐）/ Tenant-scoped
    """

    __tablename__ = "ai_api_keys"

    # 允许前端筛选的字段 / Fields exposed for list filtering
    __filterable__ = {
        "id": "id",
        "provider_id": "provider_id",
        "tenant_id": "owner_tenant_id",
        "owner_tenant_id": "owner_tenant_id",
        "scope": "scope",
        "name": "name",
        "is_active": "is_active",
        "created_at": "created_at",
    }

    # 允许排序的字段（用于前端排序） / Sortable columns for UI
    __sortable__ = {
        "id": "id",
        "name": "name",
        "scope": "scope",
        "created_at": "created_at",
        "usage_count": "usage_count",
        "last_used_at": "last_used_at",
        "is_active": "is_active",
    }

    # 资源作用域 / Resource scope (ResourceScopeEnum, 5 values)
    scope: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=ResourceScopeEnum.GLOBAL_SHARED.value,
        index=True,
        comment=_("enum.ai_api_key.scope"),
    )

    # 外键：所属供应商 / FK to provider
    provider_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("ai_providers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment=_("enum.ai_api_key.provider_id"),
    )

    # 归属企业（平台级为 NULL）；API/筛选仍可使用 tenant_id 别名
    owner_tenant_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment=_("enum.ai_api_key.tenant_id"),
    )
    tenant_id = synonym("owner_tenant_id")

    # Key 名称（便于识别） / Display name for key
    name: Mapped[str] = mapped_column(String(100), comment=_("enum.ai_api_key.name"))

    # 加密存储的 API Key / Encrypted secret
    encrypted_key: Mapped[str] = mapped_column(
        String(500), nullable=False, comment=_("enum.ai_api_key.encrypted_key")
    )

    # 是否启用 / Active flag
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, index=True, comment=_("enum.ai_api_key.is_active")
    )

    # 使用限制（可选，NULL 表示无限制） / Usage cap (NULL = unlimited)
    usage_limit: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment=_("enum.ai_api_key.usage_limit")
    )

    # 已使用次数 / Usage counter
    usage_count: Mapped[int] = mapped_column(
        Integer, default=0, comment=_("enum.ai_api_key.usage_count")
    )

    # 最后使用时间 / Last used at
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment=_("enum.ai_api_key.last_used_at"),
    )

    # 过期时间（可选） / Expires at (optional)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment=_("enum.ai_api_key.expires_at")
    )

    # ==================== 关系 ==================== / Relationships

    # 所属供应商 / Provider row
    provider = relationship(
        "AIProvider",
        back_populates="api_keys",
        lazy="selectin",
    )

    # ==================== 方法 ==================== / Methods

    def encrypt_key(self, plain_key: str) -> None:
        """
        加密并设置 API Key / Encrypt and set API key.

        Args:
            plain_key: 明文 API Key
        """
        self.encrypted_key = encrypt_data(plain_key)

    def decrypt_key(self) -> str:
        """
        解密 API Key / Decrypt API key.

        Returns:
            明文 API Key
        """
        return decrypt_data(self.encrypted_key)

    def mark_last_used(self) -> None:
        """
        仅刷新最近使用时间（不增加 usage_count）。
        For cache hits etc. where no upstream provider call occurred.
        """
        self.last_used_at = utc_now()

    def increment_usage(self) -> None:
        """增加使用次数 / Increment usage count."""
        self.usage_count += 1
        self.last_used_at = utc_now()

    def is_expired(self) -> bool:
        """
        检查是否过期 / Check if expired.

        Returns:
            是否过期 / Whether expired.
        """
        if self.expires_at is None:
            return False
        return utc_now() > self.expires_at

    def is_usage_limit_reached(self) -> bool:
        """
        检查是否达到使用限制 / Check if usage limit reached.

        Returns:
            是否达到限制 / Whether limit reached.
        """
        if self.usage_limit is None:
            return False
        return self.usage_count >= self.usage_limit

    def is_available(self) -> bool:
        """
        检查 Key 是否可用 / Check if key is available.

        Returns:
            是否可用 / Whether available.
        """
        return (
            self.is_active
            and not self.is_deleted
            and not self.is_expired()
            and not self.is_usage_limit_reached()
        )

    def __repr__(self) -> str:
        return (
            f"<ProviderApiKey(id={self.id}, name={self.name}, scope={self.scope}, "
            f"owner_tenant_id={self.owner_tenant_id})>"
        )


if TYPE_CHECKING:
    pass


__all__ = ["ProviderApiKey"]
