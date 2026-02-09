"""
AI 调用日志相关 Schema

定义调用日志的请求和响应数据结构
"""

from decimal import Decimal

from pydantic import Field

from app.core.base_schema import BaseResponseSchema, TenantResponseSchema
from app.core.i18n import _


class AICallLogResponse(TenantResponseSchema):
    """AI 调用日志响应"""
    
    user_id: int | None = Field(None, description=_("enum.ai_call_log.user_id"))
    user_type: str | None = Field(None, description=_("enum.ai_call_log.user_type"))
    provider_id: int = Field(..., description=_("enum.ai_call_log.provider_id"))
    model_id: int = Field(..., description=_("enum.ai_call_log.model_id"))
    request_type: str = Field(..., description=_("enum.ai_call_log.request_type"))
    input_tokens: int | None = Field(None, description=_("enum.ai_call_log.input_tokens"))
    output_tokens: int | None = Field(None, description=_("enum.ai_call_log.output_tokens"))
    total_tokens: int | None = Field(None, description=_("enum.ai_call_log.total_tokens"))
    cost: Decimal | None = Field(None, description=_("enum.ai_call_log.cost"))
    latency_ms: int | None = Field(None, description=_("enum.ai_call_log.latency_ms"))
    status: str = Field(..., description=_("enum.ai_call_log.status"))
    error_message: str | None = Field(None, description=_("enum.ai_call_log.error_message"))
    request_hash: str | None = Field(None, description=_("enum.ai_call_log.request_hash"))
    metadata: dict | None = Field(None, description=_("enum.ai_call_log.metadata"))
    provider_name: str | None = Field(None, description=_("enum.ai_call_log.provider_name"))
    model_name: str | None = Field(None, description=_("enum.ai_call_log.model_name"))


class AICallLogSummary(BaseResponseSchema):
    """AI 调用统计摘要"""
    
    total_calls: int = Field(..., description=_("enum.ai_call_summary.total_calls"))
    total_tokens: int = Field(..., description=_("enum.ai_call_summary.total_tokens"))
    total_cost: Decimal = Field(..., description=_("enum.ai_call_summary.total_cost"))
    avg_latency_ms: int | None = Field(None, description=_("enum.ai_call_summary.avg_latency_ms"))
    success_rate: float = Field(..., description=_("enum.ai_call_summary.success_rate"))


__all__ = [
    "AICallLogResponse",
    "AICallLogSummary",
]
