"""
通知偏好设置模型 / Notification Preference Model

用户可自定义各类通知的接收渠道（WS 推送 / 邮件 / 收件箱）。
支持全局默认 -> 个人覆盖的分层继承。
Users can customize notification channels (WS push / email / inbox) per notification type.
Supports global default -> individual override layered inheritance.
"""

from sqlalchemy import Boolean, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel


class NotificationPreference(BaseModel):
    """
    通知偏好设置 / Notification Preference

    四种 user_type / Four user_type values:
    - platform_global: 管理端全局默认 / Admin-side global default (tenant_id=0, user_id=NULL)
    - tenant_global:   租户端全局默认 / Tenant-side global default (tenant_id=N, user_id=NULL)
    - admin:           管理端管理员个人 / Admin individual (tenant_id=0, user_id=N)
    - tenant_admin:    租户端管理员个人 / Tenant admin individual (tenant_id=N, user_id=N)
    """

    __tablename__ = "notification_preferences"

    __table_args__ = (
        UniqueConstraint(
            "user_type",
            "tenant_id",
            "user_id",
            "category",
            name="uq_notification_pref_v2",
        ),
    )

    user_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="用户类型 / User type: platform_global/tenant_global/admin/tenant_admin",
    )
    tenant_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="租户 ID（0 = 平台级） / Tenant ID (0 = platform level)",
    )
    user_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        default=None,
        comment="用户 ID（NULL = 全局记录） / User ID (NULL = global record)",
    )
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="通知分类 / Notification category: system/ai/task/biz/audit",
    )
    channel_ws: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="是否接收 WS 实时推送 / Whether to receive WS push",
    )
    channel_email: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="是否接收邮件通知 / Whether to receive email notifications",
    )
    channel_inbox: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="是否写入收件箱 / Whether to write to inbox",
    )

    def __repr__(self) -> str:
        return (
            f"<NotificationPreference(type={self.user_type}, tenant={self.tenant_id}, "
            f"user={self.user_id}, category={self.category})>"
        )


__all__ = ["NotificationPreference"]
