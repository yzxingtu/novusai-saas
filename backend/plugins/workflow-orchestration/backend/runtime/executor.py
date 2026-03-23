from __future__ import annotations

import hashlib
import json
from typing import Any

from app.core.base_model import utc_now
from app.middleware.trace import trace_id_var
from app.plugins.module_loader import load_plugin_module

PLUGIN_NAME = "workflow-orchestration"


def _graph():
    module = load_plugin_module(PLUGIN_NAME, "runtime.graph")
    if module is None:
        raise RuntimeError("workflow runtime graph module is unavailable")
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


def _errors():
    module = load_plugin_module(PLUGIN_NAME, "runtime.errors")
    if module is None:
        raise RuntimeError("workflow runtime errors module is unavailable")
    return module


async def bootstrap_run_graph(db: Any, run: Any, snapshot: dict[str, Any]) -> dict[str, Any]:
    model_access = _model_access()
    node_model = model_access.try_resolve_model("workflow_node_run")
    graph = _graph().build_graph(snapshot)
    if node_model is None:
        return {
            "node_runs": [],
            "graph": graph,
        }

    created_nodes = []
    tenant_id = model_access.first_attr(run, ("tenant_id",))
    run_id = model_access.first_attr(run, ("id",))
    run_trace_id = model_access.first_attr(run, ("trace_id",)) or trace_id_var.get() or None
    now = utc_now()

    for node in graph["nodes"]:
        node_values = {
            "run_id": run_id,
            "tenant_id": tenant_id,
            "parent_node_run_id": None,
            "node_key": node["node_key"],
            "node_type": node["node_type"],
            "status": node["initial_status"],
            "attempt_no": 1,
            "executor_type": node["executor_type"],
            "executor_ref": node["executor_ref"],
            "trace_id": run_trace_id,
            "input_envelope_json": {},
            "output_envelope_json": None,
            "cost_json": {},
            "metrics_json": {
                "depends_on": list(node.get("depends_on") or []),
                "timeout_seconds": node.get("timeout_seconds"),
                "risk_level": node.get("risk_level"),
            },
            "error_summary": None,
            "started_at": None,
            "ended_at": None,
        }
        instance = model_access.instantiate_model(node_model, node_values)
        db.add(instance)
        created_nodes.append(instance)

    checkpoint = create_checkpoint_instance(
        "run_start_checkpoint",
        {
            "run": run,
            "run_id": run_id,
            "tenant_id": tenant_id,
            "snapshot_json": {
                "workflow_snapshot": snapshot,
                "root_node_keys": graph["root_node_keys"],
            },
        },
    )
    if checkpoint is not None:
        db.add(checkpoint)

    event = create_event_instance(
        "run_created",
        {
            "run": run,
            "run_id": run_id,
            "tenant_id": tenant_id,
            "message": "run bootstrapped",
            "payload_json": {
                "root_node_keys": graph["root_node_keys"],
                "node_count": len(graph["nodes"]),
            },
        },
    )
    if event is not None:
        db.add(event)

    model_access.assign_model_values(
        run,
        {
            "status": "running" if graph["root_node_keys"] else "completed",
            "current_node_key": graph["root_node_keys"][0] if graph["root_node_keys"] else None,
            "started_at": now,
            "last_heartbeat_at": now,
        },
    )

    await db.flush()
    return {
        "node_runs": created_nodes,
        "graph": graph,
    }


async def advance_run_execution(
    db: Any,
    run: Any,
    snapshot: dict[str, Any],
    *,
    node_runs: list[Any] | None = None,
    graph: dict[str, Any] | None = None,
) -> dict[str, Any]:
    model_access = _model_access()
    graph_payload = graph or _graph().build_graph(snapshot)
    active_node_runs = list(node_runs or [])
    if not active_node_runs:
        await db.flush()
        return {
            "node_runs": active_node_runs,
            "graph": graph_payload,
        }
    node_definitions = {
        str(node.get("node_key") or "").strip(): node
        for node in graph_payload.get("nodes") or []
        if str(node.get("node_key") or "").strip()
    }

    while True:
        released = _release_ready_nodes(db, run, active_node_runs, node_definitions)
        ready_nodes = [
            node
            for node in active_node_runs
            if model_access.first_attr(node, ("status",)) == "ready"
        ]
        if not ready_nodes and not released:
            break

        advanced = False
        for node_run in ready_nodes:
            if model_access.first_attr(node_run, ("status",)) != "ready":
                continue
            node_definition = _resolve_node_definition(node_run, node_definitions)
            transition = _plan_node_transition(run, node_run, node_definition, active_node_runs)
            _apply_node_transition(db, run, node_run, node_definition, transition)
            advanced = True

        if not advanced:
            break

    synchronize_run_status(run, active_node_runs)
    _update_run_metrics(run, active_node_runs, graph_payload)
    await db.flush()
    return {
        "node_runs": active_node_runs,
        "graph": graph_payload,
    }


