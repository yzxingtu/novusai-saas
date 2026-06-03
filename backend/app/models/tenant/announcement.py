"""
公告管理模型 / Announcement Management Model
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import TenantModel

if TYPE_CHECKING:
    from app.models.tenant.announcement_delivery import AnnouncementDelivery
    from app.models.tenant.announcement_response import AnnouncementResponse


class Announcement(TenantModel):
    """
    公告管理模型 / Announcement Management model.
    """

    __tablename__ = "announcements"
    __table_args__ = (
        Index("idx_announcements_scope_status", "scope", "status"),
        Index("idx_announcements_tenant_scope", "tenant_id", "scope"),
    )

    # 可过滤字段 / Filterable fields
    __filterable__ = {
        "title": "title",
        "scope": "scope",
        "status": "status",
        "priority": "priority",
        "require_response": "require_response",
        "published_at": "published_at",
        "tenant_id": "tenant_id",
    }

    # 可排序字段 / Sortable fields
    __sortable_fields__ = {
        "id": "id",
        "created_at": "created_at",
        "updated_at": "updated_at",
        "title": "title",
        "scope": "scope",
        "status": "status",
        "priority": "priority",
        "published_at": "published_at",
        "recipient_count": "recipient_count",
        "response_count": "response_count",
        "sort_order": "sort_order",
        "tenant_id": "tenant_id",
    }

    __selectable__ = {
        "label": "title",
        "value": "id",
        "search": ["title"],
    }

    # ==================== 字段定义 / Field definitions ====================

    title: Mapped[str] = mapped_column(String(200), nullable=False, comment="公告标题")

    scope: Mapped[str] = mapped_column(
        String(20), nullable=False, default="tenant", comment="公告端别: admin/tenant"
    )

    content: Mapped[str | None] = mapped_column(Text, nullable=True, comment="公告内容")

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="公告状态", default="draft"
    )

    priority: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="公告优先级", default="normal"
    )

    require_response: Mapped[bool] = mapped_column(
        Boolean, nullable=False, comment="是否需要反馈", default=False
    )

    form_schema: Mapped[list[dict] | None] = mapped_column(
        JSONB, nullable=True, comment="表单配置"
    )

    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="发布时间"
    )

    recipient_count: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="接收人数", default=0
    )

    response_count: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="回执人数", default=0
    )

    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="排序", default=0
    )

    # ==================== 关系定义 / Relationships ====================

    deliveries: Mapped[list[AnnouncementDelivery]] = relationship(
        "AnnouncementDelivery",
        back_populates="announcement",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    responses: Mapped[list[AnnouncementResponse]] = relationship(
        "AnnouncementResponse",
        back_populates="announcement",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


__all__ = ["Announcement"]
