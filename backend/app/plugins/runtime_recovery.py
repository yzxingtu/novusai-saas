"""Plugin runtime recovery helpers. / 插件运行态恢复辅助。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

PluginRecoveryAction = Literal[
    "force_cleanup",
    "install_dependencies",
    "refresh_schedules",
    "repair",
]
PluginRecoveryReason = Literal[
    "missing_dependencies",
    "missing_from_disk",
    "none",
    "runtime_error",
    "schedule_refresh_failed",
]
PluginRecoverySeverity = Literal["error", "healthy", "warning"]


def has_plugin_scheduled_tasks(manifest: Mapping[str, Any] | None) -> bool:
    """Return whether the plugin manifest declares scheduled tasks."""
    if not isinstance(manifest, Mapping):
        return False
    extensions = manifest.get("extensions")
    if not isinstance(extensions, Mapping):
        return False
    tasks = extensions.get("tasks")
    return isinstance(tasks, list) and len(tasks) > 0


def is_missing_from_disk_error_message(message: str | None) -> bool:
    """Detect missing-plugin-files error wording used by runtime lifecycle paths."""
    if not message:
        return False
    lowered = message.lower()
    return "missing from disk" in lowered or "磁盘文件已缺失" in message


def is_schedule_refresh_error_message(message: str | None) -> bool:
    """Detect the localized scheduler refresh failure message family."""
    if not message:
        return False
    lowered = message.lower()
    return "refresh scheduled tasks" in lowered or "刷新定时调度失败" in message


def build_plugin_recovery_state(
    *,
    dependency_status: Mapping[str, Any] | None,
    error_message: str | None,
    manifest: Mapping[str, Any] | None,
    status: str,
) -> dict[str, Any]:
    """Build a frontend-facing recovery contract for plugin runtime remediation."""
    has_scheduled_tasks = has_plugin_scheduled_tasks(manifest)
    dependency_missing = (
        dependency_status is not None
        and dependency_status.get("overall") != "installed"
    )
    reason: PluginRecoveryReason = "none"
    severity: PluginRecoverySeverity = "healthy"
    primary_action: None | PluginRecoveryAction = None
    secondary_actions: list[PluginRecoveryAction] = []

    if is_missing_from_disk_error_message(error_message):
        reason = "missing_from_disk"
        severity = "error"
        primary_action = "force_cleanup"
    elif dependency_missing:
        reason = "missing_dependencies"
        severity = "error" if status == "error" else "warning"
        primary_action = "install_dependencies"
        if status == "error":
            secondary_actions.append("repair")
    elif is_schedule_refresh_error_message(error_message):
        reason = "schedule_refresh_failed"
        severity = "error"
        primary_action = "refresh_schedules"
    elif status == "error":
        reason = "runtime_error"
        severity = "error"
        primary_action = "repair"

    return {
        "has_scheduled_tasks": has_scheduled_tasks,
        "needs_attention": reason != "none",
        "primary_action": primary_action,
        "reason": reason,
        "secondary_actions": secondary_actions,
        "severity": severity,
    }