def create_checkpoint_instance(checkpoint_type: str, values: dict[str, Any]) -> Any | None:
    model_access = _model_access()
    checkpoint_model = model_access.try_resolve_model("execution_checkpoint")
    if checkpoint_model is None:
        return None
    run = values.get("run")
    run_id = values.get("run_id") or values.get("workflow_run_id") or model_access.first_attr(run, ("id",))
    if run_id is None:
        return None
    snapshot_json = values.get("snapshot_json") or values.get("snapshot_payload") or {}
    tenant_id = values.get("tenant_id") or model_access.first_attr(run, ("tenant_id",))
    payload = {
        "checkpoint_type": checkpoint_type,
        "run_id": run_id,
        "node_run_id": values.get("node_run_id") or values.get("workflow_node_run_id"),
        "tenant_id": tenant_id,
        "resume_token": values.get("resume_token"),
        "state_hash": values.get("state_hash") or _stable_hash(snapshot_json),
        "snapshot_json": snapshot_json,
        "created_by": values.get("created_by"),
        "expires_at": values.get("expires_at"),
        "restored_at": values.get("restored_at"),
    }
    return model_access.instantiate_model(checkpoint_model, payload)


def create_event_instance(event_type: str, values: dict[str, Any]) -> Any | None:
    model_access = _model_access()
    event_model = model_access.try_resolve_model("execution_event")
    if event_model is None:
        return None
    run = values.get("run")
    run_id = values.get("run_id") or values.get("workflow_run_id") or model_access.first_attr(run, ("id",))
    if run_id is None:
        return None
    tenant_id = values.get("tenant_id") or model_access.first_attr(run, ("tenant_id",))
    if tenant_id is None:
        return None
    status_to = values.get("status_to")
    payload_json = values.get("payload_json")
    if payload_json is None:
        payload_json = values.get("detail")
    payload = {
        "event_type": event_type,
        "run_id": run_id,
        "node_run_id": values.get("node_run_id") or values.get("workflow_node_run_id"),
        "tenant_id": tenant_id,
        "event_level": values.get("event_level") or _infer_event_level(event_type, status_to),
        "event_code": values.get("event_code") or event_type,
        "status_from": values.get("status_from"),
        "status_to": status_to,
        "message": values.get("message"),
        "trace_id": values.get("trace_id") or model_access.first_attr(run, ("trace_id",)) or trace_id_var.get() or None,
        "payload_json": payload_json,
        "occurred_at": values.get("occurred_at") or utc_now(),
    }
    return model_access.instantiate_model(event_model, payload)


def create_artifact_instance(values: dict[str, Any]) -> Any | None:
    model_access = _model_access()
    artifact_model = model_access.try_resolve_model("execution_artifact")
    if artifact_model is None:
        return None
    run = values.get("run")
    run_id = values.get("run_id") or values.get("workflow_run_id") or model_access.first_attr(run, ("id",))
    workflow_id = values.get("workflow_id") or model_access.first_attr(run, ("workflow_id", "tenant_workflow_id"))
    workflow_version_id = values.get("workflow_version_id") or model_access.first_attr(run, ("workflow_version_id",))
    tenant_id = values.get("tenant_id") or model_access.first_attr(run, ("tenant_id",))
    if run_id is None or workflow_id is None or workflow_version_id is None or tenant_id is None:
        return None
    content_json = values.get("content_json")
    content_text = values.get("content_text")
    name = values.get("name") or values.get("title")
    status = values.get("status", "ready")
    storage_uri = values.get("storage_uri")
    storage_path = values.get("storage_path")
    payload = {
        "tenant_id": tenant_id,
        "run_id": run_id,
        "node_run_id": values.get("node_run_id") or values.get("workflow_node_run_id"),
        "workflow_id": workflow_id,
        "workflow_version_id": workflow_version_id,
        "artifact_type": values.get("artifact_type"),
        "status": status,
        "name": name or _default_artifact_name(values),
        "summary": values.get("summary") or summarize_payload(content_json or content_text),
        "content_json": content_json,
        "content_text": content_text,
        "visibility_scope": values.get("visibility_scope") or values.get("visibility", "tenant_visible"),
        "mime_type": values.get("mime_type"),
        "schema_ref": values.get("schema_ref"),
        "storage_uri": storage_uri,
        "storage_path": storage_path,
        "size_bytes": values.get("size_bytes"),
        "content_hash": values.get("content_hash") or values.get("hash") or _artifact_hash(content_json, content_text, storage_uri, storage_path),
        "feedback_summary": values.get("feedback_summary") or {},
        "download_filename": values.get("download_filename"),
        "retention_policy_json": values.get("retention_policy_json") or {},
        "metadata_json": values.get("metadata_json") or {},
        "ready_at": values.get("ready_at") or (utc_now() if status in {"ready", "adopted", "rejected", "archived"} else None),
        "expires_at": values.get("expires_at"),
    }
    return model_access.instantiate_model(artifact_model, payload)


