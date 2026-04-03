"""
Tenant system agent assignment resolve API / 企业端系统智能体绑定解析 API

Provides feature-code resolve for tenant-side AI features.
/ 为企业端 AI 功能提供 feature_code 解析能力。
"""

from fastapi import APIRouter

from app.core.deps import ActiveTenantAdmin, DbSession
from app.core.response import success
from app.rbac.decorators import auth_only
from app.services.system.agent_assignment_service import AgentAssignmentService

router = APIRouter(prefix="/ai/agent-assignments", tags=["Tenant Agent Assignments"])


@router.get("/resolve/{feature_code}", summary="解析功能绑定的智能体")
@auth_only
async def resolve_assignment(
    feature_code: str,
    db: DbSession,
    tenant_admin: ActiveTenantAdmin,
):
    """
    企业公共 resolve API：按 feature_code 获取当前企业可用的 agent_id。
    / Tenant public resolve: get tenant-resolved agent_id by feature_code.

    仅需登录，无需特殊权限。返回 agent_id + agent_name + config。
    / Login required only, no special permissions needed. Returns agent_id + agent_name + config.
    """
    service = AgentAssignmentService(db)
    assignment = await service.resolve_for_tenant(feature_code, tenant_admin.tenant_id)
    if not assignment:
        return success(
            data={
                "feature_code": feature_code,
                "agent_id": None,
                "agent_name": None,
                "config": None,
                "is_active": False,
            }
        )

    agent_name = None
    try:
        agent_obj = getattr(assignment, "agent", None)
        if agent_obj is not None and not getattr(agent_obj, "is_deleted", False):
            agent_name = agent_obj.name
    except AttributeError:
        pass

    return success(
        data={
            "feature_code": assignment.feature_code,
            "agent_id": assignment.agent_id,
            "agent_name": agent_name,
            "config": assignment.config,
            "is_active": assignment.is_active,
        }
    )


__all__ = ["router"]
