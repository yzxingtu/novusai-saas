import hashlib
import json
from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, synonym

from app.core.base_model import BaseModel

from .enums import (
    ArtifactStatusEnum,
    ArtifactTypeEnum,
    BuilderSurfaceEnum,
    CheckpointTypeEnum,
    EventLevelEnum,
    RunStatusEnum,
    TemplateStatusEnum,
)


def _generate_tenant_workflow_code() -> str:
    return f"wf-{uuid4().hex[:12]}"


def _generate_run_code() -> str:
    return f"run-{uuid4().hex[:12]}"


def _generate_artifact_code() -> str:
    return f"artifact-{uuid4().hex[:12]}"


def _generate_artifact_name() -> str:
    return f"artifact-{uuid4().hex[:8]}"


def _snapshot_hash_from_context(context) -> str:
    snapshot = context.get_current_parameters().get("snapshot_json") or {}
    payload = json.dumps(
        snapshot,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class TenantWorkflow(BaseModel):
    __tablename__ = "px_workflow_orchestration_tenant_workflows"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "code",
            name="uq_px_workflow_orchestration_tenant_workflows_tenant_code",
        ),
        Index(
            "ix_px_workflow_orchestration_tenant_workflows_status",
            "tenant_id",
            "status",
        ),
        Index(
            "ix_px_workflow_orchestration_tenant_workflows_builder",
            "builder_surface",
        ),
    )

    __filterable__ = {
        "tenant_id": "tenant_id",
        "code": "code",
        "name": "name",
        "status": "status",
        "builder_surface": "builder_surface",
    }
    __sortable__ = {
        "created_at": "created_at",
        "updated_at": "updated_at",
        "name": "name",
        "code": "code",
        "published_at": "published_at",
    }

    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False)
    source_template_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_release_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    code: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        default=_generate_tenant_workflow_code,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=TemplateStatusEnum.DRAFT.value)
    mode: Mapped[str] = mapped_column(String(32), nullable=False, default="deterministic")
    editable_level: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="tenant_simple",
    )
    is_simple_builder: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    builder_surface: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default=BuilderSurfaceEnum.TENANT_TEMPLATE_EDITOR.value,
    )
    workflow_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    summary_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    settings_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    latest_version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latest_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_release_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(nullable=True)
    published_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_by: Mapped[int | None] = mapped_column(Integer, nullable=True)


class TenantWorkflowVersion(BaseModel):
    __tablename__ = "px_workflow_orchestration_tenant_workflow_versions"
    __table_args__ = (
        UniqueConstraint(
            "workflow_id",
            "version_no",
            name="uq_px_wo_twf_versions_wf_ver",
        ),
        Index(
            "ix_px_workflow_orchestration_tenant_workflow_versions_status",
            "workflow_id",
            "status",
        ),
        Index(
            "ix_px_wo_twf_versions_snap_hash",
            "snapshot_hash",
        ),
    )

    workflow_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("px_workflow_orchestration_tenant_workflows.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=TemplateStatusEnum.DRAFT.value)
    source_template_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    snapshot_version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0.0")
    workflow_schema_version: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="1.0.0",
    )
    snapshot_hash: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        default=_snapshot_hash_from_context,
    )
    snapshot_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    compiled_at: Mapped[datetime | None] = mapped_column(nullable=True)
    compiled_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(nullable=True)
    published_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_latest: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_by: Mapped[int | None] = mapped_column(Integer, nullable=True)

    tenant_workflow_id = synonym("workflow_id")


class WorkflowRun(BaseModel):
    __tablename__ = "px_workflow_orchestration_runs"
    __table_args__ = (
        UniqueConstraint("code", name="uq_px_workflow_orchestration_runs_code"),
        Index(
            "ix_px_workflow_orchestration_runs_tenant_status",
            "tenant_id",
            "status",
        ),
        Index(
            "ix_px_workflow_orchestration_runs_workflow_version",
            "workflow_id",
            "workflow_version_id",
        ),
        Index(
            "ix_px_workflow_orchestration_runs_trace",
            "trace_id",
        ),
    )

    __filterable__ = {
        "tenant_id": "tenant_id",
        "workflow_id": "workflow_id",
        "workflow_version_id": "workflow_version_id",
        "release_id": "release_id",
        "trigger_id": "trigger_id",
        "status": "status",
    }
    __sortable__ = {
        "created_at": "created_at",
        "updated_at": "updated_at",
        "started_at": "started_at",
        "ended_at": "ended_at",
        "code": "code",
    }

    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False)
    workflow_id: Mapped[int] = mapped_column(Integer, nullable=False)
    workflow_template_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    workflow_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    release_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("px_workflow_orchestration_releases.id", ondelete="SET NULL"),
        nullable=True,
    )
    trigger_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("px_workflow_orchestration_triggers.id", ondelete="SET NULL"),
        nullable=True,
    )
    environment_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("px_workflow_orchestration_environments.id", ondelete="SET NULL"),
        nullable=True,
    )
    parent_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    code: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        default=_generate_run_code,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=RunStatusEnum.PENDING.value)
    entrypoint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    initiated_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    initiated_from: Mapped[str | None] = mapped_column(String(64), nullable=True)
    started_by_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    mode: Mapped[str] = mapped_column(String(32), nullable=False, default="deterministic")
    current_node_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    input_payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    output_payload_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    cost_summary_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    control_envelope_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    budget_snapshot_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    risk_snapshot_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    metrics_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(nullable=True)

    tenant_workflow_id = synonym("workflow_id")
    started_by_id = synonym("initiated_by")
    trigger_source = synonym("initiated_from")
    input_payload = synonym("input_payload_json")
    output_payload = synonym("output_payload_json")
    cost_summary = synonym("cost_summary_json")

    @property
    def current_node_name(self) -> str | None:
        return self.current_node_key

    @property
    def current_step_name(self) -> str | None:
        return self.current_node_key

    @property
    def final_output(self) -> dict | None:
        return self.output_payload_json