def synchronize_run_status(run: Any, node_runs: list[Any]) -> str:
    model_access = _model_access()
    node_statuses = [str(model_access.first_attr(node, ("status",), "")) for node in node_runs]
    next_status = (
        "waiting_human"
        if "waiting_human" in node_statuses
        else _state_machine().derive_run_status_from_nodes(node_statuses)
    )
    is_terminal = next_status in {"completed", "failed", "cancelled", "succeeded"}
    model_access.assign_model_values(
        run,
        {
            "status": next_status,
            "current_node_key": _first_active_node_key(node_runs),
            "ended_at": utc_now() if is_terminal else None,
            "last_heartbeat_at": utc_now(),
        },
    )
    return next_status


def mark_run_status(
    run: Any,
    *,
    status: str,
    current_node_key: str | None = None,
    error_summary: str | None = None,
) -> Any:
    if not status:
        raise _errors().WorkflowConflictError()
    is_terminal = status in {"completed", "failed", "cancelled", "succeeded"}
    _model_access().assign_model_values(
        run,
        {
            "status": status,
            "current_node_key": current_node_key,
            "error_summary": error_summary,
            "ended_at": utc_now() if is_terminal else None,
            "last_heartbeat_at": utc_now(),
        },
    )
    return run


def _first_active_node_key(node_runs: list[Any]) -> str | None:
    first_attr = _model_access().first_attr
    for status in ("running", "ready", "pending", "waiting_human", "waiting_approval", "waiting_input"):
        for node in node_runs:
            if first_attr(node, ("status",)) == status:
                return first_attr(node, ("node_key",))
    return None


def _release_ready_nodes(
    db: Any,
    run: Any,
    node_runs: list[Any],
    node_definitions: dict[str, dict[str, Any]],
) -> bool:
    model_access = _model_access()
    node_runs_by_key = {
        str(model_access.first_attr(node, ("node_key",), "")): node
        for node in node_runs
    }
    success_statuses = {"succeeded", "skipped", "compensated"}
    released = False

    for node_run in node_runs:
        if model_access.first_attr(node_run, ("status",)) != "pending":
            continue
        node_definition = _resolve_node_definition(node_run, node_definitions)
        depends_on = list(node_definition.get("depends_on") or [])
        if depends_on and not all(
            model_access.first_attr(node_runs_by_key.get(dep_key), ("status",))
            in success_statuses
            for dep_key in depends_on
        ):
            continue

        input_envelope = _build_node_input_envelope(run, node_run, node_definition, node_runs_by_key)
        metrics_payload = _merge_payload(
            model_access.first_attr(node_run, ("metrics_json",), {}) or {},
            {
                "depends_on": depends_on,
                "released_from_pending": True,
            },
        )
        model_access.assign_model_values(
            node_run,
            {
                "status": "ready",
                "input_envelope_json": input_envelope,
                "metrics_json": metrics_payload,
                "error_summary": None,
            },
        )
        _record_node_event(
            db,
            run,
            node_run,
            "node_status_changed",
            status_from="pending",
            status_to="ready",
            message="node released for execution",
            payload_json={
                "node_key": model_access.first_attr(node_run, ("node_key",)),
                "depends_on": depends_on,
            },
        )
        released = True

    return released


