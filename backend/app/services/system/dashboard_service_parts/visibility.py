"""
Dashboard visibility helpers / 仪表盘可见性条件
"""

from __future__ import annotations

from sqlalchemy import and_, or_

from app.enums.common import ResourceScopeEnum
from app.models.ai.agent import Agent
from app.models.ai.knowledge_base import KnowledgeBase
from app.repositories.system.resource_tenant_assignment_repository import (
    assigned_resource_ids_subquery,
)

_ASSIGNED_SCOPES = (
    ResourceScopeEnum.SELECTED_TENANTS.value,
    ResourceScopeEnum.ADMIN_AND_SELECTED_TENANTS.value,
)


def _visible_agent_condition(tenant_id: int):
    assigned_subq = assigned_resource_ids_subquery("agent", tenant_id)
    platform_visible = or_(
        Agent.scope.in_(
            [
                ResourceScopeEnum.ALL_TENANTS.value,
                ResourceScopeEnum.GLOBAL_SHARED.value,
            ]
        ),
        and_(
            Agent.scope.in_(_ASSIGNED_SCOPES),
            Agent.id.in_(assigned_subq),
        ),
    )
    return or_(
        Agent.owner_tenant_id == tenant_id,
        and_(Agent.owner_tenant_id.is_(None), platform_visible),
    )


def _visible_kb_condition(tenant_id: int):
    assigned_subq = assigned_resource_ids_subquery("knowledge_base", tenant_id)
    tenant_owned_visible = and_(
        KnowledgeBase.owner_tenant_id == tenant_id,
        KnowledgeBase.scope == ResourceScopeEnum.ALL_TENANTS.value,
    )
    platform_visible = and_(
        KnowledgeBase.owner_tenant_id.is_(None),
        KnowledgeBase.scope.in_(
            [
                ResourceScopeEnum.ALL_TENANTS.value,
                ResourceScopeEnum.GLOBAL_SHARED.value,
            ]
        ),
    )
    assigned_visible = and_(
        KnowledgeBase.scope.in_(_ASSIGNED_SCOPES),
        KnowledgeBase.id.in_(assigned_subq),
    )
    global_shared_visible = KnowledgeBase.scope == ResourceScopeEnum.GLOBAL_SHARED.value
    return or_(
        tenant_owned_visible,
        platform_visible,
        global_shared_visible,
        assigned_visible,
    )
