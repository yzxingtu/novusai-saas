from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.core.base_model import utc_now
from app.plugins.module_loader import load_plugin_module

PLUGIN_NAME = "workflow-orchestration"
DEFAULT_ARTIFACT_PREVIEW_BUDGET = 2048


def _constants():
    module = load_plugin_module(PLUGIN_NAME, "runtime.constants")
    if module is None:
        raise RuntimeError("workflow runtime constants module is unavailable")
    return module


def _model_access():
    module = load_plugin_module(PLUGIN_NAME, "runtime.model_access")
    if module is None:
        raise RuntimeError("workflow runtime model_access module is unavailable")
    return module


def _state_machine():
    module = load_plugin_module(PLUGIN_NAME, "runtime.state_machine")
    if module is None:
        raise RuntimeError("workflow runtime state_machine module is unavailable")
    return module


def to_iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    return str(value)


def summarize_payload(payload: Any, budget: int = DEFAULT_ARTIFACT_PREVIEW_BUDGET) -> str | None:
    if payload in (None, "", {}, []):
        return None
    if isinstance(payload, str):
        return payload[:budget]
    try:
        rendered = json.dumps(payload, ensure_ascii=False, default=str)
    except Exception:
        rendered = str(payload)
    return rendered[:budget]


def _dict_value(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def serialize_tenant_workflow(workflow: Any) -> dict[str, Any]:
    first_attr = _model_access().first_attr
    summary = _dict_value(first_attr(workflow, ("summary_json",), {}) or {})
    source_template_id = first_attr(workflow, ("source_template_id",))
    builder_surface = first_attr(workflow, ("builder_surface",))
    builder_mode = (
        "copied_from_template"
        if source_template_id
        else builder_surface
        or (
            "tenant_simple_builder"
            if bool(first_attr(workflow, ("is_simple_builder",), False))
            else "tenant_template_editor"
        )
    )
    return {
        "id": first_attr(workflow, ("id",)),
        "tenant_id": first_attr(workflow, ("tenant_id",)),
        "source_template_id": source_template_id,
        "source_release_id": first_attr(workflow, ("source_release_id",)),
        "code": first_attr(workflow, ("code",)),
        "name": first_attr(workflow, ("name",), ""),
        "description": first_attr(workflow, ("description",)),
        "mode": first_attr(workflow, ("mode",)),
        "status": first_attr(workflow, ("status",)),
        "editable_level": first_attr(workflow, ("editable_level",)),
        "is_simple_builder": bool(first_attr(workflow, ("is_simple_builder",), False)),
        "builder_surface": builder_surface,
        "builder_mode": builder_mode,
        "risk_level": summary.get("risk_level") if isinstance(summary, dict) else None,
        "workflow_summary": summary,
        "workflow_json": _dict_value(first_attr(workflow, ("workflow_json",), {}) or {}),
        "summary_json": summary,
        "settings_json": _dict_value(first_attr(workflow, ("settings_json",), {}) or {}),
        "metadata_json": _dict_value(first_attr(workflow, ("metadata_json",), {}) or {}),
        "latest_version_no": first_attr(workflow, ("latest_version_no",), 0),
        "latest_version_id": first_attr(workflow, ("latest_version_id",)),
        "active_version_id": first_attr(workflow, ("active_version_id",)),
        "current_release_id": first_attr(workflow, ("current_release_id",)),
        "created_by": first_attr(workflow, ("created_by",)),
        "updated_by": first_attr(workflow, ("updated_by",)),
        "published_by": first_attr(workflow, ("published_by",)),
        "created_at": to_iso(first_attr(workflow, ("created_at",))),
        "updated_at": to_iso(first_attr(workflow, ("updated_at",))),
        "published_at": to_iso(first_attr(workflow, ("published_at",))),
    }


def serialize_run(run: Any, node_runs: list[Any] | None = None) -> dict[str, Any]:
    first_attr = _model_access().first_attr
    state_machine = _state_machine()
    status = first_attr(run, ("status",), "")
    node_runs = node_runs or []
    available_actions = state_machine.available_run_actions(status)
    workflow_id = first_attr(run, ("workflow_id", "tenant_workflow_id"))
    input_payload = first_attr(run, ("input_payload_json", "input_payload"), {})
    output_payload = first_attr(run, ("output_payload_json", "output_payload", "final_output"))
    cost_summary = _dict_value(first_attr(run, ("cost_summary_json", "cost_summary"), {}) or {})
    control_envelope = _dict_value(first_attr(run, ("control_envelope_json",), {}) or {})
    budget_snapshot = _dict_value(first_attr(run, ("budget_snapshot_json",), {}) or {})
    risk_snapshot = _dict_value(first_attr(run, ("risk_snapshot_json",), {}) or {})
    metrics = _dict_value(first_attr(run, ("metrics_json",), {}) or {})
    return {
        "id": first_attr(run, ("id",)),
        "name": first_attr(run, ("name",), None) or first_attr(run, ("code",), None) or f"run-{first_attr(run, ('id',), 'unknown')}",
        "tenant_id": first_attr(run, ("tenant_id",)),
        "workflow_template_id": first_attr(run, ("workflow_template_id",)),
        "tenant_workflow_id": workflow_id,
        "workflow_id": workflow_id,
        "workflow_version_id": first_attr(run, ("workflow_version_id",)),
        "release_id": first_attr(run, ("release_id",)),
        "trigger_id": first_attr(run, ("trigger_id",)),
        "environment_id": first_attr(run, ("environment_id",)),
        "parent_run_id": first_attr(run, ("parent_run_id",)),
        "code": first_attr(run, ("code",)),
        "entrypoint": first_attr(run, ("entrypoint",)),
        "trigger_source": first_attr(run, ("initiated_from", "trigger_source")),
        "initiated_from": first_attr(run, ("initiated_from", "trigger_source")),
        "mode": first_attr(run, ("mode",)),
        "status": status,
        "status_bucket": state_machine.run_status_bucket(status),
        "available_actions": available_actions,
        "initiated_by": first_attr(run, ("initiated_by", "started_by_id")),
        "started_by_type": first_attr(run, ("started_by_type",)),
        "started_by_id": first_attr(run, ("initiated_by", "started_by_id")),
        "current_node_key": first_attr(run, ("current_node_key",)),
        "current_node_name": first_attr(run, ("current_node_name", "current_step_name")),
        "trace_id": first_attr(run, ("trace_id",)),
        "idempotency_key": first_attr(run, ("idempotency_key",)),
        "retry_count": first_attr(run, ("retry_count",), 0),
        "input_payload": input_payload,
        "input_payload_json": input_payload,
        "output_payload": output_payload,
        "output_payload_json": output_payload,
        "final_output": output_payload,
        "control_envelope_json": control_envelope,
        "budget_snapshot_json": budget_snapshot,
        "risk_snapshot_json": risk_snapshot,
        "metrics_json": metrics,
        "error_summary": first_attr(run, ("error_summary",)),
        "cost_summary": cost_summary,
        "cost_summary_text": summarize_payload(cost_summary, budget=512),
        "cost_amount": cost_summary.get("total_amount") if isinstance(cost_summary, dict) else None,
        "waiting_approval": status in {"waiting_human", "waiting_approval"},
        "waiting_human_input": status in {"waiting_human", "waiting_approval", "waiting_input"},
        "can_pause": "pause" in available_actions,
        "can_resume": "resume" in available_actions,
        "can_retry": "retry" in available_actions,
        "can_terminate": "terminate" in available_actions,
        "started_at": to_iso(first_attr(run, ("started_at",))),
        "ended_at": to_iso(first_attr(run, ("ended_at",))),
        "last_heartbeat_at": to_iso(first_attr(run, ("last_heartbeat_at",))),
        "created_at": to_iso(first_attr(run, ("created_at",))),
        "updated_at": to_iso(first_attr(run, ("updated_at",))),
        "node_counts": {
            "total": len(node_runs),
            "running": sum(1 for item in node_runs if first_attr(item, ("status",)) == "running"),
            "waiting_human": sum(
                1
                for item in node_runs
                if first_attr(item, ("status",)) in {"waiting_human", "waiting_approval", "waiting_input"}
            ),
            "failed": sum(
                1
                for item in node_runs
                if first_attr(item, ("status",)) in {"failed_retryable", "failed_terminal"}
            ),
            "succeeded": sum(
                1
                for item in node_runs
                if first_attr(item, ("status",)) in {"succeeded", "skipped", "compensated"}
            ),
        },
    }


def serialize_node_run(node_run: Any) -> dict[str, Any]:
    first_attr = _model_access().first_attr
    status = first_attr(node_run, ("status",), "")
    input_envelope = first_attr(node_run, ("input_envelope_json", "input_payload"), {})
    output_envelope = first_attr(node_run, ("output_envelope_json", "output_payload"))
    cost_payload = _dict_value(first_attr(node_run, ("cost_json",), {}) or {})
    metrics_payload = _dict_value(first_attr(node_run, ("metrics_json",), {}) or {})
    return {
        "id": first_attr(node_run, ("id",)),
        "tenant_id": first_attr(node_run, ("tenant_id",)),
        "run_id": first_attr(node_run, ("run_id", "workflow_run_id")),
        "workflow_run_id": first_attr(node_run, ("run_id", "workflow_run_id")),
        "parent_node_run_id": first_attr(node_run, ("parent_node_run_id",)),
        "node_id": first_attr(node_run, ("node_id", "node_key")),
        "node_key": first_attr(node_run, ("node_key",)),
        "node_name": first_attr(node_run, ("node_name", "node_label", "node_key")),
        "node_type": first_attr(node_run, ("node_type",)),
        "status": status,
        "status_bucket": _state_machine().node_status_bucket(status),
        "attempt_no": first_attr(node_run, ("attempt_no",), 0),
        "executor_type": first_attr(node_run, ("executor_type",)),
        "executor_ref": first_attr(node_run, ("executor_ref",)),
        "trace_id": first_attr(node_run, ("trace_id",)),
        "input_payload": input_envelope,
        "input_envelope_json": input_envelope,
        "output_payload": output_envelope,
        "output_envelope_json": output_envelope,
        "cost_json": cost_payload,
        "metrics_json": metrics_payload,
        "error_detail": first_attr(node_run, ("error_summary", "error_detail")),
        "error_summary": first_attr(node_run, ("error_summary", "error_detail")),
        "duration_ms": first_attr(node_run, ("duration_ms",)),
        "started_at": to_iso(first_attr(node_run, ("started_at",))),
        "ended_at": to_iso(first_attr(node_run, ("ended_at",))),
        "created_at": to_iso(first_attr(node_run, ("created_at",))),
        "updated_at": to_iso(first_attr(node_run, ("updated_at",))),
    }


def serialize_checkpoint(checkpoint: Any) -> dict[str, Any]:
    first_attr = _model_access().first_attr
    snapshot_payload = _dict_value(first_attr(checkpoint, ("snapshot_json", "snapshot_payload", "payload", "content_json"), {}) or {})
    return {
        "id": first_attr(checkpoint, ("id",)),
        "tenant_id": first_attr(checkpoint, ("tenant_id",)),
        "run_id": first_attr(checkpoint, ("run_id", "workflow_run_id")),
        "workflow_run_id": first_attr(checkpoint, ("run_id", "workflow_run_id")),
        "node_run_id": first_attr(checkpoint, ("node_run_id", "workflow_node_run_id")),
        "workflow_node_run_id": first_attr(checkpoint, ("node_run_id", "workflow_node_run_id")),
        "checkpoint_type": first_attr(checkpoint, ("checkpoint_type", "type")),
        "resume_token": first_attr(checkpoint, ("resume_token",)),
        "state_hash": first_attr(checkpoint, ("state_hash",)),
        "snapshot_json": snapshot_payload,
        "snapshot_payload": snapshot_payload,
        "artifact_refs": first_attr(checkpoint, ("artifact_refs",), []) or [],
        "created_by": first_attr(checkpoint, ("created_by",)),
        "expires_at": to_iso(first_attr(checkpoint, ("expires_at",))),
        "restored_at": to_iso(first_attr(checkpoint, ("restored_at",))),
        "created_at": to_iso(first_attr(checkpoint, ("created_at",))),
    }


def serialize_event(event: Any) -> dict[str, Any]:
    first_attr = _model_access().first_attr
    payload = first_attr(event, ("payload_json", "detail", "payload", "content_json"))
    return {
        "id": first_attr(event, ("id",)),
        "tenant_id": first_attr(event, ("tenant_id",)),
        "run_id": first_attr(event, ("run_id", "workflow_run_id")),
        "workflow_run_id": first_attr(event, ("run_id", "workflow_run_id")),
        "node_run_id": first_attr(event, ("node_run_id", "workflow_node_run_id")),
        "workflow_node_run_id": first_attr(event, ("node_run_id", "workflow_node_run_id")),
        "event_type": first_attr(event, ("event_type", "type")),
        "event_level": first_attr(event, ("event_level",), "info"),
        "event_code": first_attr(event, ("event_code",)),
        "status_from": first_attr(event, ("status_from",)),
        "status_to": first_attr(event, ("status_to",)),
        "message": first_attr(event, ("message",)),
        "trace_id": first_attr(event, ("trace_id",)),
        "payload_json": payload,
        "detail": payload,
        "occurred_at": to_iso(first_attr(event, ("occurred_at",))),
        "created_at": to_iso(first_attr(event, ("occurred_at", "created_at"))),
    }


def serialize_artifact(artifact: Any) -> dict[str, Any]:
    first_attr = _model_access().first_attr
    state_machine = _state_machine()
    status = first_attr(artifact, ("status",), "ready")
    available_actions = state_machine.available_artifact_actions(status)
    preview_text = first_attr(artifact, ("preview_text",))
    if preview_text is None:
        preview_text = first_attr(artifact, ("summary",)) or summarize_payload(
            first_attr(artifact, ("content_json", "content_text")),
        )
    feedback_summary = _dict_value(first_attr(artifact, ("feedback_summary",), {}) or {})
    return {
        "id": first_attr(artifact, ("id",)),
        "tenant_id": first_attr(artifact, ("tenant_id",)),
        "run_id": first_attr(artifact, ("run_id", "workflow_run_id")),
        "workflow_run_id": first_attr(artifact, ("run_id", "workflow_run_id")),
        "node_run_id": first_attr(artifact, ("node_run_id", "workflow_node_run_id")),
        "workflow_node_run_id": first_attr(artifact, ("node_run_id", "workflow_node_run_id")),
        "workflow_id": first_attr(artifact, ("workflow_id",)),
        "workflow_version_id": first_attr(artifact, ("workflow_version_id",)),
        "code": first_attr(artifact, ("code",)),
        "artifact_type": first_attr(artifact, ("artifact_type",)),
        "status": status,
        "available_actions": available_actions,
        "name": first_attr(artifact, ("name", "title"), ""),
        "title": first_attr(artifact, ("name", "title"), ""),
        "summary": first_attr(artifact, ("summary",)) or preview_text,
        "preview_text": preview_text,
        "content_json": first_attr(artifact, ("content_json",)),
        "content_text": first_attr(artifact, ("content_text",)),
        "mime_type": first_attr(artifact, ("mime_type",)),
        "visibility_scope": first_attr(artifact, ("visibility_scope", "visibility"), "tenant_visible"),
        "visibility": first_attr(artifact, ("visibility_scope", "visibility"), "tenant_visible"),
        "schema_ref": first_attr(artifact, ("schema_ref",)),
        "storage_uri": first_attr(artifact, ("storage_uri",)),
        "storage_path": first_attr(artifact, ("storage_path", "file_path")),
        "size_bytes": first_attr(artifact, ("size_bytes",)),
        "content_hash": first_attr(artifact, ("content_hash", "hash")),
        "hash": first_attr(artifact, ("content_hash", "hash")),
        "feedback_summary": feedback_summary,
        "feedback_count": 1 if feedback_summary else 0,
        "download_filename": first_attr(artifact, ("download_filename", "filename")),
        "retention_policy_json": _dict_value(first_attr(artifact, ("retention_policy_json",), {}) or {}),
        "metadata_json": _dict_value(first_attr(artifact, ("metadata_json",), {}) or {}),
        "can_feedback": "feedback" in available_actions,
        "can_download": "download" in available_actions,
        "created_at": to_iso(first_attr(artifact, ("created_at",))),
        "updated_at": to_iso(first_attr(artifact, ("updated_at",))),
        "ready_at": to_iso(first_attr(artifact, ("ready_at",))),
        "expires_at": to_iso(first_attr(artifact, ("expires_at", "retention_until"))),
    }


def serialize_home_payload(
    *,
    stats: dict[str, Any],
    recent_runs: list[dict[str, Any]],
    recent_artifacts: list[dict[str, Any]],
    builder_capabilities: dict[str, Any],
) -> dict[str, Any]:
    todos = {bucket: int(stats.get(bucket, 0) or 0) for bucket in _constants().HOME_TODO_BUCKETS}
    return {
        "stats": stats,
        "todos": todos,
        "recent_runs": recent_runs,
        "recent_artifacts": recent_artifacts,
        "builder_capabilities": builder_capabilities,
        "generated_at": to_iso(utc_now()),
    }
