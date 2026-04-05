"""
公共认证 Schema / Common Auth Schema

定义三端共用的认证相关数据结构
Defines authentication data structures shared across all endpoints.
"""

from pydantic import Field

from app.core.base_schema import BaseSchema


class TokenResponse(BaseSchema):
    """Token 响应 / Token response (access + refresh)."""

    access_token: str = Field(..., description="访问令牌 / Access token")
    refresh_token: str = Field(..., description="刷新令牌 / Refresh token")
    token_type: str = Field(default="bearer", description="令牌类型 / Token type")


class RefreshTokenRequest(BaseSchema):
    """刷新 Token 请求 / Refresh token request."""

    refresh_token: str = Field(..., description="刷新令牌 / Refresh token")


class DevBootstrapRequest(BaseSchema):
    """开发环境 bootstrap 登录请求 / Development bootstrap auth request."""

    bootstrap_secret: str = Field(
        ...,
        min_length=1,
        description="开发环境 bootstrap 密钥 / Development bootstrap secret",
    )


class ImpersonateTokenRequest(BaseSchema):
    """一键登录 Token 验证请求 / Impersonate token verification request."""

    impersonate_token: str = Field(
        ..., description="一键登录 Token / Impersonate token"
    )


__all__ = [
    "TokenResponse",
    "RefreshTokenRequest",
    "DevBootstrapRequest",
    "ImpersonateTokenRequest",
]
