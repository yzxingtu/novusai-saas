"""
企业端智能体版本管理路由 / Tenant Agent Version Management Routes

提供版本列表、版本详情、版本对比、发布、回滚等接口
Provides version list, version details, version diff, publish, rollback endpoints
"""

from fastapi import APIRouter, Request

from app.core.deps import ActiveTenantAdmin, DbSession
from app.core.i18n import _
from app.core.response import success
from app.rbac.decorators import action_read, action_update
from app.schemas.ai.agent_version import AgentPublishRequest, AgentRollbackRequest
from app.services.ai.agent_service import AgentService

router = APIRouter()


@router.post("/{agent_id}/publish", summary="发布智能体")
@action_update("action.agent.publish")
async def publish_agent(
    request: Request,
    db: DbSession,
    agent_id: int,
    data: AgentPublishRequest,
    tenant_admin: ActiveTenantAdmin,
):
    """
    发布智能体 / Publish agent

    将当前配置冻结为新版本快照，状态设为 published。
    Freezes current config as a new version snapshot, sets status to published.
    权限 / Permission: agent:publish
    """
    from app.api.tenant.agents import _ensure_tenant_owned_agent
    await _ensure_tenant_owned_agent(db, tenant_admin.tenant_id, agent_id)

    service = AgentService(db, tenant_admin.tenant_id)
    agent = await service.publish_agent(
        agent_id,
        change_log=data.change_log,
        created_by=tenant_admin.id,
    )
    await db.commit()

    return success(data=agent.to_dict(), message=_("agent.published"))


@router.post("/{agent_id}/rollback", summary="回滚智能体")
@action_update("action.agent.rollback")
async def rollback_agent(
    request: Request,
    db: DbSession,
    agent_id: int,
    data: AgentRollbackRequest,
    tenant_admin: ActiveTenantAdmin,
):
    """
    回滚智能体到指定版本 / Rollback agent to specified version

    将指定版本的配置回写到主记录，状态重置为 draft。
    Writes specified version config back to main record, resets status to draft.
    权限 / Permission: agent:rollback
    """
    from app.api.tenant.agents import _ensure_tenant_owned_agent
    await _ensure_tenant_owned_agent(db, tenant_admin.tenant_id, agent_id)

    service = AgentService(db, tenant_admin.tenant_id)
    agent = await service.rollback_agent(agent_id, data.version)
    await db.commit()

    return success(
        data=agent.to_dict(),
        message=_("agent.version.rolled_back"),
    )


@router.get("/{agent_id}/versions", summary="获取智能体版本历史")
@action_read("action.agent.versions")
async def list_versions(
    request: Request,
    db: DbSession,
    agent_id: int,
    tenant_admin: ActiveTenantAdmin,
):
    """
    获取智能体版本历史列表（降序） / Get agent version history list (descending)

    权限 / Permission: agent:versions
    """
    service = AgentService(db, tenant_admin.tenant_id)
    versions = await service.get_versions(agent_id)

    return success(data=versions)


# 注意：diff 路由必须在 {version} 之前注册，避免 "diff" 被匹配为版本号
# Note: diff route must be registered before {version} to avoid "diff" being matched as version number
@router.get("/{agent_id}/versions/diff", summary="对比两个版本")
@action_read("action.agent.version_diff")
async def diff_versions(
    request: Request,
    db: DbSession,
    agent_id: int,
    v1: int,
    v2: int,
    tenant_admin: ActiveTenantAdmin,
):
    """
    对比两个版本的字段差异 / Compare field differences between two versions

    Query params: v1, v2
    权限 / Permission: agent:version_diff
    """
    service = AgentService(db, tenant_admin.tenant_id)
    diff = await service.diff_versions(agent_id, v1, v2)

    return success(data=diff)


@router.get("/{agent_id}/versions/{version}", summary="获取智能体版本详情")
@action_read("action.agent.version_detail")
async def get_version_detail(
    request: Request,
    db: DbSession,
    agent_id: int,
    version: int,
    tenant_admin: ActiveTenantAdmin,
):
    """
    获取智能体指定版本的完整配置快照 / Get full config snapshot of specified agent version

    权限 / Permission: agent:version_detail
    """
    service = AgentService(db, tenant_admin.tenant_id)
    detail = await service.get_version_detail(agent_id, version)

    return success(data=detail)
