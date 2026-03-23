from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, synonym

from app.core.base_model import BaseModel

from .enums import BuilderSurfaceEnum, ReleaseScopeEnum, TemplateStatusEnum


class WorkflowTemplate(BaseModel):
    __tablename__ = "px_workflow_orchestration_templates"
    __table_args__ = (
        UniqueConstraint("code", name="uq_px_workflow_orchestration_templates_code"),
    )

    __filterable__ = {
        "code": "code",
        "name": "name",
        "status": "status",
        "category": "category",
        "builder_surface": "builder_surface",
        "release_scope": "release_scope",
    }
    __sortable__ = {
        "created_at": "created_at",
        "updated_at": "updated_at",
        "name": "name",
        "code": "code",
        "published_at": "published_at",
    }

    code: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=TemplateStatusEnum.DRAFT.value, index=True)
    builder_surface: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default=BuilderSurfaceEnum.PLATFORM_WORKFLOW_STUDIO.value,
        index=True,
    )
    release_scope: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default=ReleaseScopeEnum.SELECTED_TENANTS.value,
        index=True,
    )
    tags_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    risk_policy_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    contract_summary_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    default_trigger_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    latest_version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latest_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_published_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latest_release_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    published_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(nullable=True)


class WorkflowTemplateVersion(BaseModel):
    __tablename__ = "px_workflow_orchestration_template_versions"
    __table_args__ = (
        UniqueConstraint(
            "template_id",
            "version_no",
            name="uq_px_workflow_orchestration_template_versions_template_version",
        ),
        Index(
            "ix_px_workflow_orchestration_template_versions_published_flags",
            "template_id",
            "is_latest",
            "is_published",
        ),
    )

    template_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("px_workflow_orchestration_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=TemplateStatusEnum.DRAFT.value, index=True)
    snapshot_version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0.0")
    workflow_schema_version: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="1.0.0",
    )
    snapshot_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    snapshot_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    release_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    compiled_at: Mapped[datetime | None] = mapped_column(nullable=True)
    compiled_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(nullable=True)
    published_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_latest: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_by: Mapped[int | None] = mapped_column(Integer, nullable=True)

    workflow_template_id = synonym("template_id")


class WorkflowTemplateNode(BaseModel):
    __tablename__ = "px_workflow_orchestration_template_nodes"
    __table_args__ = (
        UniqueConstraint(
            "template_id",
            "node_key",
            name="uq_px_workflow_orchestration_template_nodes_template_node",
        ),
        Index(
            "ix_px_workflow_orchestration_template_nodes_template_type",
            "template_id",
            "node_type",
        ),
    )

    template_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("px_workflow_orchestration_templates.id", ondelete="CASCADE"),
        nullable=False,
    )
    node_key: Mapped[str] = mapped_column(String(120), nullable=False)
    node_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    timeout_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retry_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    config_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    position_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    input_contract_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    output_contract_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    policy_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class WorkflowTemplateEdge(BaseModel):
    __tablename__ = "px_workflow_orchestration_template_edges"
    __table_args__ = (
        UniqueConstraint(
            "template_id",
            "edge_key",
            name="uq_px_workflow_orchestration_template_edges_template_edge",
        ),
        Index(
            "ix_px_workflow_orchestration_template_edges_template_nodes",
            "template_id",
            "from_node_key",
            "to_node_key",
        ),
    )

    template_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("px_workflow_orchestration_templates.id", ondelete="CASCADE"),
        nullable=False,
    )
    edge_key: Mapped[str] = mapped_column(String(120), nullable=False)
    from_node_key: Mapped[str] = mapped_column(String(120), nullable=False)
    from_port: Mapped[str | None] = mapped_column(String(120), nullable=True)
    to_node_key: Mapped[str] = mapped_column(String(120), nullable=False)
    to_port: Mapped[str | None] = mapped_column(String(120), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    condition_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


__all__ = [
    "WorkflowTemplate",
    "WorkflowTemplateEdge",
    "WorkflowTemplateNode",
    "WorkflowTemplateVersion",
]
