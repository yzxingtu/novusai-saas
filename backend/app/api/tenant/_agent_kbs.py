"""
企业端智能体知识库绑定路由 / Tenant Agent Knowledge Base Binding Routes

提供知识库绑定、解绑、批量绑定等接口
Provides knowledge base bind, unbind, batch bind endpoints
"""

from fastapi import APIRouter, Request

from app.core.deps import ActiveTenantAdmin, DbSession
from app.core.i18n import _
from app.core.response import created, deleted, success
from app.exceptions import NotFoundException
from app.rbac.decorators import action_read, action_update
from app.schemas.ai.agent_kb_binding import (
    AgentKBBatchBindRequest,
    AgentKBBindingUpdate,
    AgentKBBindRequest,
)
from app.services.ai.agent_kb_binding_service import AgentKBBindingService
from app.services.ai.agent_service import AgentService

router = APIRouter()


@router.get("/{agent_id}/knowledge-bases", summary="获取智能体知识库绑定列表")
@action_read("action.agent.knowledge_bases")
async def get_agent_kbs(
    request: Request,
    db: DbSession,
    agent_id: int,
    tenant_admin: ActiveTenantAdmin,
):
    """
    获取智能体绑定的所有知识库（含 KnowledgeBase 详情）
    Get all knowledge bases bound to agent (with KnowledgeBase details)
    """
    agent_svc = AgentService(db, tenant_admin.tenant_id)
    agent = await agent_svc.get_by_id(agent_id)
    if not agent:
        raise NotFoundException(message=_("agent.error.not_found"))

    kb_service = AgentKBBindingService(db, tenant_admin.tenant_id)
    result = await kb_service.get_agent_kb_bindings(agent_id)
    return success(data=result)


@router.post("/{agent_id}/knowledge-bases", summary="绑定知识库到智能体")
@action_update("action.agent.bind_kb")
async def bind_kb(
    request: Request,
    db: DbSession,
    agent_id: int,
    data: AgentKBBindRequest,
    tenant_admin: ActiveTenantAdmin,
):
    """
    绑定单个知识库到智能体 / Bind a single knowledge base to agent
    """
    from app.api.tenant.agents import _ensure_tenant_owned_agent
    await _ensure_tenant_owned_agent(db, tenant_admin.tenant_id, agent_id)

    kb_service = AgentKBBindingService(db, tenant_admin.tenant_id)
    binding = await kb_service.bind_kb(
        agent_id=agent_id,
        knowledge_base_id=data.knowledge_base_id,
        weight=data.weight,
        sort_order=data.sort_order,
        enabled=data.enabled,
    )
    await db.commit()
    return created(data=binding.to_dict())


@router.put("/{agent_id}/knowledge-bases/batch", summary="批量绑定知识库（替换模式）")
@action_update("action.agent.batch_bind_kbs")
async def batch_bind_kbs(
    request: Request,
    db: DbSession,
    agent_id: int,
    data: AgentKBBatchBindRequest,
    tenant_admin: ActiveTenantAdmin,
):
    """
    批量绑定知识库（替换模式：先清空再批量插入）
    Batch bind knowledge bases (replace mode: clear first then batch insert)
    """
    from app.api.tenant.agents import _ensure_tenant_owned_agent
    await _ensure_tenant_owned_agent(db, tenant_admin.tenant_id, agent_id)

    kb_service = AgentKBBindingService(db, tenant_admin.tenant_id)
    bindings = await kb_service.batch_bind(
        agent_id=agent_id,
        knowledge_base_ids=data.knowledge_base_ids,
    )
    await db.commit()
    return success(data=[b.to_dict() for b in bindings])


@router.put("/{agent_id}/knowledge-bases/{binding_id}", summary="更新知识库绑定配置")
@action_update("action.agent.update_kb_binding")
async def update_kb_binding(
    request: Request,
    db: DbSession,
    agent_id: int,
    binding_id: int,
    data: AgentKBBindingUpdate,
    tenant_admin: ActiveTenantAdmin,
):
    """
    更新知识库绑定（weight / enabled / sort_order）
    Update knowledge base binding (weight / enabled / sort_order)
    """
    from app.api.tenant.agents import _ensure_tenant_owned_agent
    await _ensure_tenant_owned_agent(db, tenant_admin.tenant_id, agent_id)

    kb_service = AgentKBBindingService(db, tenant_admin.tenant_id)

    binding = await kb_service.get_by_id(binding_id)
    if not binding or binding.agent_id != agent_id:
        raise NotFoundException(message=_("agent_kb_binding.error.binding_not_found"))

    updated = await kb_service.update_binding(
        binding_id=binding_id,
        data=data.model_dump(exclude_unset=True),
    )
    await db.commit()
    return success(data=updated.to_dict())


@router.delete("/{agent_id}/knowledge-bases/{knowledge_base_id}", summary="解绑知识库")
@action_update("action.agent.unbind_kb")
async def unbind_kb(
    request: Request,
    db: DbSession,
    agent_id: int,
    knowledge_base_id: int,
    tenant_admin: ActiveTenantAdmin,
):
    """
    解绑指定知识库 / Unbind specified knowledge base
    """
    from app.api.tenant.agents import _ensure_tenant_owned_agent
    await _ensure_tenant_owned_agent(db, tenant_admin.tenant_id, agent_id)

    kb_service = AgentKBBindingService(db, tenant_admin.tenant_id)
    await kb_service.unbind_kb(agent_id=agent_id, knowledge_base_id=knowledge_base_id)
    await db.commit()
    return deleted()
