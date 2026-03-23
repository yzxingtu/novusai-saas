from datetime import datetime
from typing import Any

from pydantic import Field

from app.core.base_schema import BaseCreateSchema, BaseResponseSchema, BaseUpdateSchema


class WorkflowNodeSchema(BaseCreateSchema):
    node_key: str
    node_type: str
    title: str
    description: str | None = None
    sort_order: int = 0
    timeout_minutes: int | None = None
    retry_limit: int | None = None
    config_json: dict[str, Any] = Field(default_factory=dict)
    position_json: dict[str, Any] = Field(default_factory=dict)
    input_contract_json: dict[str, Any] = Field(default_factory=dict)
    output_contract_json: dict[str, Any] = Field(default_factory=dict)
    policy_json: dict[str, Any] = Field(default_factory=dict)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class WorkflowEdgeSchema(BaseCreateSchema):
    edge_key: str
    from_node_key: str
    from_port: str | None = None
    to_node_key: str
    to_port: str | None = None
    sort_order: int = 0
    condition_json: dict[str, Any] = Field(default_factory=dict)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class WorkflowGraphSchema(BaseCreateSchema):
    nodes: list[WorkflowNodeSchema] = Field(default_factory=list)
    edges: list[WorkflowEdgeSchema] = Field(default_factory=list)


class WorkflowSnapshotSchema(BaseCreateSchema):
    snapshot_version: str = "1.0.0"
    workflow_schema_version: str = "1.0.0"
    contract_refs: list[dict[str, Any]] = Field(default_factory=list)
    control_envelope_schema: dict[str, Any] = Field(default_factory=dict)
    graph: WorkflowGraphSchema = Field(default_factory=WorkflowGraphSchema)
    entrypoints: list[dict[str, Any]] = Field(default_factory=list)
    defaults: dict[str, Any] = Field(default_factory=dict)
    risk_policy_snapshot: dict[str, Any] = Field(default_factory=dict)
    trigger_snapshot: dict[str, Any] = Field(default_factory=dict)
    artifact_contracts: list[dict[str, Any]] = Field(default_factory=list)
    output_contracts: list[dict[str, Any]] = Field(default_factory=list)
    builder_surface: str = "platform_workflow_studio"
    compiled_at: datetime | None = None
    compiled_by: int | None = None


class CreateTemplateRequestSchema(BaseCreateSchema):
    code: str
    name: str
    description: str | None = None
    category: str | None = None
    status: str = "draft"
    builder_surface: str = "platform_workflow_studio"
    release_scope: str = "selected_tenants"
    tags_json: list[str] = Field(default_factory=list)
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    risk_policy_json: dict[str, Any] = Field(default_factory=dict)
    contract_summary_json: dict[str, Any] = Field(default_factory=dict)
    default_trigger_json: dict[str, Any] = Field(default_factory=dict)
    snapshot: WorkflowSnapshotSchema
    change_summary: str | None = None
    release_notes: str | None = None


class UpdateTemplateRequestSchema(BaseUpdateSchema):
    name: str | None = None
    description: str | None = None
    category: str | None = None
    status: str | None = None
    builder_surface: str | None = None
    release_scope: str | None = None
    tags_json: list[str] | None = None
    metadata_json: dict[str, Any] | None = None
    risk_policy_json: dict[str, Any] | None = None
    contract_summary_json: dict[str, Any] | None = None
    default_trigger_json: dict[str, Any] | None = None
    snapshot: WorkflowSnapshotSchema | None = None
    change_summary: str | None = None
    release_notes: str | None = None
    create_version: bool = True


class WorkflowTemplateListItemSchema(BaseResponseSchema):
    code: str
    name: str
    description: str | None = None
    category: str | None = None
    status: str
    builder_surface: str
    release_scope: str
    tags_json: list[Any] = Field(default_factory=list)
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    risk_policy_json: dict[str, Any] = Field(default_factory=dict)
    contract_summary_json: dict[str, Any] = Field(default_factory=dict)
    default_trigger_json: dict[str, Any] = Field(default_factory=dict)
    latest_version_no: int
    latest_version_id: int | None = None
    current_published_version_id: int | None = None
    latest_release_id: int | None = None
    created_by: int | None = None
    updated_by: int | None = None
    published_by: int | None = None
    published_at: datetime | None = None


class WorkflowTemplateVersionSchema(BaseResponseSchema):
    template_id: int
    version_no: int
    status: str
    snapshot_version: str
    workflow_schema_version: str
    snapshot_hash: str
    snapshot_json: dict[str, Any] = Field(default_factory=dict)
    change_summary: str | None = None
    release_notes: str | None = None
    compiled_at: datetime | None = None
    compiled_by: int | None = None
    published_at: datetime | None = None
    published_by: int | None = None
    is_latest: bool
    is_published: bool
    created_by: int | None = None
    updated_by: int | None = None


class WorkflowTemplateNodeResponseSchema(BaseResponseSchema):
    template_id: int
    node_key: str
    node_type: str
    title: str
    description: str | None = None
    sort_order: int
    timeout_minutes: int | None = None
    retry_limit: int | None = None
    config_json: dict[str, Any] = Field(default_factory=dict)
    position_json: dict[str, Any] = Field(default_factory=dict)
    input_contract_json: dict[str, Any] = Field(default_factory=dict)
    output_contract_json: dict[str, Any] = Field(default_factory=dict)
    policy_json: dict[str, Any] = Field(default_factory=dict)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class WorkflowTemplateEdgeResponseSchema(BaseResponseSchema):
    template_id: int
    edge_key: str
    from_node_key: str
    from_port: str | None = None
    to_node_key: str
    to_port: str | None = None
    sort_order: int
    condition_json: dict[str, Any] = Field(default_factory=dict)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class WorkflowTemplateDetailSchema(WorkflowTemplateListItemSchema):
    nodes: list[WorkflowTemplateNodeResponseSchema] = Field(default_factory=list)
    edges: list[WorkflowTemplateEdgeResponseSchema] = Field(default_factory=list)
    latest_version: WorkflowTemplateVersionSchema | None = None
    published_version: WorkflowTemplateVersionSchema | None = None
    latest_release: dict[str, Any] | None = None
    version_count: int = 0


__all__ = [
    "CreateTemplateRequestSchema",
    "UpdateTemplateRequestSchema",
    "WorkflowEdgeSchema",
    "WorkflowGraphSchema",
    "WorkflowNodeSchema",
    "WorkflowSnapshotSchema",
    "WorkflowTemplateDetailSchema",
    "WorkflowTemplateEdgeResponseSchema",
    "WorkflowTemplateListItemSchema",
    "WorkflowTemplateNodeResponseSchema",
    "WorkflowTemplateVersionSchema",
]

