from __future__ import annotations

from collections.abc import Iterable

from app.plugins.module_loader import load_plugin_module

PLUGIN_NAME = "workflow-orchestration"


def _constants():
    module = load_plugin_module(PLUGIN_NAME, "runtime.constants")
    if module is None:
        raise RuntimeError("workflow runtime constants module is unavailable")
    return module


def run_status_bucket(status: str | None) -> str:
    return _constants().RUN_STATUS_BUCKETS.get(str(status or "").strip(), "pending")


def node_status_bucket(status: str | None) -> str:
    return _constants().NODE_RUN_STATUS_BUCKETS.get(str(status or "").strip(), "pending")


def available_run_actions(status: str | None) -> list[str]:
    return list(_constants().RUN_ACTIONS_BY_STATUS.get(str(status or "").strip(), ()))


def available_artifact_actions(status: str | None) -> list[str]:
    return list(_constants().ARTIFACT_ACTIONS_BY_STATUS.get(str(status or "").strip(), ()))


def derive_run_status_from_nodes(node_statuses: Iterable[str]) -> str:
    statuses = {status for status in node_statuses if status}
    if not statuses:
        return "queued"
    if "running" in statuses:
        return "running"
    if "waiting_human" in statuses:
        return "waiting_human"
    if "waiting_approval" in statuses:
        return "waiting_approval"
    if "waiting_input" in statuses:
        return "waiting_input"
    if "failed_terminal" in statuses:
        return "failed"
    if "failed_retryable" in statuses or "retry_scheduled" in statuses:
        return "recovering"
    if statuses.issubset({"succeeded", "skipped", "compensated"}):
        return "completed"
    if statuses.issubset({"cancelled"}):
        return "cancelled"
    if "ready" in statuses or "pending" in statuses:
        return "running"
    return "queued"
