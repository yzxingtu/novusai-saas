"""Tenant plan permission assignment guards."""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.i18n import _
from app.enums import ErrorCode
from app.enums.rbac import PermissionScope
from app.exceptions import BusinessException, NotFoundException
from app.models.auth.permission import Permission


async def normalize_tenant_plan_permission_ids(
    db: AsyncSession,
    *,
    tenant_id: int,
    permission_ids: Iterable[int] | None,
    allowed_scopes: Iterable[str] = (
        PermissionScope.TENANT.value,
        PermissionScope.BOTH.value,
    ),
) -> list[int]:
    """Validate requested permission IDs and require current-plan entitlement."""
    from app.rbac.services.permission_service import PermissionService

    if not permission_ids:
        return []

    deduped = list(dict.fromkeys(permission_ids))
    scope_values = list(dict.fromkeys(allowed_scopes))
    result = await db.execute(
        select(Permission.id).where(
            Permission.id.in_(deduped),
            Permission.scope.in_(scope_values),
            Permission.is_enabled.is_(True),
            Permission.is_deleted.is_(False),
        )
    )
    existing_ids = set(result.scalars().all())
    missing_ids = [
        permission_id for permission_id in deduped if permission_id not in existing_ids
    ]
    if missing_ids:
        raise NotFoundException(message=_("permission.not_found"))

    plan_permissions = await PermissionService(db)._get_tenant_plan_permissions(
        tenant_id
    )
    plan_permission_ids = set() if plan_permissions is None else plan_permissions[1]
    forbidden_ids = [
        permission_id
        for permission_id in deduped
        if permission_id not in plan_permission_ids
    ]
    if forbidden_ids:
        raise BusinessException(
            message=_("rbac.permission_denied"),
            code=ErrorCode.FORBIDDEN,
            data={"forbidden_permission_ids": forbidden_ids},
        )

    return deduped


__all__ = ["normalize_tenant_plan_permission_ids"]
