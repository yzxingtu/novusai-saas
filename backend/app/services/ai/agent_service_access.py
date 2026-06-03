"""
Agent access & publication parts / 智能体访问与发布配置拆分模块。
"""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from app.core.base_model import utc_now
from app.core.i18n import _
from app.core.logging import LogManager
from app.core.response import serialize_datetime_for_api
from app.enums.agent import AgentPublicationAccessTypeEnum
from app.enums.ai import CallAccessChannelEnum
from app.enums.common import UserRoleEnum
from app.exceptions import BusinessException, NotFoundException
from app.models.ai.agent import Agent
from app.models.tenant.tenant import Tenant
from app.services.ai.agent_service_support import (
    audience_allows_role,
    role_ids_allow,
)

if TYPE_CHECKING:
    from app.schemas.common.query import QuerySpec

logger = LogManager.get_logger("ai.agent_service")


async def get_access_config(svc: Any, agent_id: int) -> dict[str, Any]:
    """获取智能体访问权限配置（仅角色 ID 列表）/ Get agent access config (role ID lists only)."""
    agent = await svc.repo.get_by_id(agent_id)
    if not agent:
        raise NotFoundException(message=_("agent.error.not_found"))

    access_repo = svc._get_access_repo()
    access = await access_repo.get_by_agent_id(agent_id)

    return {
        "agent_id": agent_id,
        "admin_role_ids": getattr(access, "admin_role_ids", None) if access else None,
        "tenant_role_ids": getattr(access, "tenant_role_ids", None) if access else None,
    }


async def update_access_config(
    svc: Any,
    agent_id: int,
    patch: dict[str, Any],
) -> dict[str, Any]:
    """更新智能体访问权限配置（仅角色 ID 列表）/ Update agent access config (role ID lists only)."""
    agent = await svc.repo.get_by_id(agent_id)
    if not agent:
        raise NotFoundException(message=_("agent.error.not_found"))

    allowed = frozenset({"admin_role_ids", "tenant_role_ids"})
    data = {k: v for k, v in patch.items() if k in allowed}

    access_repo = svc._get_access_repo()
    access = await access_repo.upsert(agent_id, data)

    logger.info(
        "Agent access updated: agent_id={} tenant_id={}",
        agent_id,
        svc.tenant_id,
    )

    return {
        "agent_id": agent_id,
        "admin_role_ids": getattr(access, "admin_role_ids", None),
        "tenant_role_ids": getattr(access, "tenant_role_ids", None),
    }


async def get_publication_config(svc: Any, agent_id: int) -> dict[str, Any]:
    """获取企业用户发布配置 / Get tenant-user publication config."""
    agent = await svc.repo.get_by_id(agent_id)
    if not agent:
        raise NotFoundException(message=_("agent.error.not_found"))

    publication_repo = svc._get_publication_repo()
    publication = await publication_repo.get_by_agent_id(agent_id)

    return {
        "agent_id": agent_id,
        "publication_id": getattr(publication, "id", None),
        "enabled_for_users": bool(getattr(publication, "enabled_for_users", False)),
        "access_type": getattr(
            publication,
            "access_type",
            AgentPublicationAccessTypeEnum.ALL_USERS.value,
        ),
        "tenant_user_role_ids": getattr(publication, "tenant_user_role_ids", None),
        "tenant_user_ids": getattr(publication, "tenant_user_ids", None),
        "org_node_ids": getattr(publication, "org_node_ids", None),
        "published_at": (
            serialize_datetime_for_api(publication.published_at)
            if publication
            else None
        ),
        "published_by": getattr(publication, "published_by", None),
    }


async def update_publication_config(
    svc: Any,
    agent_id: int,
    *,
    enabled_for_users: bool,
    access_type: str,
    tenant_user_role_ids: list[int] | None = None,
    tenant_user_ids: list[int] | None = None,
    org_node_ids: list[int] | None = None,
    published_by: int | None = None,
) -> dict[str, Any]:
    """更新企业用户发布配置 / Update tenant-user publication config."""
    agent = await svc.repo.get_by_id(agent_id)
    if not agent:
        raise NotFoundException(message=_("agent.error.not_found"))

    if (
        bool(enabled_for_users)
        and access_type == AgentPublicationAccessTypeEnum.ORG_NODE.value
    ):
        raise BusinessException(
            message=_("agent.error.publication_org_node_not_supported"),
        )

    publication_repo = svc._get_publication_repo()
    await publication_repo.upsert(
        agent_id,
        {
            "enabled_for_users": bool(enabled_for_users),
            "access_type": access_type,
            "tenant_user_role_ids": tenant_user_role_ids,
            "tenant_user_ids": tenant_user_ids,
            "org_node_ids": org_node_ids,
            "published_at": utc_now() if enabled_for_users else None,
            "published_by": published_by if enabled_for_users else None,
        },
    )

    return await get_publication_config(svc, agent_id)


