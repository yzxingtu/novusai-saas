"""
AI 配额诊断 Schema / AI quota diagnostics schema
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AIQuotaDiagnosticsSummary(BaseModel):
    """AI 配额诊断总览 / AI quota diagnostics summary."""

    total_quota_rules: int = Field(default=0, description="配额规则总数")
    active_quota_rules: int = Field(default=0, description="启用中的配额规则数")
    hard_quota_rules: int = Field(default=0, description="硬配额规则数")
    soft_quota_rules: int = Field(default=0, description="软配额规则数")
    quota_warning_rules: int = Field(default=0, description="达到预警阈值的配额规则数")
    quota_exceeded_rules: int = Field(default=0, description="已超限配额规则数")
    total_rate_limit_rules: int = Field(default=0, description="速率限制规则总数")
    active_rate_limit_rules: int = Field(
        default=0, description="启用中的速率限制规则数"
    )
    rate_limit_warning_rules: int = Field(default=0, description="接近限速阈值的规则数")
    rate_limit_exceeded_rules: int = Field(
        default=0, description="当前已超限的速率限制规则数"
    )


class AdminQuotaDiagnosticItem(BaseModel):
    """管理端配额诊断项 / Admin quota diagnostic item."""

    id: int
    tenant_id: int
    tenant_name: str | None = None
    model_id: int | None = None
    model_name: str | None = None
    period: str
    limit: int
    quota_type: str
    warning_threshold: int | None = None
    is_active: bool
    description: str | None = None
    scope_type: str = Field(description="global/model")
    tracking_model_id: int = Field(description="Redis usage bucket model id")
    usage: int = 0
    remaining: int = 0
    usage_percent: float = 0
    is_warning: bool = False
    is_exceeded: bool = False
    runtime_status: str = Field(description="inactive/healthy/warning/exceeded")
    exhaustion_action: str = Field(description="allow/deny")
    exhaustion_http_status: int | None = None
    exhaustion_error_code: int | None = None
    exhaustion_message_preview: str | None = None
    is_latest_scope_rule: bool = True
    created_at: datetime
    updated_at: datetime


class AdminRateLimitDiagnosticItem(BaseModel):
    """管理端速率限制诊断项 / Admin rate-limit diagnostic item."""

    id: int
    tenant_id: int
    tenant_name: str | None = None
    model_id: int
    model_name: str | None = None
    is_active: bool
    description: str | None = None
    configured_rpm_limit: int | None = None
    configured_tpm_limit: int | None = None
    model_default_rpm_limit: int | None = None
    model_default_tpm_limit: int | None = None
    effective_rpm_limit: int | None = None
    effective_tpm_limit: int | None = None
    rpm_source: str = Field(description="tenant/model/none")
    tpm_source: str = Field(description="tenant/model/none")
    current_rpm: int = 0
    current_tpm: int = 0
    rpm_usage_percent: float = 0
    tpm_usage_percent: float = 0
    is_warning: bool = False
    is_exceeded: bool = False
    runtime_status: str = Field(description="inactive/healthy/warning/exceeded")
    exhaustion_action: str = Field(default="deny", description="allow/deny")
    exhaustion_http_status: int = 429
    exhaustion_error_code: int = 4292
    exhaustion_message_preview: str | None = None
    is_latest_model_rule: bool = True
    created_at: datetime
    updated_at: datetime


__all__ = [
    "AIQuotaDiagnosticsSummary",
    "AdminQuotaDiagnosticItem",
    "AdminRateLimitDiagnosticItem",
]
