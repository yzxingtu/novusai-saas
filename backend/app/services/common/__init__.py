"""
公共服务模块

提供三端共用的服务和 Mixin
"""

from app.services.common.role_tree_mixin import RoleTreeMixin, MAX_ROLE_DEPTH
from app.services.common.auth_service import AuthService
from app.services.common.storage_quota_service import StorageQuotaService
from app.services.common.storage_config_resolver import StorageConfigResolver
from app.services.common.image_process_service import ImageProcessService
from app.services.common.file_validator import (
    FileValidator,
    FileValidationResult,
    validate_result_or_raise,
)
from app.services.common.email_service import (
    EmailService,
    EmailMessage,
    EmailAttachment,
    EmailResult,
    send_email_sync,
)


__all__ = [
    "RoleTreeMixin",
    "MAX_ROLE_DEPTH",
    "AuthService",
    "StorageQuotaService",
    "StorageConfigResolver",
    "ImageProcessService",
    "FileValidator",
    "FileValidationResult",
    "validate_result_or_raise",
    "EmailService",
    "EmailMessage",
    "EmailAttachment",
    "EmailResult",
    "send_email_sync",
]
