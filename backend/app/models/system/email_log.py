"""
邮件发送日志模型 / Email Log Model

记录每封邮件的发送状态，用于审计追溯和问题排查
Records each email's sending status for audit tracing and troubleshooting.
"""

from datetime import datetime

from sqlalchemy import ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel


class EmailLog(BaseModel):
    """
    邮件发送日志模型 / Email log model.

    记录邮件的收件人、主题、触发来源、发送状态
    """

    __tablename__ = "email_logs"


    __filterable__ = {
        "id": "id",
        "to_address": "to_address",
        "subject": "subject",
        "status": "status",
        "triggered_by": "triggered_by",
        "tenant_id": "tenant_id",
        "created_at": "created_at",
    }

    __sortable__ = ["created_at", "subject", "status"]

    __table_args__ = (
        Index("ix_email_logs_status", "status"),
        Index("ix_email_logs_triggered_by", "triggered_by"),
        Index("ix_email_logs_tenant_id", "tenant_id"),
    )

    to_address: Mapped[str] = mapped_column(
        comment="收件人（逗号分隔）",
    )
    cc: Mapped[str | None] = mapped_column(
        default=None,
        comment="抄送（逗号分隔）",
    )
    bcc: Mapped[str | None] = mapped_column(
        default=None,
        comment="密送（逗号分隔）",
    )
    subject: Mapped[str] = mapped_column(
        comment="邮件主题",
    )
    status: Mapped[str] = mapped_column(
        default="pending",
        comment="发送状态（pending/sent/failed）",
    )
    triggered_by: Mapped[str] = mapped_column(
        default="manual",
        comment="触发来源（manual/task_failure/password_reset/test/welcome/ssl_expiry）",
    )
    html_body: Mapped[str | None] = mapped_column(
        Text,
        default=None,
        comment="HTML 正文内容",
    )
    text_body: Mapped[str | None] = mapped_column(
        Text,
        default=None,
        comment="纯文本正文内容",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        default=None,
        comment="错误信息",
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        default=None,
        comment="实际发送时间",
    )
    tenant_id: Mapped[int | None] = mapped_column(
        ForeignKey("tenants.id", ondelete="SET NULL"),
        default=None,
        comment="关联企业ID（可选）",
    )
