"""
邮件日志 Schema / Email Log Schema

定义邮件日志 API 的响应数据结构
Defines email log API response data structures.
"""

from datetime import datetime

from pydantic import Field

from app.core.base_schema import BaseSchema


class EmailLogResponse(BaseSchema):
    """邮件日志响应 / Email log response schema."""

    id: int = Field(..., description="ID")
    to_address: str = Field(..., description="收件人")
    cc: str | None = Field(None, description="抄送")
    bcc: str | None = Field(None, description="密送")
    subject: str = Field(..., description="主题")
    status: str = Field(..., description="状态")
    triggered_by: str = Field(..., description="触发来源")
    error_message: str | None = Field(None, description="错误信息")
    sent_at: datetime | None = Field(None, description="发送时间")
    tenant_id: int | None = Field(None, description="企业ID")
    created_at: datetime = Field(..., description="创建时间")


class EmailSendRequest(BaseSchema):
    """手动发送邮件请求 / Manual send email request."""

    to: list[str] = Field(..., min_length=1, description="收件人列表 / Recipient list")
    subject: str = Field(..., min_length=1, max_length=500, description="邮件主题")
    html_body: str | None = Field(None, description="HTML 正文")
    text_body: str | None = Field(None, description="纯文本正文")
    cc: list[str] | None = Field(None, description="抄送列表")
    bcc: list[str] | None = Field(None, description="密送列表")


class EmailTestRequest(BaseSchema):
    """测试邮件请求 / Test email request."""

    to: str = Field(..., description="测试收件人邮箱 / Test recipient email")


__all__ = [
    "EmailLogResponse",
    "EmailSendRequest",
    "EmailTestRequest",
]
