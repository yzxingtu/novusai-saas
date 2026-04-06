"""
AI 供应商相关 Schema / AI Provider Schema

定义 AI 供应商的请求和响应数据结构
Defines AI provider request and response data structures.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.base_schema import (
    BaseCreateSchema,
    BaseResponseSchema,
    BaseUpdateSchema,
)
from app.core.i18n import _


class AIProviderCreate(BaseCreateSchema):
    """创建 AI 供应商请求 / Create AI provider request."""

    name: str = Field(..., max_length=100, description=_("enum.ai_provider.name"))
    code: str | None = Field(
        None, max_length=50, description=_("enum.ai_provider.code")
    )
    type: str = Field(..., max_length=50, description=_("enum.ai_provider.type"))
    base_url: str | None = Field(
        None, max_length=500, description=_("enum.ai_provider.base_url")
    )
    description: str | None = Field(None, description=_("enum.ai_provider.description"))
    icon: str | None = Field(
        None, max_length=255, description=_("enum.ai_provider.icon")
    )
    is_active: bool = Field(True, description=_("enum.ai_provider.is_active"))
    sort_order: int = Field(0, description=_("enum.ai_provider.sort_order"))
    config: dict | None = Field(None, description=_("enum.ai_provider.config"))


class AIProviderUpdate(BaseUpdateSchema):
    """更新 AI 供应商请求 / Update AI provider request."""

    name: str | None = Field(
        None, max_length=100, description=_("enum.ai_provider.name")
    )
    code: str | None = Field(
        None, max_length=50, description=_("enum.ai_provider.code")
    )
    type: str | None = Field(
        None, max_length=50, description=_("enum.ai_provider.type")
    )
    base_url: str | None = Field(
        None, max_length=500, description=_("enum.ai_provider.base_url")
    )
    description: str | None = Field(None, description=_("enum.ai_provider.description"))
    icon: str | None = Field(
        None, max_length=255, description=_("enum.ai_provider.icon")
    )
    is_active: bool | None = Field(None, description=_("enum.ai_provider.is_active"))
    sort_order: int | None = Field(None, description=_("enum.ai_provider.sort_order"))
    config: dict | None = Field(None, description=_("enum.ai_provider.config"))


class AIProviderWebSearchConfig(BaseModel):
    """AI Provider web_search config (stored under provider.config.web_search)."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    strategy: Literal["native_first_fallback_public"] = "native_first_fallback_public"
    max_results_cap: int = Field(8, ge=1, le=10)
    native_timeout_seconds: int = Field(20, ge=1, le=60)
    public_timeout_seconds: int = Field(15, ge=1, le=60)
    public_providers: list[Literal["baidu", "so360"]] = Field(
        default_factory=lambda: ["baidu", "so360"],
        min_length=1,
    )


class AIProviderWebSearchRuntime(BaseModel):
    """Runtime-only web_search capability summary (not persisted)."""

    native_supported: bool = False
    native_provider: str = ""
    reason: str = ""


class AIProviderResponse(BaseResponseSchema):
    """AI 供应商响应 / AI provider response."""

    name: str = Field(..., description=_("enum.ai_provider.name"))
    code: str = Field(..., description=_("enum.ai_provider.code"))
    type: str = Field(..., description=_("enum.ai_provider.type"))
    base_url: str | None = Field(None, description=_("enum.ai_provider.base_url"))
    description: str | None = Field(None, description=_("enum.ai_provider.description"))
    icon: str | None = Field(None, description=_("enum.ai_provider.icon"))
    is_active: bool = Field(..., description=_("enum.ai_provider.is_active"))
    sort_order: int = Field(..., description=_("enum.ai_provider.sort_order"))
    config: dict | None = Field(None, description=_("enum.ai_provider.config"))
    model_count: int = Field(0, description=_("enum.ai_provider.model_count"))
    web_search_runtime: AIProviderWebSearchRuntime | None = Field(
        None,
        description="Runtime web-search capability summary",
    )


def normalize_provider_web_search_config(
    config: dict[str, Any] | None,
    *,
    defaults: AIProviderWebSearchConfig,
) -> AIProviderWebSearchConfig:
    """Normalize provider.config.web_search using structured schema + defaults."""
    merged = defaults.model_dump()
    if isinstance(config, dict):
        merged.update(config)
    return AIProviderWebSearchConfig.model_validate(merged)


__all__ = [
    "AIProviderCreate",
    "AIProviderUpdate",
    "AIProviderResponse",
    "AIProviderWebSearchConfig",
    "AIProviderWebSearchRuntime",
    "normalize_provider_web_search_config",
]
