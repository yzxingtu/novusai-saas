"""Admin-side query helpers for AI action logs."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.configs.service import PLATFORM_TENANT_ID
from app.models.ai.action_log import AIActionLog
from app.models.ai.agent import Agent
from app.models.system.admin import Admin
from app.models.tenant.tenant import Tenant
from app.models.tenant.tenant_admin import TenantAdmin
from app.models.tenant.tenant_user import TenantUser
from app.services.ai.action_log_service_parts.normalization import _normalize_operator_type
from app.services.ai.action_log_service_parts.snapshots import _build_operator_meta


async def load_agent_meta_map(
    db: AsyncSession,
    agent_ids: set[int],
) -> dict[int, dict[str, Any]]:
    if not agent_ids:
        return {}

    stmt = select(Agent.id, Agent.name, Agent.avatar).where(
        Agent.id.in_(agent_ids),
        Agent.is_deleted.is_(False),
    )
    result = await db.execute(stmt)
    return {
        row.id: {
            "agent_avatar": row.avatar,
            "agent_name": row.name,
        }
        for row in result.all()
    }


async def load_tenant_meta_map(
    db: AsyncSession,
    tenant_ids: set[int],
) -> dict[int, dict[str, str | None]]:
    positive_tenant_ids = {
        tenant_id for tenant_id in tenant_ids if tenant_id > PLATFORM_TENANT_ID
    }
    tenant_meta_map: dict[int, dict[str, str | None]] = {
        PLATFORM_TENANT_ID: {
            "tenant_name": None,
            "tenant_code": "platform_admin",
        },
    }

    if not positive_tenant_ids:
        return tenant_meta_map

    stmt = select(Tenant.id, Tenant.name, Tenant.code).where(
        Tenant.id.in_(positive_tenant_ids),
        Tenant.is_deleted.is_(False),
    )
    result = await db.execute(stmt)
    for row in result.all():
        tenant_meta_map[row.id] = {
            "tenant_name": row.name,
            "tenant_code": row.code,
        }
    return tenant_meta_map


async def load_operator_meta_map(
    db: AsyncSession,
    logs: list[AIActionLog],
) -> dict[tuple[int, str, int], dict[str, Any]]:
    from app.models.auth.admin_role import AdminRole
    from app.models.auth.tenant_admin_role import TenantAdminRole
    from app.models.auth.tenant_user_role import TenantUserRole
    from app.models.org.admin_org_node import AdminOrgNode
    from app.models.org.tenant_org_node import TenantOrgNode

    platform_operator_ids = {
        log.operator_id
        for log in logs
        if (log.tenant_id or PLATFORM_TENANT_ID) == PLATFORM_TENANT_ID
        and log.operator_id
    }
    tenant_admin_pairs = {
        (log.tenant_id, log.operator_id)
        for log in logs
        if (log.tenant_id or PLATFORM_TENANT_ID) != PLATFORM_TENANT_ID
        and log.tenant_id
        and log.operator_id
        and _normalize_operator_type(log.operator_type) in {None, "tenant_admin"}
    }
    tenant_user_pairs = {
        (log.tenant_id, log.operator_id)
        for log in logs
        if (log.tenant_id or PLATFORM_TENANT_ID) != PLATFORM_TENANT_ID
        and log.tenant_id
        and log.operator_id
        and _normalize_operator_type(log.operator_type) in {None, "tenant_user"}
    }

    operator_meta_map: dict[tuple[int, str, int], dict[str, Any]] = {}

    if platform_operator_ids:
        stmt = (
            select(
                Admin.id,
                Admin.username,
                Admin.nickname,
                Admin.avatar,
                Admin.org_node_id,
                Admin.is_active,
                Admin.is_super,
                AdminRole.name.label("role_name"),
                AdminOrgNode.name.label("org_node_name"),
                AdminOrgNode.leader_id.label("org_leader_id"),
            )
            .select_from(Admin)
            .join(AdminRole, AdminRole.id == Admin.role_id, isouter=True)
            .join(AdminOrgNode, AdminOrgNode.id == Admin.org_node_id, isouter=True)
            .where(
                Admin.id.in_(platform_operator_ids),
                Admin.is_deleted.is_(False),
            )
        )
        result = await db.execute(stmt)
        for row in result.all():
            operator_meta_map[(PLATFORM_TENANT_ID, "platform_admin", row.id)] = (
                _build_operator_meta(
                    operator_type="platform_admin",
                    username=row.username,
                    nickname=row.nickname,
                    avatar=row.avatar,
                    org_node_id=row.org_node_id,
                    org_node_name=row.org_node_name,
                    role_name=row.role_name,
                    is_active=row.is_active,
                    is_leader=bool(
                        row.org_leader_id is not None and row.org_leader_id == row.id
                    ),
                    is_owner=bool(row.is_super),
                )
            )

    if tenant_admin_pairs:
        tenant_ids = {tenant_id for tenant_id, _ in tenant_admin_pairs}
        operator_ids = {operator_id for _, operator_id in tenant_admin_pairs}

        stmt = (
            select(
                TenantAdmin.tenant_id,
                TenantAdmin.id,
                TenantAdmin.username,
                TenantAdmin.nickname,
                TenantAdmin.avatar,
                TenantAdmin.org_node_id,
                TenantAdmin.is_active,
                TenantAdmin.is_owner,
                TenantAdminRole.name.label("role_name"),
                TenantOrgNode.name.label("org_node_name"),
                TenantOrgNode.leader_id.label("org_leader_id"),
            )
            .select_from(TenantAdmin)
            .join(
                TenantAdminRole,
                TenantAdminRole.id == TenantAdmin.role_id,
                isouter=True,
            )
            .join(
                TenantOrgNode,
                TenantOrgNode.id == TenantAdmin.org_node_id,
                isouter=True,
            )
            .where(
                TenantAdmin.tenant_id.in_(tenant_ids),
                TenantAdmin.id.in_(operator_ids),
                TenantAdmin.is_deleted.is_(False),
            )
        )
        result = await db.execute(stmt)
        for row in result.all():
            operator_meta_map[(row.tenant_id, "tenant_admin", row.id)] = (
                _build_operator_meta(
                    operator_type="tenant_admin",
                    username=row.username,
                    nickname=row.nickname,
                    avatar=row.avatar,
                    org_node_id=row.org_node_id,
                    org_node_name=row.org_node_name,
                    role_name=row.role_name,
                    is_active=row.is_active,
                    is_leader=bool(
                        row.org_leader_id is not None
                        and row.org_leader_id == row.id
                    ),
                    is_owner=bool(row.is_owner),
                )
            )

    if tenant_user_pairs:
        tenant_ids = {tenant_id for tenant_id, _ in tenant_user_pairs}
        operator_ids = {operator_id for _, operator_id in tenant_user_pairs}
        user_stmt = (
            select(
                TenantUser.tenant_id,
                TenantUser.id,
                TenantUser.username,
                TenantUser.nickname,
                TenantUser.avatar,
                TenantUser.org_node_id,
                TenantUser.is_active,
                TenantUserRole.name.label("role_name"),
                TenantOrgNode.name.label("org_node_name"),
            )
            .select_from(TenantUser)
            .join(
                TenantUserRole,
                TenantUserRole.id == TenantUser.role_id,
                isouter=True,
            )
            .join(
                TenantOrgNode,
                TenantOrgNode.id == TenantUser.org_node_id,
                isouter=True,
            )
            .where(
                TenantUser.tenant_id.in_(tenant_ids),
                TenantUser.id.in_(operator_ids),
                TenantUser.is_deleted.is_(False),
            )
        )
        user_result = await db.execute(user_stmt)
        for row in user_result.all():
            operator_meta_map[(row.tenant_id, "tenant_user", row.id)] = (
                _build_operator_meta(
                    operator_type="tenant_user",
                    username=row.username,
                    nickname=row.nickname,
                    avatar=row.avatar,
                    org_node_id=row.org_node_id,
                    org_node_name=row.org_node_name,
                    role_name=row.role_name,
                    is_active=row.is_active,
                    is_leader=False,
                    is_owner=False,
                )
            )

    return operator_meta_map


__all__ = [
    "load_agent_meta_map",
    "load_operator_meta_map",
    "load_tenant_meta_map",
]
