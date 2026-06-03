"""
附件相关枚举 / Attachment Enums

定义附件可见性、状态、来源枚举
Defines attachment visibility, status, source enums.
"""

from app.enums.base import StrEnum


class AttachmentVisibility(StrEnum):
    PUBLIC = ("public", "enum.attachment_visibility.public")
    PRIVATE = ("private", "enum.attachment_visibility.private")


class AttachmentStatus(StrEnum):
    ACTIVE = ("active", "enum.attachment_status.active")
    DELETED = ("deleted", "enum.attachment_status.deleted")


class AttachmentSource(StrEnum):
    PLATFORM_ADMIN = ("platform_admin", "enum.attachment_source.platform_admin")
    TENANT_ADMIN = ("tenant_admin", "enum.attachment_source.tenant_admin")
    TENANT_USER = ("tenant_user", "enum.attachment_source.tenant_user")
    SYSTEM = ("system", "enum.attachment_source.system")


__all__ = [
    "AttachmentVisibility",
    "AttachmentStatus",
    "AttachmentSource",
]
