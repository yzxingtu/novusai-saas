"""
公开 API Schema

定义无需认证即可访问的 API 数据结构
"""

from app.schemas.public.platform import PlatformPublicConfig
from app.schemas.public.tenant import (
    DomainVerificationInfo,
    TenantPublicConfig,
)

__all__ = [
    "TenantPublicConfig",
    "DomainVerificationInfo",
    "PlatformPublicConfig",
]
