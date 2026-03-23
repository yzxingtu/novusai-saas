from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel

from .enums import (
    ChangeSetStatusEnum,
    ConfigScopeEnum,
    EnvironmentScopeEnum,
    EnvironmentStatusEnum,
    ReleaseChannelEnum,
    ReleaseScopeEnum,
    ReleaseStatusEnum,
    TriggerStatusEnum,
    TriggerTypeEnum,
    WorkflowKindEnum,
)


class WorkflowEnvironment(BaseModel):
    __tablename__ = "px_workflow_orchestration_environments"
    __table_args__ = (
        UniqueConstraint("code", name="uq_px_workflow_orchestration_environments_code"),
        Index(
            "ix_px_workflow_orchestration_environments_scope_status",
            "scope",
            "status",
        ),
    )

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    scope: Mapped[str] = mapped_column(String(32), nullable=False, default=EnvironmentScopeEnum.PLATFORM.value)
    tenant_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=EnvironmentStatusEnum.PROVISIONED.value)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    capability_boundary_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    rollout_policy_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_by: Mapped[int | None] = mapped_column(Integer, nullable=True)


class WorkflowChangeSet(BaseModel):
    __tablename__ = "px_workflow_orchestration_change_sets"
    __table_args__ = (
        UniqueConstraint("code", name="uq_px_workflow_orchestration_change_sets_code"),
        Index(
            "ix_px_workflow_orchestration_change_sets_workflow_status",
            "workflow_kind",
            "workflow_id",
            "status",
        ),
    )

    code: Mapped[str] = mapped_column(String(120), nullable=False)
    workflow_kind: Mapped[str] = mapped_column(String(32), nullable=False, default=WorkflowKindEnum.TEMPLATE.value)
    workflow_id: Mapped[int] = mapped_column(Integer, nullable=False)
    environment_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("px_workflow_orchestration_environments.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=ChangeSetStatusEnum.DRAFT.value)
    risk_level: Mapped[str | None] = mapped_column(String(32), nullable=True)
    change_types_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    impact_summary_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    dependency_snapshot_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    validation_result_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    rollback_plan_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_by: Mapped[int | None] = mapped_column(Integer, nullable=True)


class WorkflowTrigger(BaseModel):
    __tablename__ = "px_workflow_orchestration_triggers"
    __table_args__ = (
        Index(
            "ix_px_workflow_orchestration_triggers_workflow_status",
            "workflow_kind",
            "workflow_id",
            "status",
        ),
        Index(
            "ix_px_workflow_orchestration_triggers_type_owner",
            "trigger_type",
            "owner_tenant_id",
        ),
    )

    workflow_kind: Mapped[str] = mapped_column(String(32), nullable=False, default=WorkflowKindEnum.TEMPLATE.value)
    workflow_id: Mapped[int] = mapped_column(Integer, nullable=False)
    workflow_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    environment_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("px_workflow_orchestration_environments.id", ondelete="SET NULL"),
        nullable=True,
    )
    owner_type: Mapped[str] = mapped_column(String(32), nullable=False, default="platform")
    owner_tenant_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trigger_type: Mapped[str] = mapped_column(String(32), nullable=False, default=TriggerTypeEnum.MANUAL.value)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=TriggerStatusEnum.DRAFT.value)
    config_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    auth_config_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    mapping_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    risk_guard_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    last_triggered_at: Mapped[datetime | None] = mapped_column(nullable=True)
    next_trigger_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_by: Mapped[int | None] = mapped_column(Integer, nullable=True)


class WorkflowRelease(BaseModel):
    __tablename__ = "px_workflow_orchestration_releases"
    __table_args__ = (
        UniqueConstraint("code", name="uq_px_workflow_orchestration_releases_code"),
        Index(
            "ix_px_workflow_orchestration_releases_workflow_status",
            "workflow_kind",
            "workflow_id",
            "status",
        ),
        Index(
            "ix_px_workflow_orchestration_releases_scope_channel",
            "release_scope",
            "channel",
        ),
        Index(
            "ix_px_workflow_orchestration_releases_published_at",
            "published_at",
        ),
    )

    __filterable__ = {
        "workflow_kind": "workflow_kind",
        "workflow_id": "workflow_id",
        "status": "status",
        "release_scope": "release_scope",
        "channel": "channel",
        "environment_code": "environment_code",
    }
    __sortable__ = {
        "created_at": "created_at",
        "updated_at": "updated_at",
        "published_at": "published_at",
        "code": "code",
    }

    code: Mapped[str] = mapped_column(String(120), nullable=False)
    workflow_kind: Mapped[str] = mapped_column(String(32), nullable=False, default=WorkflowKindEnum.TEMPLATE.value)
    workflow_id: Mapped[int] = mapped_column(Integer, nullable=False)
    workflow_version_id: Mapped[int] = mapped_column(Integer, nullable=False)
    change_set_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("px_workflow_orchestration_change_sets.id", ondelete="SET NULL"),
        nullable=True,
    )
    environment_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("px_workflow_orchestration_environments.id", ondelete="SET NULL"),
        nullable=True,
    )
    environment_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    release_scope: Mapped[str] = mapped_column(String(64), nullable=False, default=ReleaseScopeEnum.SELECTED_TENANTS.value)
    channel: Mapped[str] = mapped_column(String(32), nullable=False, default=ReleaseChannelEnum.STABLE.value)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=ReleaseStatusEnum.DRAFT.value)
    rollout_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    rollback_of_release_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rollback_target_release_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    published_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_by: Mapped[int | None] = mapped_column(Integer, nullable=True)


class WorkflowModuleConfig(BaseModel):
    __tablename__ = "px_workflow_orchestration_module_configs"
    __table_args__ = (
        Index(
            "uq_px_workflow_orchestration_module_configs_global",
            "config_scope",
            "config_key",
            unique=True,
            postgresql_where=text("tenant_id IS NULL"),
        ),
        Index(
            "uq_px_workflow_orchestration_module_configs_tenant",
            "config_scope",
            "config_key",
            "tenant_id",
            unique=True,
            postgresql_where=text("tenant_id IS NOT NULL"),
        ),
    )

    config_scope: Mapped[str] = mapped_column(String(32), nullable=False, default=ConfigScopeEnum.GLOBAL.value)
    config_key: Mapped[str] = mapped_column(String(120), nullable=False)
    tenant_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    settings_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_by: Mapped[int | None] = mapped_column(Integer, nullable=True)


__all__ = [
    "WorkflowChangeSet",
    "WorkflowEnvironment",
    "WorkflowModuleConfig",
    "WorkflowRelease",
    "WorkflowTrigger",
]
