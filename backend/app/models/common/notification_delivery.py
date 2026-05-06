"""
通知投递记录模型 / Notification Delivery Model

按渠道记录通知投递状态，作为 WS、收件箱、邮件、Webhook 的 durable outbox/audit trail。
Records per-channel notification delivery state as a durable outbox/audit trail.
"""

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel


class NotificationDelivery(BaseModel):
    """通知投递记录 / Notification delivery record."""

    __tablename__ = "notification_deliveries"

    __table_args__ = (
        Index("idx_notification_deliveries_notification", "notification_id"),
        Index("idx_notification_deliveries_template_id", "template_id"),
        Index("idx_notification_deliveries_template", "template_code", "channel"),
        Index(
            "idx_notification_deliveries_recipient",
            "recipient_type",
            "recipient_id",
            "tenant_id",
        ),
        Index("idx_notification_deliveries_status", "status", "created_at"),
        Index("idx_notification_deliveries_task_id", "task_id"),
    )

    __filterable__ = {
        "id": "id",
        "notification_id": "notification_id",
        "template_id": "template_id",
        "template_code": "template_code",
        "channel": "channel",
        "recipient_type": "recipient_type",
        "recipient_id": "recipient_id",
        "tenant_id": "tenant_id",
        "status": "status",
        "task_id": "task_id",
        "created_at": "created_at",
    }

    __sortable__ = {"id", "created_at", "updated_at", "delivered_at", "status"}

    notification_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="收件箱通知 ID（非 inbox 渠道可为空）",
    )
    template_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="通知模板 ID",
    )
    template_code: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="通知模板编码",
    )
    channel: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="投递渠道: ws/inbox/email/webhook",
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
    tenant_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="企业 ID（NULL=平台级）",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        comment="状态: pending/queued/sent/failed/skipped",
    )
    attempt: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="投递尝试次数",
    )
    task_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="异步任务 ID",
    )
    last_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="最近错误信息",
    )
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        comment="投递完成时间",
    )

    def __repr__(self) -> str:
        return (
            f"<NotificationDelivery(id={self.id}, template={self.template_code}, "
            f"channel={self.channel}, status={self.status})>"
        )


__all__ = ["NotificationDelivery"]