def _resolve_node_definition(node_run: Any, node_definitions: dict[str, dict[str, Any]]) -> dict[str, Any]:
    model_access = _model_access()
    node_key = str(model_access.first_attr(node_run, ("node_key",), "")).strip()
    node_definition = dict(node_definitions.get(node_key) or {})
    if node_definition:
        return node_definition
    return {
        "node_key": node_key,
        "node_type": model_access.first_attr(node_run, ("node_type",), "system"),
        "executor_type": model_access.first_attr(node_run, ("executor_type",), "system"),
        "executor_ref": model_access.first_attr(node_run, ("executor_ref",)),
        "config": {},
        "depends_on": list(
            (model_access.first_attr(node_run, ("metrics_json",), {}) or {}).get("depends_on") or []
        ),
    }


def _plan_node_transition(
    run: Any,
    node_run: Any,
    node_definition: dict[str, Any],
    node_runs: list[Any],
) -> dict[str, Any]:
    model_access = _model_access()
    node_runs_by_key = {
        str(model_access.first_attr(item, ("node_key",), "")): item
        for item in node_runs
    }
    node_key = str(node_definition.get("node_key") or model_access.first_attr(node_run, ("node_key",), "")).strip()
    node_type = str(
        node_definition.get("node_type")
        or model_access.first_attr(node_run, ("node_type",), "system")
        or "system"
    ).strip().lower() or "system"
    input_envelope = _build_node_input_envelope(run, node_run, node_definition, node_runs_by_key)

    if node_type == "approval":
        return {
            "status": "waiting_approval",
            "message": "node waiting for approval",
            "input_envelope": input_envelope,
            "checkpoint_type": "approval_wait_checkpoint",
            "checkpoint_snapshot": {
                "node_key": node_key,
                "node_type": node_type,
                "waiting_status": "waiting_approval",
                "required_action": "approve",
                "input_envelope": input_envelope,
            },
            "artifact": {
                "artifact_type": "approval_packet",
                "name": f"{node_key}-approval",
                "content_json": {
                    "node_key": node_key,
                    "node_type": node_type,
                    "required_action": "approve",
                    "input_envelope": input_envelope,
                },
                "metadata_json": {
                    "transition": "waiting_approval",
                },
            },
        }

    if node_type == "human_review":
        return {
            "status": "waiting_approval",
            "message": "node waiting for human review",
            "input_envelope": input_envelope,
            "checkpoint_type": "manual_handover_checkpoint",
            "checkpoint_snapshot": {
                "node_key": node_key,
                "node_type": node_type,
                "waiting_status": "waiting_approval",
                "required_action": "review",
                "input_envelope": input_envelope,
            },
            "artifact": {
                "artifact_type": "approval_packet",
                "name": f"{node_key}-review",
                "content_json": {
                    "node_key": node_key,
                    "node_type": node_type,
                    "required_action": "review",
                    "input_envelope": input_envelope,
                },
                "metadata_json": {
                    "transition": "waiting_human_review",
                },
            },
        }

    if node_type == "input":
        return {
            "status": "waiting_input",
            "message": "node waiting for input",
            "input_envelope": input_envelope,
            "checkpoint_type": "node_input_checkpoint",
            "checkpoint_snapshot": {
                "node_key": node_key,
                "node_type": node_type,
                "waiting_status": "waiting_input",
                "required_fields": list((node_definition.get("config") or {}).get("required_fields") or []),
                "input_envelope": input_envelope,
            },
        }

    output_envelope = _build_deterministic_output(run, node_run, node_definition, input_envelope)
    return {
        "status": "succeeded",
        "message": "node completed via deterministic fallback",
        "input_envelope": input_envelope,
        "output_envelope": output_envelope,
        "checkpoint_type": "node_output_checkpoint",
        "checkpoint_snapshot": {
            "node_key": node_key,
            "node_type": node_type,
            "status": "succeeded",
            "output_envelope": output_envelope,
        },
        "artifact": {
            "artifact_type": "report",
            "name": f"{node_key}-output",
            "content_json": output_envelope,
            "metadata_json": {
                "transition": "deterministic_fallback",
                "node_type": node_type,
            },
        },
    }


