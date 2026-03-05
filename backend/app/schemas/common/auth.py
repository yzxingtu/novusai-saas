"""
公共认证 Schema

定义三端共用的认证相关数据结构
"""

from pydantic import Field

from app.core.base_schema import BaseSchema


class TokenResponse(BaseSchema):
    """Token 响应"""

    access_token: str = Field(..., description="访问令牌")
    refresh_token: str = Field(..., description="刷新令牌")
    token_type: str = Field(default="bearer", description="令牌类型")


class RefreshTokenRequest(BaseSchema):
    """刷新 Token 请求"""

    refresh_token: str = Field(..., description="刷新令牌")


class ImpersonateTokenRequest(BaseSchema):
    """一键登录 Token 验证请求"""

    impersonate_token: str = Field(..., description="一键登录 Token")


__all__ = [
    "TokenResponse",
    "RefreshTokenRequest",
    "ImpersonateTokenRequest",
]
