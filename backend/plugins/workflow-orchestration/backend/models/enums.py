from app.enums.base import LabeledStrEnum


class TemplateStatusEnum(LabeledStrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class ReleaseStatusEnum(LabeledStrEnum):
    DRAFT = "draft"
    REVIEWING = "reviewing"
    APPROVED = "approved"
    PUBLISHED = "published"
    DISABLED = "disabled"
    DEPRECATED = "deprecated"
    ROLLED_BACK = "rolled_back"


class ReleaseScopeEnum(LabeledStrEnum):
    PLATFORM_CATALOG = "platform_catalog"
    SELECTED_TENANTS = "selected_tenants"
    TENANT_PRIVATE = "tenant_private"


class ReleaseChannelEnum(LabeledStrEnum):
    STABLE = "stable"
    BETA = "beta"
    INTERNAL = "internal"


class WorkflowKindEnum(LabeledStrEnum):
    TEMPLATE = "template"
    TENANT_WORKFLOW = "tenant_workflow"


class BuilderSurfaceEnum(LabeledStrEnum):
    PLATFORM_WORKFLOW_STUDIO = "platform_workflow_studio"
    TENANT_TEMPLATE_EDITOR = "tenant_template_editor"
    TENANT_SIMPLE_BUILDER = "tenant_simple_builder"


class TriggerTypeEnum(LabeledStrEnum):
    MANUAL = "manual"
    SCHEDULE = "schedule"
    API = "api"
    WEBHOOK = "webhook"
    EVENT = "event"


class TriggerStatusEnum(LabeledStrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    DISABLED = "disabled"


class EnvironmentScopeEnum(LabeledStrEnum):
    PLATFORM = "platform"
    TENANT = "tenant"


class EnvironmentStatusEnum(LabeledStrEnum):
    PROVISIONED = "provisioned"
    ACTIVATED = "activated"
    PILOT = "pilot"
    LIVE = "live"
    SUSPENDED = "suspended"


class ChangeSetStatusEnum(LabeledStrEnum):
    DRAFT = "draft"
    REVIEWING = "reviewing"
    APPROVED = "approved"
    PUBLISHED = "published"
    ROLLED_BACK = "rolled_back"
    ARCHIVED = "archived"


class ConfigScopeEnum(LabeledStrEnum):
    GLOBAL = "global"
    TENANT_DEFAULT = "tenant_default"


class RunStatusEnum(LabeledStrEnum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_HUMAN = "waiting_human"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ArtifactTypeEnum(LabeledStrEnum):
    DRAFT = "draft"
    REPORT = "report"
    RECOMMENDATION = "recommendation"
    APPROVAL_PACKET = "approval_packet"
    EVIDENCE_BUNDLE = "evidence_bundle"
    DATASET = "dataset"
    MEDIA = "media"


class ArtifactStatusEnum(LabeledStrEnum):
    DRAFT = "draft"
    READY = "ready"
    ARCHIVED = "archived"
    FAILED = "failed"


class EventLevelEnum(LabeledStrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    AUDIT = "audit"


class CheckpointTypeEnum(LabeledStrEnum):
    RUN_START_CHECKPOINT = "run_start_checkpoint"
    NODE_INPUT_CHECKPOINT = "node_input_checkpoint"
    NODE_OUTPUT_CHECKPOINT = "node_output_checkpoint"
    APPROVAL_WAIT_CHECKPOINT = "approval_wait_checkpoint"
    EXTERNAL_WRITE_PREFLIGHT_CHECKPOINT = "external_write_preflight_checkpoint"
    EXTERNAL_WRITE_RECEIPT_CHECKPOINT = "external_write_receipt_checkpoint"
    MANUAL_HANDOVER_CHECKPOINT = "manual_handover_checkpoint"


__all__ = [
    "ArtifactStatusEnum",
    "ArtifactTypeEnum",
    "BuilderSurfaceEnum",
    "ChangeSetStatusEnum",
    "CheckpointTypeEnum",
    "ConfigScopeEnum",
    "EnvironmentScopeEnum",
    "EnvironmentStatusEnum",
    "EventLevelEnum",
    "ReleaseChannelEnum",
    "ReleaseScopeEnum",
    "ReleaseStatusEnum",
    "RunStatusEnum",
    "TemplateStatusEnum",
    "TriggerStatusEnum",
    "TriggerTypeEnum",
    "WorkflowKindEnum",
]
