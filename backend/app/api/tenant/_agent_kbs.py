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
    AgentPlatformKbSuppressRequest,
)
from app.services.ai.agent_kb_binding_service import AgentKBBindingService
from app.services.ai.agent_service import AgentService
from app.services.ai.tenant_platform_kb_suppression_service import (
    TenantPlatformKbSuppressionService,
)

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
    获取智能体绑定的所有知识库（含 KnowledgeBase 详情）/ Get agent bound knowledge bases with KB details.
    """
    agent_svc = AgentService(db, tenant_admin.tenant_id)
    agent = await agent_svc.get_by_id(agent_id)
    if not agent:
        raise NotFoundException(message=_("agent.error.not_found"))

    kb_service = AgentKBBindingService(db, tenant_admin.tenant_id)
    result = await kb_service.get_agent_kb_bindings(
        agent_id, merge_platform_bindings=True
    )
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
    from app.api.tenant.agents import _ensure_agent_kb_mutations_allowed

    await _ensure_agent_kb_mutations_allowed(db, tenant_admin.tenant_id, agent_id)

    kb_service = AgentKBBindingService(db, tenant_admin.tenant_id)
    binding = await kb_service.bind_kb(
        agent_id=agent_id,
        knowledge_base_id=data.knowledge_base_id,
        weight=data.weight,
        sort_order=data.sort_order,
        enabled=data.enabled,
    )
    await db.commit()
    return created(data=kb_service.serialize_binding_public(binding))


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
    批量绑定知识库（替换模式：先清空再批量插入）/ Batch bind knowledge bases (replace mode).
    """
    from app.api.tenant.agents import _ensure_agent_kb_mutations_allowed

    await _ensure_agent_kb_mutations_allowed(db, tenant_admin.tenant_id, agent_id)

    kb_service = AgentKBBindingService(db, tenant_admin.tenant_id)
    bindings = await kb_service.batch_bind(
        agent_id=agent_id,
        knowledge_base_ids=data.knowledge_base_ids,
    )
    await db.commit()
    return success(data=[kb_service.serialize_binding_public(b) for b in bindings])


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
    from app.api.tenant.agents import _ensure_agent_kb_mutations_allowed

    await _ensure_agent_kb_mutations_allowed(db, tenant_admin.tenant_id, agent_id)

    kb_service = AgentKBBindingService(db, tenant_admin.tenant_id)

    binding = await kb_service.get_by_id(binding_id)
    if not binding or binding.agent_id != agent_id:
        raise NotFoundException(message=_("agent_kb_binding.error.binding_not_found"))

    updated = await kb_service.update_binding(
        binding_id=binding_id,
        data=data.model_dump(exclude_unset=True),
    )
    await db.commit()
    return success(data=kb_service.serialize_binding_public(updated))


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
    from app.api.tenant.agents import _ensure_agent_kb_mutations_allowed

    await _ensure_agent_kb_mutations_allowed(db, tenant_admin.tenant_id, agent_id)

    kb_service = AgentKBBindingService(db, tenant_admin.tenant_id)
    await kb_service.unbind_kb(agent_id=agent_id, knowledge_base_id=knowledge_base_id)
    await db.commit()
    return deleted()


@router.post(
    "/{agent_id}/knowledge-bases/platform-suppressions",
    summary="本企业停用平台全局知识库（不参与 RAG）",
)
@action_update("action.agent.update_kb_binding")
async def suppress_platform_kb(
    request: Request,
    db: DbSession,
    agent_id: int,
    data: AgentPlatformKbSuppressRequest,
    tenant_admin: ActiveTenantAdmin,
):
    """
    对管理端配置的平台全局绑定，本企业选择不参与检索 / Opt out of platform KB for RAG.
    """
    from app.api.tenant.agents import _ensure_agent_kb_mutations_allowed

    await _ensure_agent_kb_mutations_allowed(db, tenant_admin.tenant_id, agent_id)
    svc = TenantPlatformKbSuppressionService(db, tenant_admin.tenant_id)
    payload = await svc.suppress(agent_id, data.knowledge_base_id)
    await db.commit()
    return success(data=payload)


@router.delete(
    "/{agent_id}/knowledge-bases/platform-suppressions/{knowledge_base_id}",
    summary="取消本企业对平台全局知识库的停用",
)
@action_update("action.agent.update_kb_binding")
async def unsuppress_platform_kb(
    request: Request,
    db: DbSession,
    agent_id: int,
    knowledge_base_id: int,
    tenant_admin: ActiveTenantAdmin,
):
    """恢复使用平台全局知识库参与 RAG / Remove tenant opt-out."""
    from app.api.tenant.agents import _ensure_agent_kb_mutations_allowed

    await _ensure_agent_kb_mutations_allowed(db, tenant_admin.tenant_id, agent_id)
    svc = TenantPlatformKbSuppressionService(db, tenant_admin.tenant_id)
    await svc.unsuppress(agent_id, knowledge_base_id)
    await db.commit()
    return deleted()
