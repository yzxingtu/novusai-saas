"""
租户端智能体技能绑定路由

提供技能包绑定、解绑、批量绑定等接口
"""

from fastapi import APIRouter, Request

from app.core.deps import DbSession, ActiveTenantAdmin
from app.core.i18n import _
from app.core.response import success, created, deleted
from app.exceptions import NotFoundException
from app.rbac.decorators import action_read, action_update
from app.schemas.ai.agent_skill_binding import (
    AgentSkillBindRequest,
    AgentSkillBatchBindRequest,
    AgentSkillBindingUpdate,
)
from app.services.ai.agent_service import AgentService
from app.services.ai.agent_skill_binding_service import AgentSkillBindingService

router = APIRouter()


@router.get("/{agent_id}/skills", summary="获取智能体技能包绑定列表")
@action_read("action.agent.skills")
async def get_agent_skills(
    request: Request,
    db: DbSession,
    agent_id: int,
    tenant_admin: ActiveTenantAdmin,
):
    """
    获取智能体绑定的所有技能包（含 SkillPackage 详情）
    """
    agent_svc = AgentService(db, tenant_admin.tenant_id)
    agent = await agent_svc.get_by_id(agent_id)
    if not agent:
        raise NotFoundException(message=_("agent.error.not_found"))

    binding_service = AgentSkillBindingService(db, tenant_admin.tenant_id)
    result = await binding_service.get_agent_packages(agent_id)
    return success(data=result)


@router.post("/{agent_id}/skills", summary="绑定技能包到智能体")
@action_update("action.agent.bind_skill")
async def bind_skill(
    request: Request,
    db: DbSession,
    agent_id: int,
    data: AgentSkillBindRequest,
    tenant_admin: ActiveTenantAdmin,
):
    """
    绑定单个技能包到智能体
    """
    agent_svc = AgentService(db, tenant_admin.tenant_id)
    agent = await agent_svc.get_by_id(agent_id)
    if not agent:
        raise NotFoundException(message=_("agent.error.not_found"))

    binding_service = AgentSkillBindingService(db, tenant_admin.tenant_id)
    binding = await binding_service.bind_package(
        agent_id=agent_id,
        package_id=data.package_id,
        config_override=data.config_override,
        sort_order=data.sort_order,
        consent_mode=data.consent_mode,
    )
    await db.commit()
    return created(data=binding.to_dict())


@router.put("/{agent_id}/skills/batch", summary="批量绑定技能包（替换模式）")
@action_update("action.agent.batch_bind_skills")
async def batch_bind_skills(
    request: Request,
    db: DbSession,
    agent_id: int,
    data: AgentSkillBatchBindRequest,
    tenant_admin: ActiveTenantAdmin,
):
    """
    批量绑定技能包（替换模式：先清空再批量插入）
    """
    agent_svc = AgentService(db, tenant_admin.tenant_id)
    agent = await agent_svc.get_by_id(agent_id)
    if not agent:
        raise NotFoundException(message=_("agent.error.not_found"))

    binding_service = AgentSkillBindingService(db, tenant_admin.tenant_id)
    bindings = await binding_service.batch_bind(
        agent_id=agent_id,
        package_ids=data.package_ids,
    )
    await db.commit()
    return success(data=[b.to_dict() for b in bindings])


@router.put("/{agent_id}/skills/{binding_id}", summary="更新技能绑定配置")
@action_update("action.agent.update_skill_binding")
async def update_skill_binding(
    request: Request,
    db: DbSession,
    agent_id: int,
    binding_id: int,
    data: AgentSkillBindingUpdate,
    tenant_admin: ActiveTenantAdmin,
):
    """
    更新技能绑定（enabled / config_override / sort_order）
    """
    agent_svc = AgentService(db, tenant_admin.tenant_id)
    agent = await agent_svc.get_by_id(agent_id)
    if not agent:
        raise NotFoundException(message=_("agent.error.not_found"))

    binding_service = AgentSkillBindingService(db, tenant_admin.tenant_id)

    # 校验 binding_id 归属 agent_id
    binding = await binding_service.get_by_id(binding_id)
    if not binding or binding.agent_id != agent_id:
        raise NotFoundException(message=_("agent_skill_binding.error.binding_not_found"))

    updated = await binding_service.update_binding(
        binding_id=binding_id,
        data=data.model_dump(exclude_unset=True),
    )
    await db.commit()
    return success(data=updated.to_dict())


@router.delete("/{agent_id}/skills/{package_id}", summary="解绑技能包")
@action_update("action.agent.unbind_skill")
async def unbind_skill(
    request: Request,
    db: DbSession,
    agent_id: int,
    package_id: int,
    tenant_admin: ActiveTenantAdmin,
):
    """
    解绑指定技能包
    """
    agent_svc = AgentService(db, tenant_admin.tenant_id)
    agent = await agent_svc.get_by_id(agent_id)
    if not agent:
        raise NotFoundException(message=_("agent.error.not_found"))

    binding_service = AgentSkillBindingService(db, tenant_admin.tenant_id)
    await binding_service.unbind_package(agent_id=agent_id, package_id=package_id)
    await db.commit()
    return deleted()
