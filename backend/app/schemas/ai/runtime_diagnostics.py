"""
AI runtime diagnostics schemas / AI 运行时诊断 Schema。
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from app.core.base_schema import BaseSchema

RuntimeStatus = Literal["green", "yellow", "red"]
CapabilityStatus = Literal["available", "degraded", "unavailable"]


class RuntimeCapabilityItem(BaseSchema):
    name: str
    kind: str
    status: CapabilityStatus
    reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    source: str | None = None


class RuntimeCapabilityManifestSchema(BaseSchema):
    scope: str
    tenant_id: int | None = None
    agent_id: int | None = None
    provider: dict[str, Any] = Field(default_factory=dict)
    model: dict[str, Any] = Field(default_factory=dict)
    runtime_model_capabilities: dict[str, Any] = Field(default_factory=dict)
    tools: list[RuntimeCapabilityItem] = Field(default_factory=list)
    skills: list[RuntimeCapabilityItem] = Field(default_factory=list)
    knowledge_bases: list[RuntimeCapabilityItem] = Field(default_factory=list)
    memory: list[RuntimeCapabilityItem] = Field(default_factory=list)
    page_context: list[RuntimeCapabilityItem] = Field(default_factory=list)
    web_research: list[RuntimeCapabilityItem] = Field(default_factory=list)
    extensions: list[RuntimeCapabilityItem] = Field(default_factory=list)
    disabled_capabilities: list[RuntimeCapabilityItem] = Field(default_factory=list)
    boundaries: dict[str, Any] = Field(default_factory=dict)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)


class RuntimeCheckItem(BaseSchema):
    name: str
    status: CapabilityStatus
    blocking: bool = False
    reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RuntimeFailureAggregateItem(BaseSchema):
    failure_kind: str | None = None
    provider: str | None = None
    model: str | None = None
    agent: str | None = None
    tool: str | None = None
    contract_breach_type: str | None = None
    count: int = 0


class RuntimeDoctorReportSchema(BaseSchema):
    overall_status: RuntimeStatus
    checks: list[RuntimeCheckItem] = Field(default_factory=list)
    recent_failures: list[RuntimeFailureAggregateItem] = Field(default_factory=list)
    capability_manifest_summary: dict[str, Any] = Field(default_factory=dict)
    recommended_actions: list[str] = Field(default_factory=list)


class RuntimeSmokeRequest(BaseSchema):
    tenant_id: int | None = None
    agent_id: int | None = None
    agent_code: str | None = None


class RuntimeSmokeReportSchema(BaseSchema):
    overall_status: RuntimeStatus
    checks: list[RuntimeCheckItem] = Field(default_factory=list)
    runtime_capability_manifest: RuntimeCapabilityManifestSchema | None = None
    recommended_actions: list[str] = Field(default_factory=list)


class RuntimeRootCauseReportSchema(BaseSchema):
    status: str
    failure_layer: str | None = None
    cause_code: str | None = None
    summary: str = ""
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    first_fix: str | None = None
    confidence: float | None = None
    recovered_via_retry: bool | None = None
    related_ids: dict[str, Any] = Field(default_factory=dict)


class ExtensionLifecycleAuditReportSchema(BaseSchema):
    runtime_kind: str
    target: dict[str, Any] = Field(default_factory=dict)
    stage_results: list[dict[str, Any]] = Field(default_factory=list)
    degraded_reason: str | None = None
    recovery_actions: list[str] = Field(default_factory=list)
    exposed_capabilities: list[dict[str, Any]] = Field(default_factory=list)
    recent_failures: list[dict[str, Any]] = Field(default_factory=list)
    mcp: dict[str, Any] | None = None


__all__ = [
    "CapabilityStatus",
    "ExtensionLifecycleAuditReportSchema",
    "RuntimeCapabilityItem",
    "RuntimeCapabilityManifestSchema",
    "RuntimeCheckItem",
    "RuntimeDoctorReportSchema",
    "RuntimeFailureAggregateItem",
    "RuntimeRootCauseReportSchema",
    "RuntimeSmokeReportSchema",
    "RuntimeSmokeRequest",
    "RuntimeStatus",
]
