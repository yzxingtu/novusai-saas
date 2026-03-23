from datetime import datetime
from typing import Any

from pydantic import Field

from app.core.base_schema import BaseCreateSchema, BaseResponseSchema


class PublishTemplateRequestSchema(BaseCreateSchema):
    version_id: int | None = None
    release_scope: str = "selected_tenants"
    channel: str = "stable"
    environment_code: str = "prod_env"
    rollout_json: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None
    change_types_json: list[str] = Field(default_factory=lambda: ["workflow_definition_change"])
    validation_result_json: dict[str, Any] = Field(default_factory=dict)
    risk_level: str | None = None


class RollbackReleaseRequestSchema(BaseCreateSchema):
    target_release_id: int | None = None
    notes: str | None = None


class WorkflowEnvironmentSchema(BaseResponseSchema):
    code: str
    name: str
    description: str | None = None
    scope: str
    tenant_id: int | None = None
    status: str
    sort_order: int
    is_system: bool
    capability_boundary_json: dict[str, Any] = Field(default_factory=dict)
    rollout_policy_json: dict[str, Any] = Field(default_factory=dict)
    created_by: int | None = None
    updated_by: int | None = None


class WorkflowChangeSetSchema(BaseResponseSchema):
    code: str
    workflow_kind: str
    workflow_id: int
    environment_id: int | None = None
    status: str
    risk_level: str | None = None
    change_types_json: list[Any] = Field(default_factory=list)
    impact_summary_json: dict[str, Any] = Field(default_factory=dict)
    dependency_snapshot_json: dict[str, Any] = Field(default_factory=dict)
    validation_result_json: dict[str, Any] = Field(default_factory=dict)
    rollback_plan_json: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None
    created_by: int | None = None
    updated_by: int | None = None


class WorkflowTriggerSchema(BaseResponseSchema):
    workflow_kind: str
    workflow_id: int
    workflow_version_id: int | None = None
    environment_id: int | None = None
    owner_type: str
    owner_tenant_id: int | None = None
    trigger_type: str
    status: str
    config_json: dict[str, Any] = Field(default_factory=dict)
    auth_config_json: dict[str, Any] = Field(default_factory=dict)
    mapping_json: dict[str, Any] = Field(default_factory=dict)
    risk_guard_json: dict[str, Any] = Field(default_factory=dict)
    last_triggered_at: datetime | None = None
    next_trigger_at: datetime | None = None
    created_by: int | None = None
    updated_by: int | None = None


class WorkflowReleaseSchema(BaseResponseSchema):
    code: str
    workflow_kind: str
    workflow_id: int
    workflow_version_id: int
    change_set_id: int | None = None
    environment_id: int | None = None
    environment_code: str | None = None
    release_scope: str
    channel: str
    status: str
    rollout_json: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None
    rollback_of_release_id: int | None = None
    rollback_target_release_id: int | None = None
    published_by: int | None = None
    reviewed_by: int | None = None
    published_at: datetime | None = None
    reviewed_at: datetime | None = None
    created_by: int | None = None
    updated_by: int | None = None


__all__ = [
    "PublishTemplateRequestSchema",
    "RollbackReleaseRequestSchema",
    "WorkflowChangeSetSchema",
    "WorkflowEnvironmentSchema",
    "WorkflowReleaseSchema",
    "WorkflowTriggerSchema",
]
