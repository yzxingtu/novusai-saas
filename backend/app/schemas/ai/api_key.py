"""
AI 供应商 API Key 相关 Schema / AI Provider API Key Schema

定义 API Key 的请求和响应数据结构
Defines API key request and response data structures.
"""

from datetime import datetime
from typing import Any

from pydantic import Field, model_validator

from app.core.base_schema import (
    BaseCreateSchema,
    BaseResponseSchema,
    BaseUpdateSchema,
)
from app.core.i18n import _
from app.enums.common import ResourceScopeEnum


class ProviderApiKeyCreate(BaseCreateSchema):
    """创建 API Key 请求 / Create API Key request"""

    provider_id: int = Field(..., description=_("enum.ai_api_key.provider_id"))
    scope: str = Field(
        ResourceScopeEnum.GLOBAL_SHARED.value,
        description=_("enum.ai_api_key.scope"),
    )
    owner_tenant_id: int | None = Field(
        None,
        description="归属企业 ID / Owner tenant id",
    )
    name: str = Field(..., max_length=100, description=_("enum.ai_api_key.name"))
    api_key: str = Field(..., min_length=1, description=_("enum.ai_api_key.api_key"))
    is_active: bool = Field(True, description=_("enum.ai_api_key.is_active"))
    usage_limit: int | None = Field(
        None, ge=0, description=_("enum.ai_api_key.usage_limit")
    )
    expires_at: datetime | None = Field(
        None, description=_("enum.ai_api_key.expires_at")
    )

    @model_validator(mode="before")
    @classmethod
    def reject_legacy_tenant_id(cls, data: Any) -> Any:
        """中文: AI API Key 公共契约只接受 owner_tenant_id。

        EN: The public AI API key contract only accepts owner_tenant_id.
        """
        if isinstance(data, dict) and "tenant_id" in data:
            raise ValueError("tenant_id is retired; use owner_tenant_id")
        return data


class ProviderApiKeyUpdate(BaseUpdateSchema):
    """更新 API Key 请求（不允许更新 Key 本身） / Update API Key request (key value not updatable)."""

    name: str | None = Field(
        None, max_length=100, description=_("enum.ai_api_key.name")
    )
    is_active: bool | None = Field(None, description=_("enum.ai_api_key.is_active"))
    usage_limit: int | None = Field(
        None, ge=0, description=_("enum.ai_api_key.usage_limit")
    )
    expires_at: datetime | None = Field(
        None, description=_("enum.ai_api_key.expires_at")
    )


class ProviderApiKeyResponse(BaseResponseSchema):
    """API Key 响应（不返回明文 Key） / API Key response (no plaintext key)"""

    provider_id: int = Field(..., description=_("enum.ai_api_key.provider_id"))
    scope: str = Field(..., description=_("enum.ai_api_key.scope"))
    owner_tenant_id: int | None = Field(
        None,
        description=_("enum.ai_api_key.tenant_id"),
    )
    name: str = Field(..., description=_("enum.ai_api_key.name"))
    is_active: bool = Field(..., description=_("enum.ai_api_key.is_active"))
    usage_limit: int | None = Field(None, description=_("enum.ai_api_key.usage_limit"))
    usage_count: int = Field(..., description=_("enum.ai_api_key.usage_count"))
    last_used_at: datetime | None = Field(
        None, description=_("enum.ai_api_key.last_used_at")
    )
    expires_at: datetime | None = Field(
        None, description=_("enum.ai_api_key.expires_at")
    )
    provider_name: str | None = Field(
        None, description=_("enum.ai_api_key.provider_name")
    )
    provider_icon: str | None = Field(
        None, description=_("enum.ai_api_key.provider_icon")
    )
    provider_model_count: int = Field(
        0, description=_("enum.ai_api_key.provider_model_count")
    )
    tenant_name: str | None = Field(None, description=_("enum.ai_api_key.tenant_name"))
    is_available: bool = Field(..., description=_("enum.ai_api_key.is_available"))
    key_preview: str | None = Field(None, description=_("enum.ai_api_key.key_preview"))


__all__ = [
    "ProviderApiKeyCreate",
    "ProviderApiKeyUpdate",
    "ProviderApiKeyResponse",
]
