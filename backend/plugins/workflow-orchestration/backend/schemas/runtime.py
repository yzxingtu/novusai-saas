from datetime import datetime
from typing import Any

from pydantic import Field

from app.core.base_schema import BaseResponseSchema, TenantResponseSchema


class TenantWorkflowSchema(TenantResponseSchema):
    source_template_id: int | None = None
    source_release_id: int | None = None
    code: str
    name: str
    description: str | None = None
    status: str
    builder_surface: str
    settings_json: dict[str, Any] = Field(default_factory=dict)
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    latest_version_no: int
    latest_version_id: int | None = None
    active_version_id: int | None = None
    current_release_id: int | None = None
    published_at: datetime | None = None
    published_by: int | None = None
    created_by: int | None = None
    updated_by: int | None = None


class TenantWorkflowVersionSchema(BaseResponseSchema):
    workflow_id: int
    version_no: int
    status: str
    source_template_version_id: int | None = None
    snapshot_version: str
    workflow_schema_version: str
    snapshot_hash: str
    snapshot_json: dict[str, Any] = Field(default_factory=dict)
    change_summary: str | None = None
    compiled_at: datetime | None = None
    compiled_by: int | None = None
    published_at: datetime | None = None
    published_by: int | None = None
    is_latest: bool
    is_published: bool
    created_by: int | None = None
    updated_by: int | None = None


class WorkflowRunSchema(TenantResponseSchema):
    workflow_id: int
    workflow_version_id: int
    release_id: int | None = None
    trigger_id: int | None = None
    environment_id: int | None = None
    parent_run_id: int | None = None
    code: str
    status: str
    entrypoint: str | None = None
    initiated_by: int | None = None
    initiated_from: str | None = None
    current_node_key: str | None = None
    trace_id: str | None = None
    idempotency_key: str | None = None
    retry_count: int
    input_payload_json: dict[str, Any] = Field(default_factory=dict)
    output_payload_json: dict[str, Any] = Field(default_factory=dict)
    control_envelope_json: dict[str, Any] = Field(default_factory=dict)
    budget_snapshot_json: dict[str, Any] = Field(default_factory=dict)
    risk_snapshot_json: dict[str, Any] = Field(default_factory=dict)
    metrics_json: dict[str, Any] = Field(default_factory=dict)
    error_summary: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    last_heartbeat_at: datetime | None = None


class WorkflowNodeRunSchema(TenantResponseSchema):
    run_id: int
    parent_node_run_id: int | None = None
    node_key: str
    node_type: str
    status: str
    attempt_no: int
    trace_id: str | None = None
    input_envelope_json: dict[str, Any] = Field(default_factory=dict)
    output_envelope_json: dict[str, Any] = Field(default_factory=dict)
    cost_json: dict[str, Any] = Field(default_factory=dict)
    metrics_json: dict[str, Any] = Field(default_factory=dict)
    error_summary: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None


class WorkflowCheckpointSchema(TenantResponseSchema):
    run_id: int
    node_run_id: int | None = None
    checkpoint_type: str
    resume_token: str | None = None
    state_hash: str | None = None
    snapshot_json: dict[str, Any] = Field(default_factory=dict)
    created_by: int | None = None
    expires_at: datetime | None = None
    restored_at: datetime | None = None


class WorkflowEventSchema(TenantResponseSchema):
    run_id: int
    node_run_id: int | None = None
    event_type: str
    event_level: str
    event_code: str | None = None
    message: str | None = None
    trace_id: str | None = None
    payload_json: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime | None = None


class WorkflowArtifactSchema(TenantResponseSchema):
    run_id: int
    node_run_id: int | None = None
    workflow_id: int
    workflow_version_id: int
    code: str
    name: str
    artifact_type: str
    status: str
    schema_ref: str | None = None
    mime_type: str | None = None
    storage_uri: str | None = None
    summary: str | None = None
    visibility_scope: str | None = None
    size_bytes: int | None = None
    content_hash: str | None = None
    retention_policy_json: dict[str, Any] = Field(default_factory=dict)
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    ready_at: datetime | None = None
    expires_at: datetime | None = None


__all__ = [
    "TenantWorkflowSchema",
    "TenantWorkflowVersionSchema",
    "WorkflowArtifactSchema",
    "WorkflowCheckpointSchema",
    "WorkflowEventSchema",
    "WorkflowNodeRunSchema",
    "WorkflowRunSchema",
]

