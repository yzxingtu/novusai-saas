"""Shared module-resolution helpers for operation log rows."""

from __future__ import annotations

import re

_ROUTE_SCOPE_SEGMENTS = {"admin", "tenant", "user", "public"}
_ROUTE_NON_MODULE_SEGMENTS = {"api", "internal", "v1", "v2"}
_ROUTE_MODULE_ALIASES = {
    "admin_users": "admin_user",
    "email_logs": "email_log",
    "notification_templates": "notification_template",
    "operation_logs": "operation_log",
    "periodic_tasks": "periodic_task",
    "system_logs": "system_log",
    "task_logs": "task_log",
    "tenant_admins": "tenant_admin",
    "tenant_users": "tenant_user",
}
_MODULE_SEPARATOR_RE = re.compile(r"[\s-]+")


def normalize_operation_log_module(module: str | None) -> str | None:
    """Normalize a module/resource token into a stable snake_case identifier."""
    if not module:
        return None

    normalized = _MODULE_SEPARATOR_RE.sub("_", str(module).strip().lower()).strip(
        "_"
    )
    return normalized or None


def _singularize_route_module(module: str) -> str:
    alias = _ROUTE_MODULE_ALIASES.get(module)
    if alias:
        return alias

    if module.endswith("ies") and len(module) > 3:
        return f"{module[:-3]}y"

    if module.endswith("s") and not module.endswith(("ss", "us")):
        return module[:-1]

    return module


def infer_operation_log_module_from_path(path: str | None) -> str | None:
    """Infer a module name from a request path when the row did not store one."""
    if not path:
        return None

    segments = [segment for segment in path.split("/") if segment]
    if not segments:
        return None

    if segments[0] in _ROUTE_SCOPE_SEGMENTS:
        segments = segments[1:]

    for segment in segments:
        if (
            not segment
            or segment in _ROUTE_NON_MODULE_SEGMENTS
            or segment.isdigit()
            or (segment.startswith("{") and segment.endswith("}"))
        ):
            continue

        normalized = normalize_operation_log_module(segment)
        if not normalized or normalized in _ROUTE_NON_MODULE_SEGMENTS:
            continue

        return _singularize_route_module(normalized)

    return None


def resolve_operation_log_module(
    *,
    module: str | None,
    resource: str | None,
    path: str | None,
) -> str | None:
    """Resolve the most useful module code for writes and legacy-row display."""
    normalized_module = normalize_operation_log_module(module)
    if normalized_module:
        return normalized_module

    if resource:
        resource_prefix = normalize_operation_log_module(resource.partition(":")[0])
        if resource_prefix:
            return resource_prefix

    return infer_operation_log_module_from_path(path)


__all__ = [
    "infer_operation_log_module_from_path",
    "normalize_operation_log_module",
    "resolve_operation_log_module",
]
