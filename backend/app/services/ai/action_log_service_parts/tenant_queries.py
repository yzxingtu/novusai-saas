"""Tenant-side query helpers for AI action logs."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai.agent import Agent
from app.models.tenant.tenant_admin import TenantAdmin
from app.models.tenant.tenant_user import TenantUser
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


async def load_operator_meta_map(
    db: AsyncSession,
    tenant_id: int,
    operator_refs: set[tuple[str | None, int]],
) -> dict[tuple[str, int], dict[str, Any]]:
    if not operator_refs:
        return {}

    from app.models.auth.tenant_admin_role import TenantAdminRole
    from app.models.auth.tenant_user_role import TenantUserRole
    from app.models.org.tenant_org_node import TenantOrgNode

    tenant_admin_ids = {
        operator_id
        for operator_type, operator_id in operator_refs
        if operator_type in {None, "tenant_admin"}
    }
    tenant_user_ids = {
        operator_id
        for operator_type, operator_id in operator_refs
        if operator_type in {None, "tenant_user"}
    }

    operator_meta_map: dict[tuple[str, int], dict[str, Any]] = {}

    if tenant_admin_ids:
        stmt = (
            select(
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
                TenantAdmin.tenant_id == tenant_id,
                TenantAdmin.id.in_(tenant_admin_ids),
                TenantAdmin.is_deleted.is_(False),
            )
        )
        result = await db.execute(stmt)
        for row in result.all():
            operator_meta_map[("tenant_admin", row.id)] = _build_operator_meta(
                operator_type="tenant_admin",
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
                is_owner=bool(row.is_owner),
            )

    if tenant_user_ids:
        user_stmt = (
            select(
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
                TenantUser.tenant_id == tenant_id,
                TenantUser.id.in_(tenant_user_ids),
                TenantUser.is_deleted.is_(False),
            )
        )
        user_result = await db.execute(user_stmt)
        for row in user_result.all():
            operator_meta_map[("tenant_user", row.id)] = _build_operator_meta(
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

    return operator_meta_map


__all__ = [
    "load_agent_meta_map",
    "load_operator_meta_map",
]
