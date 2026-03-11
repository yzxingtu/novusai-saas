"""
通知模型 / Notification Model

存储所有持久化通知（收件箱），支持已读/未读、分类筛选、过期清理。
Stores all persistent notifications (inbox), supports read/unread, category filtering, expiry cleanup.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel


class Notification(BaseModel):
    """
    通知收件箱

    - tenant_id: NULL=平台级通知，有值=租户级通知
    - recipient_type: admin / tenant_admin / tenant_user
    - recipient_id: 接收人 ID
    - template_code: 关联通知模板编码
    - category: 分类（冗余，方便筛选）
    - title / body: 渲染后的标题和正文
    - data: 业务关联数据（JSON）
    - link: 点击跳转链接
    - priority: 优先级
    - is_read / read_at: 已读状态
    - expired_at: 过期时间（可选）
    """

    __tablename__ = "notifications"

    __table_args__ = (
        Index("idx_notifications_recipient", "recipient_type", "recipient_id", "is_read"),
        Index("idx_notifications_tenant", "tenant_id", "created_at"),
    )

    tenant_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, index=True, comment="租户 ID（NULL=平台级）",
    )
    recipient_type: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="接收人类型: admin/tenant_admin/tenant_user",
    )
    recipient_id: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="接收人 ID",
    )
    template_code: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="通知模板编码",
    )
    category: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True, comment="分类: system/ai/task/biz/audit",
    )
    title: Mapped[str] = mapped_column(
        Text, nullable=False, comment="通知标题（已渲染）",
    )
    body: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="通知正文（已渲染）",
    )
    data: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="业务关联数据",
    )
    link: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="点击跳转链接",
    )
    priority: Mapped[str] = mapped_column(
        String(20), nullable=False, default="normal",
        comment="优先级: low/normal/high/urgent",
    )
    is_read: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, comment="是否已读",
    )
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="已读时间",
    )
    expired_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="过期时间",
    )

    def __repr__(self) -> str:
        return f"<Notification(id={self.id}, recipient={self.recipient_type}:{self.recipient_id}, category={self.category})>"


__all__ = ["Notification"]
