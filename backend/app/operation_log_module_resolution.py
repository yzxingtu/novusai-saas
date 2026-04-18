"""Shared module-resolution helpers for operation log rows."""

from __future__ import annotations

import re

_ROUTE_SCOPE_SEGMENTS = {"admin", "tenant", "user", "public"}
_ROUTE_NON_MODULE_SEGMENTS = {"api", "internal", "v1", "v2", "ws"}
_INVALID_MODULE_VALUES = _ROUTE_SCOPE_SEGMENTS | {"api", "v1", "v2", "w"}
_MODULE_VALUE_ALIASES = {
    "admins": "admin_user",
    "ai_action_logs": "ai_action_log",
    "ai_agents": "ai_agent",
    "ai_api_keys": "ai_api_key",
    "ai_call_logs": "ai_call_log",
    "ai_knowledge_bases": "ai_knowledge_base",
    "ai_models": "ai_model",
    "ai_providers": "ai_provider",
    "ai_skill_packages": "ai_skill_package",
    "ai_skills": "ai_skill",
    "cache": "cache_management",
    "dashboards": "dashboard",
    "knowledge_bases": "knowledge_base",
    "notification_preferences": "notification",
    "notifications": "notification",
    "preferences": "preference",
    "plugin_assets": "plugin",
    "plugin_icons": "plugin",
    "plugin_public_assets": "plugin",
    "plugins": "plugin",
}
_ROUTE_MODULE_ALIASES = {
    "analytics": "analytics",
    "admin_users": "admin_user",
    "email_logs": "email_log",
    "notification_templates": "notification_template",
    "operation_logs": "operation_log",
    "periodic_tasks": "periodic_task",
    "plugin_assets": "plugin",
    "plugin_icons": "plugin",
    "plugin_public_assets": "plugin",
    "system_logs": "system_log",
    "task_logs": "task_log",
    "tenant_admins": "tenant_admin",
    "tenant_users": "tenant_user",
}
_PATH_PREFIX_MODULE_ALIASES = (
    ("/api/public/platform/config", "platform_config"),
    ("/api/public/tenant/config", "tenant_config"),
    ("/api/public/attachments/", "attachment"),
    ("/api/public/captcha/", "captcha"),
    ("/api/public/health", "health"),
    ("/api/public/tenant/legal", "legal"),
    ("/plugin-assets/", "plugin"),
    ("/plugin-icons/", "plugin"),
    ("/plugin-public-assets/", "plugin"),
    ("/admin/dashboard/", "dashboard"),
    ("/tenant/dashboard/", "dashboard"),
    ("/admin/preferences/", "preference"),
    ("/tenant/preferences/", "preference"),
    ("/admin/notification-preferences/", "notification"),
    ("/tenant/notification-preferences/", "notification"),
    ("/admin/auth/", "auth"),
    ("/tenant/auth/", "auth"),
    ("/api/user/auth/", "auth"),
    ("/tenant/login", "auth"),
    ("/admin/ws/", "presence"),
    ("/tenant/ws/", "presence"),
    ("/admin/analytics/", "analytics"),
    ("/tenant/analytics/", "analytics"),
    ("/api/user/permissions/", "user_permission"),
    ("/api/user/ai/agent-chat", "user_agent_chat"),
    ("/api/user/ai/agents", "user_agents"),
    ("/api/admin/login", "auth"),
    ("/admin/ai/agents", "ai_agent"),
    ("/admin/ai/skill-packages", "ai_skill_package"),
    ("/tenant/ai/agents", "agent"),
    ("/tenant/ai/skill-packages", "skill_package"),
    ("/admin/ai/skill-registry", "ai_skill_registry"),
    ("/admin/ai/platform-tools", "ai_platform_tool"),
    ("/admin/ai/table-policies", "ai_table_policy"),
    ("/tenant/ai/table-policies", "ai_table_policy_override"),
    ("/admin/ai/agent-assignments", "agent_assignment"),
    ("/admin/ai/tools", "ai_tool"),
    ("/tenant/ai/tools", "agent_tool"),
    ("/tenant/ai/agent-assignments", "tenant_agent_assignment"),
    ("/admin/monitoring/", "system_monitoring"),
    ("/admin/files/", "attachment"),
    ("/tenant/menus", "permission"),
    ("/tenant/subscription", "subscription"),
    ("/tenant/announcements", "announcement"),
    ("/tenant/workflows", "workflow"),
    ("/admin/articles", "article"),
)
_MODULE_SEPARATOR_RE = re.compile(r"[^a-z0-9]+")


def normalize_operation_log_module(module: str | None) -> str | None:
    """Normalize a module/resource token into a stable snake_case identifier."""
    if not module:
        return None

    normalized = _MODULE_SEPARATOR_RE.sub("_", str(module).strip().lower()).strip("_")
    if not normalized:
        return None
    return _MODULE_VALUE_ALIASES.get(normalized, normalized)


def _match_path_prefix_module(path: str) -> str | None:
    normalized_path = path.rstrip("/") or path
    for prefix, module in _PATH_PREFIX_MODULE_ALIASES:
        if prefix.endswith("/"):
            if normalized_path.startswith(prefix):
                return module
            continue
        if normalized_path == prefix or normalized_path.startswith(f"{prefix}/"):
            return module
    return None


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

    if matched_module := _match_path_prefix_module(path):
        return matched_module

    segments = [segment for segment in path.split("/") if segment]
    if not segments:
        return None

    for segment in segments:
        if (
            not segment
            or segment.isdigit()
            or (segment.startswith("{") and segment.endswith("}"))
        ):
            continue

        normalized = normalize_operation_log_module(segment)
        if (
            not normalized
            or normalized in _ROUTE_NON_MODULE_SEGMENTS
            or normalized in _ROUTE_SCOPE_SEGMENTS
        ):
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
    if normalized_module and normalized_module not in _INVALID_MODULE_VALUES:
        return normalized_module

    if resource:
        resource_prefix = normalize_operation_log_module(resource.partition(":")[0])
        if resource_prefix and resource_prefix not in _INVALID_MODULE_VALUES:
            return resource_prefix

    return infer_operation_log_module_from_path(path)


__all__ = [
    "infer_operation_log_module_from_path",
    "normalize_operation_log_module",
    "resolve_operation_log_module",
]
