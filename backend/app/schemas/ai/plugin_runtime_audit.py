"""
Plugin runtime audit schemas / 插件运行时审计 Schema。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from app.core.base_schema import BaseSchema

PluginAuditStatus = Literal["available", "degraded", "unavailable", "not_implemented"]
PluginRuntimeKind = Literal["plugin"]


class ExtensionLifecycleAuditStageResult(BaseSchema):
    stage: str
    status: PluginAuditStatus
    reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExtensionLifecycleRecentFailure(BaseSchema):
    source: str
    code: str
    message: str
    occurred_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExtensionLifecycleExposedCapability(BaseSchema):
    name: str
    kind: str
    status: PluginAuditStatus
    reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    source: str | None = None


class ExtensionLifecycleAuditReport(BaseSchema):
    runtime_kind: PluginRuntimeKind = "plugin"
    target: dict[str, Any] = Field(default_factory=dict)
    stage_results: list[ExtensionLifecycleAuditStageResult] = Field(
        default_factory=list
    )
    degraded_reason: str | None = None
    recovery_actions: list[str] = Field(default_factory=list)
    exposed_capabilities: list[ExtensionLifecycleExposedCapability] = Field(
        default_factory=list
    )
    recent_failures: list[ExtensionLifecycleRecentFailure] = Field(default_factory=list)


__all__ = [
    "ExtensionLifecycleAuditReport",
    "ExtensionLifecycleAuditStageResult",
    "ExtensionLifecycleExposedCapability",
    "ExtensionLifecycleRecentFailure",
    "PluginAuditStatus",
    "PluginRuntimeKind",
]