def _apply_node_transition(
    db: Any,
    run: Any,
    node_run: Any,
    node_definition: dict[str, Any],
    transition: dict[str, Any],
) -> None:
    model_access = _model_access()
    now = utc_now()
    current_status = str(model_access.first_attr(node_run, ("status",), "ready"))
    next_status = str(transition["status"])
    started_at = model_access.first_attr(node_run, ("started_at",)) or now
    ended_at = now if next_status in {"succeeded", "failed_terminal", "failed_retryable", "skipped", "compensated", "cancelled"} else None
    duration_ms = None
    if ended_at is not None:
        duration_ms = max(int((ended_at - started_at).total_seconds() * 1000), 0)

    metrics_payload = _merge_payload(
        model_access.first_attr(node_run, ("metrics_json",), {}) or {},
        {
            "depends_on": list(node_definition.get("depends_on") or []),
            "last_transition": next_status,
            "node_type": node_definition.get("node_type"),
        },
    )
    if transition.get("output_envelope") is not None:
        metrics_payload["output_summary"] = summarize_payload(transition["output_envelope"], budget=512)

    model_access.assign_model_values(
        node_run,
        {
            "status": next_status,
            "input_envelope_json": transition.get("input_envelope") or model_access.first_attr(node_run, ("input_envelope_json",), {}) or {},
            "output_envelope_json": transition.get("output_envelope"),
            "cost_json": transition.get("cost_json") or model_access.first_attr(node_run, ("cost_json",), {}) or {},
            "metrics_json": metrics_payload,
            "error_summary": transition.get("error_summary"),
            "started_at": started_at,
            "ended_at": ended_at,
            "duration_ms": duration_ms,
        },
    )

    if transition.get("output_envelope") is not None:
        model_access.assign_model_values(
            run,
            {
                "output_payload_json": transition["output_envelope"],
            },
        )

    _record_node_event(
        db,
        run,
        node_run,
        "node_status_changed",
        status_from=current_status,
        status_to=next_status,
        message=transition.get("message"),
        payload_json={
            "node_key": model_access.first_attr(node_run, ("node_key",)),
            "node_type": model_access.first_attr(node_run, ("node_type",)),
            "checkpoint_type": transition.get("checkpoint_type"),
            "output_summary": summarize_payload(transition.get("output_envelope"), budget=512),
        },
    )

    checkpoint_type = transition.get("checkpoint_type")
    if checkpoint_type:
        checkpoint = create_checkpoint_instance(
            checkpoint_type,
            {
                "run": run,
                "node_run_id": model_access.first_attr(node_run, ("id",)),
                "tenant_id": model_access.first_attr(node_run, ("tenant_id",)),
                "snapshot_json": transition.get("checkpoint_snapshot") or {},
            },
        )
        if checkpoint is not None:
            db.add(checkpoint)
            _record_node_event(
                db,
                run,
                node_run,
                "checkpoint_recorded",
                status_to=next_status,
                message=f"{checkpoint_type} recorded",
                payload_json={
                    "node_key": model_access.first_attr(node_run, ("node_key",)),
                    "checkpoint_type": checkpoint_type,
                },
            )

    artifact_payload = transition.get("artifact")
    if artifact_payload:
        artifact = create_artifact_instance(
            {
                "run": run,
                "node_run_id": model_access.first_attr(node_run, ("id",)),
                **artifact_payload,
            },
        )
        if artifact is not None:
            db.add(artifact)
            _record_node_event(
                db,
                run,
                node_run,
                "artifact_recorded",
                status_to=next_status,
                message="node artifact recorded",
                payload_json={
                    "node_key": model_access.first_attr(node_run, ("node_key",)),
                    "artifact_type": artifact_payload.get("artifact_type"),
                    "artifact_name": artifact_payload.get("name"),
                },
            )


def _record_node_event(
    db: Any,
    run: Any,
    node_run: Any,
    event_type: str,
    *,
    status_from: str | None = None,
    status_to: str | None = None,
    message: str | None = None,
    payload_json: dict[str, Any] | None = None,
) -> None:
    event = create_event_instance(
        event_type,
        {
            "run": run,
            "node_run_id": _model_access().first_attr(node_run, ("id",)),
            "tenant_id": _model_access().first_attr(node_run, ("tenant_id",)),
            "status_from": status_from,
            "status_to": status_to,
            "message": message,
            "payload_json": payload_json or {},
        },
    )
    if event is not None:
        db.add(event)


