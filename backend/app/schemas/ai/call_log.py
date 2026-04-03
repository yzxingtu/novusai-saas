"""
AI 调用日志相关 Schema / AI Call Log Schema

定义调用日志的请求和响应数据结构
Defines call log request and response data structures.
"""

from decimal import Decimal

from pydantic import Field

from app.core.base_schema import BaseResponseSchema, TenantResponseSchema
from app.core.i18n import _


class AICallLogResponse(TenantResponseSchema):
    """AI 调用日志响应 / AI call log response schema."""

    user_id: int | None = Field(None, description=_("enum.ai_call_log.user_id"))
    user_type: str | None = Field(None, description=_("enum.ai_call_log.user_type"))
    billing_tenant_id: int | None = Field(None, description="Billing tenant ID")
    actor_user_id: int | None = Field(None, description="Actor user ID")
    actor_user_type: str | None = Field(None, description="Actor user type")
    access_channel: str | None = Field(None, description="Access channel")
    trace_id: str | None = Field(None, description="Trace ID for ledger join")
    tool_call_id: str | None = Field(None, description="Tool call ID when applicable")
    provider_id: int = Field(..., description=_("enum.ai_call_log.provider_id"))
    model_id: int = Field(..., description=_("enum.ai_call_log.model_id"))
    request_type: str = Field(..., description=_("enum.ai_call_log.request_type"))
    call_type: str = Field(..., description="Call type")
    input_tokens: int | None = Field(
        None, description=_("enum.ai_call_log.input_tokens")
    )
    output_tokens: int | None = Field(
        None, description=_("enum.ai_call_log.output_tokens")
    )
    total_tokens: int | None = Field(
        None, description=_("enum.ai_call_log.total_tokens")
    )
    cost: Decimal | None = Field(None, description=_("enum.ai_call_log.cost"))
    latency_ms: int | None = Field(None, description=_("enum.ai_call_log.latency_ms"))
    status: str = Field(..., description=_("enum.ai_call_log.status"))
    error_message: str | None = Field(
        None, description=_("enum.ai_call_log.error_message")
    )
    request_hash: str | None = Field(
        None, description=_("enum.ai_call_log.request_hash")
    )
    metadata: dict | None = Field(None, description=_("enum.ai_call_log.metadata"))
    provider_name: str | None = Field(
        None, description=_("enum.ai_call_log.provider_name")
    )
    model_name: str | None = Field(None, description=_("enum.ai_call_log.model_name"))
    agent_owner_type: str | None = Field(None, description="Agent owner type")
    agent_owner_tenant_id: int | None = Field(None, description="Agent owner tenant ID")
    agent_resource_scope: str | None = Field(
        None,
        description="Agent resource scope snapshot (ResourceScopeEnum)",
    )
    tenant_publication_id: int | None = Field(None, description="Tenant publication ID")
    publication_enabled_snapshot: bool | None = Field(
        None, description="Publication enabled snapshot"
    )
    publication_access_type_snapshot: str | None = Field(
        None, description="Publication access type snapshot"
    )


class AICallLogSummary(BaseResponseSchema):
    """AI 调用统计摘要 / AI call statistics summary."""

    total_calls: int = Field(..., description=_("enum.ai_call_summary.total_calls"))
    total_tokens: int = Field(..., description=_("enum.ai_call_summary.total_tokens"))
    total_cost: Decimal = Field(..., description=_("enum.ai_call_summary.total_cost"))
    avg_latency_ms: int | None = Field(
        None, description=_("enum.ai_call_summary.avg_latency_ms")
    )
    success_rate: float = Field(..., description=_("enum.ai_call_summary.success_rate"))


__all__ = [
    "AICallLogResponse",
    "AICallLogSummary",
]
