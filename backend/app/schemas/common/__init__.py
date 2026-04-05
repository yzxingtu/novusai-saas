"""
公共 Schema 模块 / Common Schema Module

导出三端共用的 Schema
Exports schemas shared across all endpoints.
"""

from app.schemas.common.auth import (
    DevBootstrapRequest,
    ImpersonateTokenRequest,
    RefreshTokenRequest,
    TokenResponse,
)
from app.schemas.common.captcha import (
    CaptchaChallengeRequest,
    CaptchaChallengeResponse,
    CaptchaVerifyRequest,
    CaptchaVerifyResponse,
)
from app.schemas.common.permission import (
    MenuAIResponse,
    MenuMetaResponse,
    MenuResponse,
    PermissionResponse,
    PermissionTreeResponse,
)
from app.schemas.common.query import (
    FilterOp,
    FilterRule,
    QuerySpec,
)
from app.schemas.common.select import (
    SelectOption,
    SelectResponse,
)
from app.schemas.common.sort import (
    ReorderRequest,
    ReorderResponse,
)

__all__ = [
    "TokenResponse",
    "RefreshTokenRequest",
    "DevBootstrapRequest",
    "ImpersonateTokenRequest",
    "CaptchaChallengeRequest",
    "CaptchaChallengeResponse",
    "CaptchaVerifyRequest",
    "CaptchaVerifyResponse",
    "PermissionResponse",
    "PermissionTreeResponse",
    "MenuAIResponse",
    "MenuMetaResponse",
    "MenuResponse",
    "FilterOp",
    "FilterRule",
    "QuerySpec",
    "SelectOption",
    "SelectResponse",
    "ReorderRequest",
    "ReorderResponse",
]
