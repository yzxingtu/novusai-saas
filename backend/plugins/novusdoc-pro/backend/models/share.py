"""
NovusDoc Pro 分享链接模型

表名: px_novusdoc_pro_shares
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import TenantModel


class NovusdocProShare(TenantModel):
    """分享链接"""

    __tablename__ = "px_novusdoc_pro_shares"

    __filterable__ = {
        "id": "id",
        "tenant_id": "tenant_id",
        "document_id": "document_id",
        "created_at": "created_at",
    }

    document_id: Mapped[int] = mapped_column(
        Integer, nullable=False, index=True, comment="文档 ID",
    )
    token: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True, comment="分享令牌",
    )
    permission: Mapped[str] = mapped_column(
        String(20), nullable=False, default="viewer",
        comment="权限: viewer / editor",
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="过期时间",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="是否有效",
    )
    creator_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="创建者 ID",
    )
