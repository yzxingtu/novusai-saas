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
    tenant_id: int | None = Field(default=None)
    tenant_name: str | None = Field(default=None)
    org_node_id: int | None = Field(default=None)
    org_node_name: str | None = Field(default=None)
    role_name: str | None = Field(default=None)
    is_active: bool | None = Field(default=None)
    is_owner: bool | None = Field(default=None)
    is_leader: bool | None = Field(default=None)


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
    turn_outcome: str | None = None
    termination_reason: str | None = None
    protocol_path: str | None = None
    selected_tool_names: list[str] = Field(default_factory=list)
    selected_skill_names: list[str] = Field(default_factory=list)
    execution_path: str | None = None
    intent_plan: list[dict[str, Any]] = Field(default_factory=list)
    budget: dict[str, Any] | None = None
    budget_status: str | None = None
    budget_exit_reason: str | None = None
    candidate_tool_names: list[str] = Field(default_factory=list)
    context_sources: list[dict[str, Any]] = Field(default_factory=list)
    fallback_history: list[dict[str, Any]] = Field(default_factory=list)
    retry_events: list[dict[str, Any]] = Field(default_factory=list)
    partial_exit_reason: str | None = None
    failure_kind: str | None = None
    provider_events: list[dict[str, Any]] = Field(default_factory=list)
    sync_rescue: bool | None = None
    should_record_call_log: bool | None = None
    contract_breach_type: str | None = None
    tool_leak_detected: bool = False
    unfinished_intents: list[str] = Field(default_factory=list)
    leaked_tool_names: list[str] = Field(default_factory=list)
    recovered_via_retry: bool | None = None
    last_tool_name: str | None = None
    last_page_key: str | None = None
    last_page_op: str | None = None
    interrupted_stage: str | None = None
    tool_loop_progress: dict[str, Any] | None = None
    turn_record: dict[str, Any] | None = None


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
    context_diagnostics: dict[str, Any] | None = None
    last_run_summary: dict[str, Any] | None = None
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
    actor: MonitoringActorInfo | None = None
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
    access_channel_stats: list[MonitoringUsageBreakdownItem] = Field(
        default_factory=list
    )
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
