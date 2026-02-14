"""
AI 使用量统计相关 Schema

定义使用量统计的响应数据结构
"""

from datetime import date

from pydantic import Field

from app.core.base_schema import TenantResponseSchema
from app.core.i18n import _


class UsageStatResponse(TenantResponseSchema):
    """AI 使用量统计响应"""

    user_id: int | None = Field(None, description=_("enum.ai_usage_stat.user_id"))
    model_id: int = Field(..., description=_("enum.ai_usage_stat.model_id"))
    request_type: str = Field(..., description=_("enum.ai_usage_stat.request_type"))
    stat_date: date = Field(..., description=_("enum.ai_usage_stat.stat_date"))
    input_tokens: int = Field(0, description=_("enum.ai_usage_stat.input_tokens"))
    output_tokens: int = Field(0, description=_("enum.ai_usage_stat.output_tokens"))
    total_tokens: int = Field(0, description=_("enum.ai_usage_stat.total_tokens"))
    call_count: int = Field(0, description=_("enum.ai_usage_stat.call_count"))
    success_count: int = Field(0, description=_("enum.ai_usage_stat.success_count"))
    failed_count: int = Field(0, description=_("enum.ai_usage_stat.failed_count"))
    total_cost: float = Field(0, description=_("enum.ai_usage_stat.total_cost"))
    avg_latency_ms: int | None = Field(None, description=_("enum.ai_usage_stat.avg_latency_ms"))
    max_latency_ms: int | None = Field(None, description=_("enum.ai_usage_stat.max_latency_ms"))


__all__ = [
    "UsageStatResponse",
]
