"""
通知偏好设置模型

用户可自定义各类通知的接收渠道（WS 推送 / 邮件 / 收件箱）。
"""

from sqlalchemy import Boolean, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel


class NotificationPreference(BaseModel):
    """
    通知偏好设置

    - user_type + user_id + category 唯一
    - 每个组合控制该用户对该类通知的三个渠道开关
    """

    __tablename__ = "notification_preferences"

    __table_args__ = (
        UniqueConstraint("user_type", "user_id", "category", name="uq_notification_pref"),
    )

    user_type: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="用户类型: admin/tenant_admin/tenant_user",
    )
    user_id: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="用户 ID",
    )
    category: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="通知分类: system/ai/task/biz/audit",
    )
    channel_ws: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, comment="是否接收 WS 实时推送",
    )
    channel_email: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, comment="是否接收邮件通知",
    )
    channel_inbox: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, comment="是否写入收件箱",
    )

    def __repr__(self) -> str:
        return f"<NotificationPreference(user={self.user_type}:{self.user_id}, category={self.category})>"


__all__ = ["NotificationPreference"]
