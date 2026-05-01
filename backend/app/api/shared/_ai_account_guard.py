"""AI account availability helpers for API controllers."""

from __future__ import annotations

from typing import Any, Final

from fastapi import HTTPException, Request, status

from app.core.i18n import _
from app.enums.rbac import PermissionScope, PermissionType
from app.rbac.decorators import PermissionMeta
from app.rbac.registry import permission_registry
from app.rbac.services.permission_domains.checks import PermissionCheckDomain

AI_ENABLED_FIELD: Final = "ai_enabled"
ORGANIZATION_MANAGE_MEMBER_AI_PERMISSION: Final = "organization:manage_member_ai"
TENANT_ADMIN_MANAGE_AI_PERMISSION: Final = "tenant_admin:manage_ai"

_AI_ENABLED_NOT_PROVIDED = object()


def register_ai_switch_operation_permission(
    *,
    scope: PermissionScope,
    resource: str,
    action: str,
    name: str,
    parent_resource: str,
    sort_order: int = 47,
) -> None:
    """Register assignable AI switch operation permissions."""
    if scope == PermissionScope.ADMIN:
        scope_prefix = "admin"
    elif scope == PermissionScope.USER:
        scope_prefix = "user"
    else:
        scope_prefix = "tenant"

    permission_registry.register(
        PermissionMeta(
            code=f"{resource}:{action}",
            name=name,
            type=PermissionType.OPERATION,
            scope=scope,
            resource=resource,
            action=action,
            parent_code=f"menu:{scope_prefix}.{parent_resource}",
            sort_order=sort_order,
        )
    )


async def resolve_authorized_ai_enabled_override(
    *,
    request: Request,
    data: Any,
    permission_code: str,
) -> bool | None:
    """
    Return an explicitly submitted ai_enabled value after checking permission.

    The management schemas are updated in separate workstreams, so this helper
    accepts either a parsed Pydantic field or a raw JSON body field. Missing
    ai_enabled means the normal create/update permission is enough.
    """
    value = await _extract_ai_enabled_value(request, data)
    if value is _AI_ENABLED_NOT_PROVIDED:
        return None

    _require_permission(request, permission_code)
    if not isinstance(value, bool):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_("common.validation_error"),
        )
    return value


async def _extract_ai_enabled_value(request: Request, data: Any) -> Any:
    fields_set = getattr(data, "model_fields_set", None)
    if fields_set is None:
        fields_set = getattr(data, "__fields_set__", set())

    if AI_ENABLED_FIELD in fields_set:
        return getattr(data, AI_ENABLED_FIELD, _AI_ENABLED_NOT_PROVIDED)

    try:
        body = await request.json()
    except Exception:
        return _AI_ENABLED_NOT_PROVIDED

    if isinstance(body, dict) and AI_ENABLED_FIELD in body:
        return body[AI_ENABLED_FIELD]
    return _AI_ENABLED_NOT_PROVIDED


def _require_permission(request: Request, permission_code: str) -> None:
    user_permissions = getattr(request.state, "user_permissions", set())
    if not isinstance(user_permissions, set):
        user_permissions = set(user_permissions or [])

    if PermissionCheckDomain.check_permission(user_permissions, permission_code):
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=_("rbac.permission_denied"),
    )


__all__ = [
    "ORGANIZATION_MANAGE_MEMBER_AI_PERMISSION",
    "TENANT_ADMIN_MANAGE_AI_PERMISSION",
    "register_ai_switch_operation_permission",
    "resolve_authorized_ai_enabled_override",
]
