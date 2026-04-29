"""
公告投递模型 / Announcement delivery model.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import TenantModel

if TYPE_CHECKING:
    from app.models.tenant.announcement import Announcement
    from app.models.tenant.announcement_response import AnnouncementResponse


class AnnouncementDelivery(TenantModel):
    """公告接收人投递状态 / Announcement per-recipient delivery state."""

    __tablename__ = "announcement_deliveries"
    __table_args__ = (
        UniqueConstraint(
            "announcement_id",
            "recipient_type",
            "recipient_id",
            name="uq_announcement_delivery_recipient",
        ),
        Index(
            "idx_announcement_deliveries_recipient_status",
            "recipient_type",
            "recipient_id",
            "status",
        ),
        Index("idx_announcement_deliveries_announcement", "announcement_id"),
    )

    __filterable__ = {
        "announcement_id": "announcement_id",
        "recipient_type": "recipient_type",
        "recipient_id": "recipient_id",
        "status": "status",
        "tenant_id": "tenant_id",
    }

    __sortable_fields__ = {
        "id": "id",
        "created_at": "created_at",
        "submitted_at": "submitted_at",
        "tenant_id": "tenant_id",
    }

    announcement_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("announcements.id", ondelete="CASCADE"),
        nullable=False,
        comment="公告 ID",
    )
    recipient_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="接收人类型: admin/tenant_admin/tenant_user",
    )
    recipient_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="接收人 ID",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        comment="状态: pending/read/submitted",
    )
    notification_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="关联通知 ID",
    )
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        comment="已读时间",
    )
    form_schema_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="表单配置版本",
    )
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        comment="提交时间",
    )
    announcement: Mapped[Announcement] = relationship(
        "Announcement",
        back_populates="deliveries",
        lazy="selectin",
    )
    response: Mapped[AnnouncementResponse | None] = relationship(
        "AnnouncementResponse",
        back_populates="delivery",
        uselist=False,
        lazy="selectin",
    )


__all__ = ["AnnouncementDelivery"]