def publication_allows_user(
    publication: Any | None,
    *,
    user_id: int,
    user_role_id: int | None = None,
) -> bool:
    """判断企业用户发布规则是否允许当前用户 / Check whether publication allows current tenant user."""
    if not publication or not getattr(publication, "enabled_for_users", False):
        return False

    access_type = getattr(
        publication,
        "access_type",
        AgentPublicationAccessTypeEnum.ALL_USERS.value,
    )
    if access_type == AgentPublicationAccessTypeEnum.ALL_USERS.value:
        return True
    if access_type == AgentPublicationAccessTypeEnum.SPECIFIC_USERS.value:
        return user_id in (getattr(publication, "tenant_user_ids", None) or [])
    if access_type == AgentPublicationAccessTypeEnum.TENANT_USER_ROLES.value:
        return role_ids_allow(
            getattr(publication, "tenant_user_role_ids", None),
            user_role_id,
        )
    if access_type == AgentPublicationAccessTypeEnum.ORG_NODE.value:
        return False
    return False


async def check_user_access(
    svc: Any,
    agent_id: int,
    user_id: int,
    user_role: str = UserRoleEnum.TENANT_USER.value,
    user_role_id: int | None = None,
) -> bool:
    """检查用户是否有权访问指定智能体 / Check if user can access agent."""
    agent = await svc.repo.get_by_id(agent_id)
    if not agent:
        raise NotFoundException(message=_("agent.error.not_found"))

    target_audience = getattr(agent, "target_audience", None)
    if not audience_allows_role(target_audience, user_role):
        return False

    if user_role == UserRoleEnum.PLATFORM_ADMIN.value:
        access = await svc._get_access_repo().get_by_agent_id(agent_id)
        return role_ids_allow(
            getattr(access, "admin_role_ids", None) if access else None,
            user_role_id,
        )

    if user_role == UserRoleEnum.TENANT_ADMIN.value:
        access = await svc._get_access_repo().get_by_agent_id(agent_id)
        return role_ids_allow(
            getattr(access, "tenant_role_ids", None) if access else None,
            user_role_id,
        )

    publication = await svc._get_publication_repo().get_by_agent_id(agent_id)
    return publication_allows_user(
        publication,
        user_id=user_id,
        user_role_id=user_role_id,
    )


async def list_user_accessible_agents(
    svc: Any,
    user_id: int,
    user_role_id: int | None,
    spec: QuerySpec,
) -> tuple[list[Agent], int]:
    """获取终端用户可访问的智能体列表 / List agents accessible to end user."""
    return await svc.repo.query_user_accessible_list(
        spec=spec,
        user_id=user_id,
        user_role_id=user_role_id,
    )


async def build_usage_attribution_context(
    svc: Any,
    *,
    agent: Agent,
    user_id: int | None,
    user_role: str,
    user_role_id: int | None = None,
) -> dict[str, Any]:
    """构建调用时不可变计费归属上下文 / Build immutable billing attribution context at call time."""
    publication = None
    billing_tenant_id = None
    access_channel = None

    if user_role == UserRoleEnum.TENANT_ADMIN.value:
        billing_tenant_id = svc.tenant_id
        access_channel = CallAccessChannelEnum.TENANT_ADMIN.value
    elif user_role == UserRoleEnum.TENANT_USER.value:
        billing_tenant_id = svc.tenant_id
        access_channel = CallAccessChannelEnum.TENANT_USER.value
        publication = await svc._get_publication_repo().get_by_agent_id(agent.id)
        if not publication_allows_user(
            publication,
            user_id=user_id or 0,
            user_role_id=user_role_id,
        ):
            raise BusinessException(message=_("agent.access.error.no_permission"))
    else:
        access_channel = CallAccessChannelEnum.ADMIN_INTERNAL.value

    billing_tenant_name_snapshot = None
    if billing_tenant_id is not None:
        row = await svc.db.execute(
            select(Tenant.name).where(Tenant.id == billing_tenant_id).limit(1),
        )
        billing_tenant_name_snapshot = row.scalar_one_or_none()
        if inspect.isawaitable(billing_tenant_name_snapshot):
            billing_tenant_name_snapshot = await billing_tenant_name_snapshot

    _own_tid = getattr(agent, "owner_tenant_id", None)
    return {
        "billing_tenant_id": billing_tenant_id,
        "actor_user_id": user_id,
        "actor_user_type": user_role,
        "access_channel": access_channel,
        "agent_owner_type": ("platform" if _own_tid is None else "tenant"),
        "agent_owner_tenant_id": _own_tid,
        "agent_resource_scope": getattr(agent, "scope", None),
        "tenant_publication_id": getattr(publication, "id", None)
        if publication
        else None,
        "publication_enabled_snapshot": (
            bool(getattr(publication, "enabled_for_users", False))
            if publication is not None
            else None
        ),
        "publication_access_type_snapshot": (
            getattr(publication, "access_type", None)
            if publication is not None
            else None
        ),
        "agent_id_snapshot": agent.id,
        "agent_name_snapshot": getattr(agent, "name", None),
        "billing_tenant_name_snapshot": billing_tenant_name_snapshot,
    }
