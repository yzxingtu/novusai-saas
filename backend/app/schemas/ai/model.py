"""
AI 模型相关 Schema / AI Model Schema

定义 AI 模型的请求和响应数据结构
Defines AI model request and response data structures.
"""

from decimal import Decimal

from pydantic import Field

from app.core.base_schema import (
    BaseCreateSchema,
    BaseResponseSchema,
    BaseUpdateSchema,
)
from app.core.i18n import _


class AIModelCreate(BaseCreateSchema):
    """创建 AI 模型请求"""

    provider_id: int = Field(..., description=_("enum.ai_model.provider_id"))
    name: str = Field(..., max_length=100, description=_("enum.ai_model.name"))
    code: str = Field(..., max_length=100, description=_("enum.ai_model.code"))
    type: str = Field(..., max_length=50, description=_("enum.ai_model.type"))
    context_window: int | None = Field(None, description=_("enum.ai_model.context_window"))
    max_output_tokens: int | None = Field(None, description=_("enum.ai_model.max_output_tokens"))
    input_price_per_1k: float | None = Field(None, description=_("enum.ai_model.input_price_per_1k"))
    output_price_per_1k: float | None = Field(None, description=_("enum.ai_model.output_price_per_1k"))
    supports_function_calling: bool = Field(False, description=_("enum.ai_model.supports_function_calling"))
    supports_vision: bool = Field(False, description=_("enum.ai_model.supports_vision"))
    supports_streaming: bool = Field(True, description=_("enum.ai_model.supports_streaming"))
    max_image_count: int | None = Field(5, description=_("enum.ai_model.max_image_count"))
    max_image_size_mb: int | None = Field(10, description=_("enum.ai_model.max_image_size_mb"))
    is_active: bool = Field(True, description=_("enum.ai_model.is_active"))
    config: dict | None = Field(None, description=_("enum.ai_model.config"))
    fallback_model_id: int | None = Field(None, description=_("enum.ai_model.fallback_model_id"))
    tier: str | None = Field(None, description=_("enum.ai_model.tier"))


class AIModelUpdate(BaseUpdateSchema):
    """更新 AI 模型请求"""

    provider_id: int | None = Field(None, description=_("enum.ai_model.provider_id"))
    name: str | None = Field(None, max_length=100, description=_("enum.ai_model.name"))
    code: str | None = Field(None, max_length=100, description=_("enum.ai_model.code"))
    type: str | None = Field(None, max_length=50, description=_("enum.ai_model.type"))
    context_window: int | None = Field(None, description=_("enum.ai_model.context_window"))
    max_output_tokens: int | None = Field(None, description=_("enum.ai_model.max_output_tokens"))
    input_price_per_1k: float | None = Field(None, description=_("enum.ai_model.input_price_per_1k"))
    output_price_per_1k: float | None = Field(None, description=_("enum.ai_model.output_price_per_1k"))
    supports_function_calling: bool | None = Field(None, description=_("enum.ai_model.supports_function_calling"))
    supports_vision: bool | None = Field(None, description=_("enum.ai_model.supports_vision"))
    supports_streaming: bool | None = Field(None, description=_("enum.ai_model.supports_streaming"))
    max_image_count: int | None = Field(None, description=_("enum.ai_model.max_image_count"))
    max_image_size_mb: int | None = Field(None, description=_("enum.ai_model.max_image_size_mb"))
    is_active: bool | None = Field(None, description=_("enum.ai_model.is_active"))
    config: dict | None = Field(None, description=_("enum.ai_model.config"))
    fallback_model_id: int | None = Field(None, description=_("enum.ai_model.fallback_model_id"))
    tier: str | None = Field(None, description=_("enum.ai_model.tier"))


class AIModelResponse(BaseResponseSchema):
    """AI 模型响应"""

    provider_id: int = Field(..., description=_("enum.ai_model.provider_id"))
    name: str = Field(..., description=_("enum.ai_model.name"))
    code: str = Field(..., description=_("enum.ai_model.code"))
    type: str = Field(..., description=_("enum.ai_model.type"))
    context_window: int | None = Field(None, description=_("enum.ai_model.context_window"))
    max_output_tokens: int | None = Field(None, description=_("enum.ai_model.max_output_tokens"))
    input_price_per_1k: Decimal | None = Field(None, description=_("enum.ai_model.input_price_per_1k"))
    output_price_per_1k: Decimal | None = Field(None, description=_("enum.ai_model.output_price_per_1k"))
    supports_function_calling: bool = Field(..., description=_("enum.ai_model.supports_function_calling"))
    supports_vision: bool = Field(..., description=_("enum.ai_model.supports_vision"))
    supports_streaming: bool = Field(..., description=_("enum.ai_model.supports_streaming"))
    max_image_count: int | None = Field(None, description=_("enum.ai_model.max_image_count"))
    max_image_size_mb: int | None = Field(None, description=_("enum.ai_model.max_image_size_mb"))
    is_active: bool = Field(..., description=_("enum.ai_model.is_active"))
    config: dict | None = Field(None, description=_("enum.ai_model.config"))
    fallback_model_id: int | None = Field(None, description=_("enum.ai_model.fallback_model_id"))
    fallback_model_name: str | None = Field(None, description=_("enum.ai_model.fallback_model_name"))
    provider_name: str | None = Field(None, description=_("enum.ai_model.provider_name"))
    provider_icon: str | None = Field(None, description=_("enum.ai_model.provider_icon"))
    tier: str | None = Field(None, description=_("enum.ai_model.tier"))


__all__ = [
    "AIModelCreate",
    "AIModelUpdate",
    "AIModelResponse",
]