def _build_node_input_envelope(
    run: Any,
    node_run: Any,
    node_definition: dict[str, Any],
    node_runs_by_key: dict[str, Any],
) -> dict[str, Any]:
    model_access = _model_access()
    existing = dict(model_access.first_attr(node_run, ("input_envelope_json",), {}) or {})
    upstream_outputs: dict[str, Any] = {}
    for dep_key in node_definition.get("depends_on") or []:
        dep_run = node_runs_by_key.get(str(dep_key))
        if dep_run is None:
            continue
        dep_output = model_access.first_attr(dep_run, ("output_envelope_json", "output_payload"))
        if dep_output not in (None, {}, []):
            upstream_outputs[str(dep_key)] = dep_output

    input_envelope = {
        "run_input": dict(model_access.first_attr(run, ("input_payload_json", "input_payload"), {}) or {}),
        "node_config": dict(node_definition.get("config") or {}),
        "depends_on": list(node_definition.get("depends_on") or []),
    }
    if upstream_outputs:
        input_envelope["upstream_outputs"] = upstream_outputs
    return _merge_payload(input_envelope, existing)


def _build_deterministic_output(
    run: Any,
    node_run: Any,
    node_definition: dict[str, Any],
    input_envelope: dict[str, Any],
) -> dict[str, Any]:
    model_access = _model_access()
    return {
        "mode": "deterministic_fallback",
        "node_key": model_access.first_attr(node_run, ("node_key",)),
        "node_type": model_access.first_attr(node_run, ("node_type",), node_definition.get("node_type")),
        "executor_type": model_access.first_attr(node_run, ("executor_type",), node_definition.get("executor_type")),
        "executor_ref": model_access.first_attr(node_run, ("executor_ref",), node_definition.get("executor_ref")),
        "workflow_mode": model_access.first_attr(run, ("mode",), "deterministic"),
        "input_envelope": input_envelope,
        "result": {
            "status": "succeeded",
            "message": "minimal deterministic fallback executed",
        },
        "emitted_at": str(utc_now().isoformat()),
    }


def _update_run_metrics(run: Any, node_runs: list[Any], graph: dict[str, Any]) -> None:
    model_access = _model_access()
    status_counts: dict[str, int] = {}
    for node in node_runs:
        status = str(model_access.first_attr(node, ("status",), "")).strip()
        if not status:
            continue
        status_counts[status] = status_counts.get(status, 0) + 1

    metrics_payload = _merge_payload(
        model_access.first_attr(run, ("metrics_json",), {}) or {},
        {
            "node_count": len(graph.get("nodes") or []),
            "edge_count": len(graph.get("edges") or []),
            "root_node_count": len(graph.get("root_node_keys") or []),
            "status_counts": status_counts,
            "succeeded_node_count": sum(
                status_counts.get(status, 0)
                for status in ("succeeded", "skipped", "compensated")
            ),
            "waiting_node_count": sum(
                status_counts.get(status, 0)
                for status in ("waiting_human", "waiting_approval", "waiting_input")
            ),
        },
    )
    model_access.assign_model_values(run, {"metrics_json": metrics_payload})


def _merge_payload(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in extra.items():
        if value is not None:
            merged[key] = value
    return merged


def _stable_hash(payload: Any) -> str | None:
    if payload in (None, "", {}, []):
        return None
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _default_artifact_name(values: dict[str, Any]) -> str:
    code = str(values.get("code") or "").strip()
    artifact_type = str(values.get("artifact_type") or "artifact").strip() or "artifact"
    return code or artifact_type


def _artifact_hash(content_json: Any, content_text: Any, storage_uri: Any, storage_path: Any) -> str | None:
    if content_json not in (None, {}, []):
        return _stable_hash(content_json)
    if content_text not in (None, ""):
        return hashlib.sha256(str(content_text).encode("utf-8")).hexdigest()
    storage_ref = storage_path or storage_uri
    if storage_ref:
        return hashlib.sha256(str(storage_ref).encode("utf-8")).hexdigest()
    return None


def _infer_event_level(event_type: str, status_to: str | None) -> str:
    if event_type in {"run_timed_out"} or status_to in {"failed", "failed_terminal"}:
        return "warning"
    if event_type in {"artifact_feedback_submitted", "artifact_retention_cleaned"}:
        return "audit"
    return "info"


def summarize_payload(payload: Any, budget: int = 256) -> str | None:
    if payload in (None, "", {}, []):
        return None
    if isinstance(payload, str):
        return payload[:budget]
    try:
        rendered = json.dumps(payload, ensure_ascii=False, default=str)
    except Exception:
        rendered = str(payload)
    return rendered[:budget]
