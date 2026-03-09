"""
租户端智能体技能绑定路由（只读）

租户端不允许修改技能绑定，仅提供只读查询（最小权限原则）。
"""

from fastapi import APIRouter, Request

from app.core.deps import ActiveTenantAdmin, DbSession
from app.core.i18n import _
from app.core.response import success
from app.exceptions import NotFoundException
from app.rbac.decorators import action_read
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
