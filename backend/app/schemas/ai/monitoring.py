"""
AI monitoring read models / AI 监控读模型。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from app.core.base_schema import BaseSchema


class MonitoringActorInfo(BaseSchema):
    id: int | None = Field(default=None)
    type: str | None = Field(default=None)
    display_name: str | None = Field(default=None)
    username: str | None = Field(default=None)
    nickname: str | None = Field(default=None)
    avatar: str | None = Field(default=None)


class MonitoringConversationListItem(BaseSchema):
    id: int
    tenant_id: int | None = None
    tenant_name: str | None = None
    agent_id: int | None = None
    agent_name: str | None = None
    agent_avatar: str | None = None
    owner_type: str | None = None
    actor: MonitoringActorInfo | None = None
    title: str | None = None
    status: str
    message_count: int = 0
    call_count: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    last_call_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class MonitoringCallTraceItem(BaseSchema):
    id: int
    created_at: datetime
    status: str
    request_type: str
    model_name: str | None = None
    provider_name: str | None = None
    total_tokens: int = 0
    cost: float = 0.0
    latency_ms: int | None = None
    usage_mode: str | None = None
    error_message: str | None = None


class MonitoringConversationDetail(BaseSchema):
    id: int
    tenant_id: int | None = None
    tenant_name: str | None = None
    agent_id: int | None = None
    agent_name: str | None = None
    agent_avatar: str | None = None
    owner_type: str | None = None
    actor: MonitoringActorInfo | None = None
    title: str | None = None
    status: str
    message_count: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    call_count: int = 0
    last_call_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] | None = None
    message_list: list[dict[str, Any]] = Field(default_factory=list)
    call_trace: list[MonitoringCallTraceItem] = Field(default_factory=list)


class MonitoringUsageSummary(BaseSchema):
    total_calls: int = 0
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_cost: float = 0.0
    success_calls: int = 0
    failed_calls: int = 0
    success_rate: float = 0.0


class MonitoringUsageSeriesPoint(BaseSchema):
    date: str
    call_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    success_calls: int = 0
    failed_calls: int = 0


class MonitoringUsageBreakdownItem(BaseSchema):
    key: str
    label: str
    call_count: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    success_calls: int = 0
    failed_calls: int = 0


class MonitoringUsageDashboard(BaseSchema):
    scope: str
    tenant_id: int | None = None
    tenant_name: str | None = None
    summary: MonitoringUsageSummary
    daily_stats: list[MonitoringUsageSeriesPoint] = Field(default_factory=list)
    model_stats: list[MonitoringUsageBreakdownItem] = Field(default_factory=list)
    access_channel_stats: list[MonitoringUsageBreakdownItem] = Field(default_factory=list)
    top_agents: list[MonitoringUsageBreakdownItem] = Field(default_factory=list)
    top_users: list[MonitoringUsageBreakdownItem] = Field(default_factory=list)
    top_tenants: list[MonitoringUsageBreakdownItem] = Field(default_factory=list)


__all__ = [
    "MonitoringActorInfo",
    "MonitoringCallTraceItem",
    "MonitoringConversationDetail",
    "MonitoringConversationListItem",
    "MonitoringUsageBreakdownItem",
    "MonitoringUsageDashboard",
    "MonitoringUsageSeriesPoint",
    "MonitoringUsageSummary",
]
