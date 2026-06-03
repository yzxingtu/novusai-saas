"""
公告回执模型 / Announcement response model.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import TenantModel, utc_now

if TYPE_CHECKING:
    from app.models.tenant.announcement import Announcement
    from app.models.tenant.announcement_delivery import AnnouncementDelivery


class AnnouncementResponse(TenantModel):
    """公告反馈答案 / Announcement feedback answers."""

    __tablename__ = "announcement_responses"
    __table_args__ = (
        UniqueConstraint(
            "announcement_id",
            "recipient_type",
            "recipient_id",
            name="uq_announcement_response_recipient",
        ),
        UniqueConstraint(
            "delivery_id",
            name="uq_announcement_response_delivery",
        ),
        Index("idx_announcement_responses_announcement", "announcement_id"),
    )

    __filterable__ = {
        "announcement_id": "announcement_id",
        "recipient_type": "recipient_type",
        "recipient_id": "recipient_id",
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
    delivery_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("announcement_deliveries.id", ondelete="CASCADE"),
        nullable=False,
        comment="投递 ID",
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
    answers: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="反馈答案",
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=utc_now,
        comment="提交时间",
    )

    announcement: Mapped[Announcement] = relationship(
        "Announcement",
        back_populates="responses",
        lazy="selectin",
    )
    delivery: Mapped[AnnouncementDelivery] = relationship(
        "AnnouncementDelivery",
        back_populates="response",
        lazy="selectin",
    )


__all__ = ["AnnouncementResponse"]