class WorkflowNodeRun(BaseModel):
    __tablename__ = "px_workflow_orchestration_node_runs"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "node_key",
            "attempt_no",
            name="uq_px_workflow_orchestration_node_runs_run_node_attempt",
        ),
        Index(
            "ix_px_workflow_orchestration_node_runs_status",
            "tenant_id",
            "status",
        ),
    )

    run_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("px_workflow_orchestration_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parent_node_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    node_key: Mapped[str] = mapped_column(String(120), nullable=False)
    node_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=RunStatusEnum.PENDING.value)
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    executor_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    executor_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    input_envelope_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    output_envelope_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    cost_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    metrics_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(nullable=True)

    workflow_run_id = synonym("run_id")
    input_payload = synonym("input_envelope_json")
    output_payload = synonym("output_envelope_json")
    error_detail = synonym("error_summary")

    @property
    def node_name(self) -> str:
        return self.node_key

    @property
    def node_label(self) -> str:
        return self.node_key


class WorkflowCheckpoint(BaseModel):
    __tablename__ = "px_workflow_orchestration_checkpoints"
    __table_args__ = (
        UniqueConstraint(
            "resume_token",
            name="uq_px_workflow_orchestration_checkpoints_resume_token",
        ),
        Index(
            "ix_px_workflow_orchestration_checkpoints_run_type",
            "run_id",
            "checkpoint_type",
        ),
    )

    run_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("px_workflow_orchestration_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    node_run_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("px_workflow_orchestration_node_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    tenant_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    checkpoint_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default=CheckpointTypeEnum.RUN_START_CHECKPOINT.value,
    )
    resume_token: Mapped[str | None] = mapped_column(String(255), nullable=True)
    state_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    snapshot_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    restored_at: Mapped[datetime | None] = mapped_column(nullable=True)

    workflow_run_id = synonym("run_id")
    workflow_node_run_id = synonym("node_run_id")
    snapshot_payload = synonym("snapshot_json")


class WorkflowEvent(BaseModel):
    __tablename__ = "px_workflow_orchestration_events"
    __table_args__ = (
        Index(
            "ix_px_workflow_orchestration_events_run_type",
            "run_id",
            "event_type",
        ),
        Index(
            "ix_px_workflow_orchestration_events_trace",
            "trace_id",
        ),
    )

    run_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("px_workflow_orchestration_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    node_run_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("px_workflow_orchestration_node_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    tenant_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    event_level: Mapped[str] = mapped_column(String(32), nullable=False, default=EventLevelEnum.INFO.value)
    event_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status_from: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status_to: Mapped[str | None] = mapped_column(String(32), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    payload_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    occurred_at: Mapped[datetime | None] = mapped_column(nullable=True)

    workflow_run_id = synonym("run_id")
    workflow_node_run_id = synonym("node_run_id")
    detail = synonym("payload_json")


class WorkflowArtifact(BaseModel):
    __tablename__ = "px_workflow_orchestration_artifacts"
    __table_args__ = (
        UniqueConstraint("code", name="uq_px_workflow_orchestration_artifacts_code"),
        Index(
            "ix_px_workflow_orchestration_artifacts_run_status",
            "run_id",
            "status",
        ),
        Index(
            "ix_px_workflow_orchestration_artifacts_type_visibility",
            "artifact_type",
            "visibility_scope",
        ),
        Index(
            "ix_px_workflow_orchestration_artifacts_hash",
            "content_hash",
        ),
    )

    __filterable__ = {
        "tenant_id": "tenant_id",
        "run_id": "run_id",
        "workflow_id": "workflow_id",
        "artifact_type": "artifact_type",
        "status": "status",
    }
    __sortable__ = {
        "created_at": "created_at",
        "updated_at": "updated_at",
        "ready_at": "ready_at",
        "code": "code",
        "size_bytes": "size_bytes",
    }

    tenant_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    run_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("px_workflow_orchestration_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    node_run_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("px_workflow_orchestration_node_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    workflow_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    workflow_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    code: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        default=_generate_artifact_code,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, default=_generate_artifact_name)
    artifact_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default=ArtifactTypeEnum.DRAFT.value,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=ArtifactStatusEnum.DRAFT.value,
    )
    schema_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    storage_uri: Mapped[str | None] = mapped_column(String(500), nullable=True)
    storage_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    content_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    visibility_scope: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        default="tenant_visible",
    )
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    feedback_summary: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    download_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    retention_policy_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    ready_at: Mapped[datetime | None] = mapped_column(nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(nullable=True)

    workflow_run_id = synonym("run_id")
    workflow_node_run_id = synonym("node_run_id")
    title = synonym("name")
    visibility = synonym("visibility_scope")
    hash = synonym("content_hash")


__all__ = [
    "TenantWorkflow",
    "TenantWorkflowVersion",
    "WorkflowArtifact",
    "WorkflowCheckpoint",
    "WorkflowEvent",
    "WorkflowNodeRun",
    "WorkflowRun",
]
