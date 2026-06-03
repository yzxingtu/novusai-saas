"""
公开 API Schema / Public API Schema

定义无需认证即可访问的 API 数据结构
Defines API data structures accessible without authentication.
"""

from app.schemas.public.platform import PlatformPublicConfig
from app.schemas.public.tenant import (
    DomainVerificationInfo,
    TenantLegalDocumentResponse,
    TenantPublicConfig,
)

__all__ = [
    "TenantPublicConfig",
    "TenantLegalDocumentResponse",
    "DomainVerificationInfo",
    "PlatformPublicConfig",
]
