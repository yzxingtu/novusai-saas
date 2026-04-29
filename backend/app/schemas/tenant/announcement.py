"""
公告管理相关 Schema / Announcement management schemas.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from app.core.base_schema import (
    BaseCreateSchema,
    BaseResponseSchema,
    BaseSchema,
    BaseUpdateSchema,
    TenantResponseSchema,
)
from app.core.i18n import _

AnnouncementScope = Literal["admin", "tenant"]
AnnouncementStatus = Literal["draft", "published"]
AnnouncementPriority = Literal["low", "normal", "high", "urgent"]
AnnouncementRecipientType = Literal["admin", "tenant_admin", "tenant_user"]
AnnouncementFieldType = Literal["consent", "text", "radio", "checkbox"]


class AnnouncementFormOption(BaseSchema):
    """表单选项 / Form option."""

    label: str = Field(..., min_length=1)
    value: str = Field(..., min_length=1)


class AnnouncementFormField(BaseSchema):
    """公告反馈表单字段 / Announcement feedback form field."""

    key: str = Field(..., min_length=1)
    type: AnnouncementFieldType
    label: str = Field(..., min_length=1)
    required: bool = False
    placeholder: str | None = None
    options: list[AnnouncementFormOption] | None = None
    must_be_true: bool | None = None


class AnnouncementCreate(BaseCreateSchema):
    """创建公告草稿请求 / Create announcement draft request."""

    title: str = Field(..., min_length=1, description=_("tenant.announcement.field.title"))
    content: str | None = Field(None, description=_("tenant.announcement.field.content"))
    priority: AnnouncementPriority = Field(
        "normal", description=_("tenant.announcement.field.priority")
    )
    require_response: bool = Field(
        False, description=_("tenant.announcement.field.require_response")
    )
    form_schema: list[AnnouncementFormField] = Field(
        default_factory=list,
        description=_("tenant.announcement.field.form_schema"),
    )
    sort_order: int = Field(0, description=_("tenant.announcement.field.sort_order"))


class AnnouncementUpdate(BaseUpdateSchema):
    """更新公告草稿请求 / Update announcement draft request."""

    title: str | None = Field(None, min_length=1, description=_("tenant.announcement.field.title"))
    content: str | None = Field(None, description=_("tenant.announcement.field.content"))
    priority: AnnouncementPriority | None = Field(
        None, description=_("tenant.announcement.field.priority")
    )
    require_response: bool | None = Field(
        None, description=_("tenant.announcement.field.require_response")
    )
    form_schema: list[AnnouncementFormField] | None = Field(
        None,
        description=_("tenant.announcement.field.form_schema"),
    )
    sort_order: int | None = Field(
        None, description=_("tenant.announcement.field.sort_order")
    )


class AnnouncementAnswerSubmit(BaseSchema):
    """提交公告反馈 / Submit announcement feedback."""

    answers: dict[str, Any] = Field(default_factory=dict)


class AnnouncementBaseResponse(TenantResponseSchema):
    """公告基础响应 / Announcement base response."""

    scope: str = Field(..., description=_("tenant.announcement.field.scope"))
    title: str = Field(..., description=_("tenant.announcement.field.title"))
    content: str | None = Field(None, description=_("tenant.announcement.field.content"))
    status: str = Field(..., description=_("tenant.announcement.field.status"))
    priority: str = Field(..., description=_("tenant.announcement.field.priority"))
    require_response: bool = Field(
        ..., description=_("tenant.announcement.field.require_response")
    )
    form_schema: list[dict] = Field(
        default_factory=list,
        description=_("tenant.announcement.field.form_schema"),
    )
    published_at: datetime | None = Field(
        None, description=_("tenant.announcement.field.published_at")
    )
    recipient_count: int = Field(
        ..., description=_("tenant.announcement.field.recipient_count")
    )
    response_count: int = Field(
        ..., description=_("tenant.announcement.field.response_count")
    )
    sort_order: int = Field(..., description=_("tenant.announcement.field.sort_order"))

    @classmethod
    def from_model(cls, obj) -> AnnouncementBaseResponse:
        """从模型创建响应 / Build response from model."""
        return cls(
            id=obj.id,
            tenant_id=obj.tenant_id,
            scope=getattr(obj, "scope", None),
            title=getattr(obj, "title", None),
            content=getattr(obj, "content", None),
            status=getattr(obj, "status", None),
            priority=getattr(obj, "priority", None),
            require_response=getattr(obj, "require_response", False),
            form_schema=getattr(obj, "form_schema", None) or [],
            published_at=getattr(obj, "published_at", None),
            recipient_count=getattr(obj, "recipient_count", 0),
            response_count=getattr(obj, "response_count", 0),
            sort_order=getattr(obj, "sort_order", 0),
            created_at=obj.created_at,
            updated_at=obj.updated_at,
        )


class AdminAnnouncementResponse(AnnouncementBaseResponse):
    """公告管理响应（管理端）/ Announcement response (admin)."""


class TenantAnnouncementResponse(AnnouncementBaseResponse):
    """公告管理响应（企业端）/ Announcement response (tenant)."""


class AnnouncementDeliveryResponse(TenantResponseSchema):
    """公告投递响应 / Announcement delivery response."""

    announcement_id: int
    recipient_type: str
    recipient_id: int
    status: str
    notification_id: int | None = None
    submitted_at: datetime | None = None
    answers: dict[str, Any] | None = None

    @classmethod
    def from_delivery(cls, obj) -> AnnouncementDeliveryResponse:
        response = getattr(obj, "response", None)
        return cls(
            id=obj.id,
            tenant_id=obj.tenant_id,
            announcement_id=obj.announcement_id,
            recipient_type=obj.recipient_type,
            recipient_id=obj.recipient_id,
            status=obj.status,
            notification_id=obj.notification_id,
            submitted_at=obj.submitted_at,
            answers=getattr(response, "answers", None) if response else None,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
        )


class PendingAnnouncementResponse(AnnouncementBaseResponse):
    """待处理公告响应 / Pending announcement response."""

    delivery_id: int

    @classmethod
    def from_delivery(cls, delivery) -> PendingAnnouncementResponse:
        announcement = delivery.announcement
        payload = AnnouncementBaseResponse.from_model(announcement).model_dump()
        payload["delivery_id"] = delivery.id
        return cls(**payload)


class CurrentAnnouncementResponse(AnnouncementBaseResponse):
    """当前接收人的公告详情 / Announcement detail for current recipient."""

    delivery_id: int
    delivery_status: str
    notification_id: int | None = None
    submitted_at: datetime | None = None
    answers: dict[str, Any] | None = None

    @classmethod
    def from_delivery(cls, delivery) -> CurrentAnnouncementResponse:
        announcement = delivery.announcement
        response = getattr(delivery, "response", None)
        payload = AnnouncementBaseResponse.from_model(announcement).model_dump()
        payload["delivery_id"] = delivery.id
        payload["delivery_status"] = delivery.status
        payload["notification_id"] = delivery.notification_id
        payload["submitted_at"] = delivery.submitted_at
        payload["answers"] = getattr(response, "answers", None) if response else None
        return cls(**payload)


class AnnouncementSubmitResult(BaseResponseSchema):
    """公告反馈提交结果 / Announcement feedback submit result."""

    announcement_id: int
    delivery_id: int
    status: str

    @classmethod
    def from_delivery(cls, delivery) -> AnnouncementSubmitResult:
        return cls(
            id=delivery.id,
            announcement_id=delivery.announcement_id,
            delivery_id=delivery.id,
            status=delivery.status,
            created_at=delivery.created_at,
            updated_at=delivery.updated_at,
        )


__all__ = [
    "AnnouncementAnswerSubmit",
    "AnnouncementCreate",
    "AnnouncementDeliveryResponse",
    "AnnouncementFormField",
    "AnnouncementFormOption",
    "AnnouncementSubmitResult",
    "AnnouncementUpdate",
    "AdminAnnouncementResponse",
    "CurrentAnnouncementResponse",
    "PendingAnnouncementResponse",
    "TenantAnnouncementResponse",
]
