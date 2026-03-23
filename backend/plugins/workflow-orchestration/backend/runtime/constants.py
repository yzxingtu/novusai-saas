from __future__ import annotations

PLUGIN_NAME = "workflow-orchestration"

DEFAULT_PAGE_NUMBER = 1
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
DEFAULT_HOME_LIMIT = 5
DEFAULT_RUN_TIMEOUT_MINUTES = 30
DEFAULT_ARTIFACT_PREVIEW_BUDGET = 2048
DEFAULT_ARTIFACT_RETENTION_DAYS = 30

RUN_STATUSES = (
    "pending",
    "queued",
    "validating",
    "planning",
    "running",
    "waiting_human",
    "waiting_approval",
    "waiting_input",
    "paused",
    "recovering",
    "compensating",
    "succeeded",
    "completed",
    "partially_completed",
    "failed",
    "cancelled",
)

RUN_STATUS_BUCKETS = {
    "pending": "pending",
    "queued": "pending",
    "validating": "pending",
    "planning": "pending",
    "running": "running",
    "waiting_human": "waiting_human",
    "waiting_approval": "waiting_human",
    "waiting_input": "waiting_human",
    "paused": "waiting_human",
    "recovering": "running",
    "compensating": "running",
    "succeeded": "succeeded",
    "completed": "succeeded",
    "partially_completed": "succeeded",
    "failed": "failed",
    "cancelled": "cancelled",
}

RUN_TERMINAL_STATUSES = {
    "completed",
    "partially_completed",
    "failed",
    "cancelled",
}

RUN_ACTIVE_STATUSES = {
    "pending",
    "queued",
    "validating",
    "planning",
    "running",
    "waiting_human",
    "waiting_approval",
    "waiting_input",
    "paused",
    "recovering",
    "compensating",
}

RUN_ACTIONS_BY_STATUS = {
    "pending": ("terminate",),
    "queued": ("terminate",),
    "validating": ("terminate",),
    "planning": ("terminate",),
    "running": ("pause", "terminate"),
    "waiting_human": ("resume", "terminate"),
    "waiting_approval": ("resume", "terminate"),
    "waiting_input": ("resume", "terminate"),
    "paused": ("resume", "terminate"),
    "recovering": ("terminate",),
    "compensating": ("terminate",),
    "succeeded": ("replay",),
    "completed": ("replay",),
    "partially_completed": ("recover", "replay"),
    "failed": ("retry", "recover", "replay"),
    "cancelled": ("replay",),
}

NODE_RUN_STATUSES = (
    "pending",
    "ready",
    "running",
    "waiting_approval",
    "waiting_input",
    "retry_scheduled",
    "succeeded",
    "failed_retryable",
    "failed_terminal",
    "skipped",
    "compensated",
    "cancelled",
)

NODE_RUN_STATUS_BUCKETS = {
    "pending": "pending",
    "ready": "pending",
    "running": "running",
    "waiting_approval": "waiting_human",
    "waiting_input": "waiting_human",
    "retry_scheduled": "pending",
    "succeeded": "succeeded",
    "failed_retryable": "failed",
    "failed_terminal": "failed",
    "skipped": "succeeded",
    "compensated": "succeeded",
    "cancelled": "cancelled",
}

NODE_TERMINAL_STATUSES = {
    "succeeded",
    "failed_retryable",
    "failed_terminal",
    "skipped",
    "compensated",
    "cancelled",
}

CHECKPOINT_TYPES = (
    "run_start_checkpoint",
    "node_input_checkpoint",
    "node_output_checkpoint",
    "approval_wait_checkpoint",
    "external_write_preflight_checkpoint",
    "external_write_receipt_checkpoint",
    "manual_handover_checkpoint",
)

EVENT_TYPES = (
    "run_created",
    "run_status_changed",
    "node_bootstrapped",
    "node_status_changed",
    "checkpoint_recorded",
    "artifact_recorded",
    "recovery_requested",
    "recovery_completed",
    "run_timed_out",
    "artifact_feedback_submitted",
    "artifact_retention_cleaned",
)

ARTIFACT_TYPES = (
    "prompt",
    "tool_result",
    "search_result",
    "analysis",
    "action_preview",
    "approval_packet",
    "report",
    "dataset",
    "draft",
    "evidence_bundle",
    "media",
    "recommendation",
)

ARTIFACT_STATUSES = (
    "draft",
    "ready",
    "adopted",
    "rejected",
    "archived",
    "expired",
)

ARTIFACT_ACTIONS_BY_STATUS = {
    "draft": ("feedback",),
    "ready": ("feedback", "download"),
    "adopted": ("download",),
    "rejected": ("feedback", "download"),
    "archived": ("download",),
    "expired": (),
}

ARTIFACT_VISIBILITIES = (
    "internal",
    "tenant_visible",
    "approval_only",
)

TRIGGER_SOURCES = (
    "manual",
    "schedule",
    "api",
    "webhook",
    "event",
)

WORKFLOW_MODES = (
    "deterministic",
    "hybrid",
    "agentic",
)

WORKFLOW_STATUSES = (
    "draft",
    "published",
    "disabled",
)

WORKFLOW_EDITABLE_LEVELS = (
    "tenant_simple",
    "managed_locked",
    "managed_partial",
)

STARTED_BY_TYPES = (
    "platform_admin",
    "tenant_admin",
    "system",
)

EXECUTOR_TYPES = (
    "llm",
    "tool",
    "planner",
    "approval",
    "system",
)

HOME_TODO_BUCKETS = (
    "approval_todo",
    "recovery_todo",
    "artifact_review_todo",
    "context_fix_todo",
    "activation_todo",
    "quota_warning_todo",
)

TASK_NAMES = (
    "run_timeout_sweeper",
    "run_retry_dispatcher",
    "artifact_retention",
)
