"""
租户端系统智能体绑定 API

提供功能代码到智能体的映射解析 + 租户级覆盖管理
"""

from fastapi import Request
from pydantic import BaseModel as PydanticBaseModel, Field

from app.core.base_controller import TenantController
from app.core.deps import DbSession, ActiveTenantAdmin
from app.core.i18n import _
from app.core.logging import LogManager
from app.core.response import success, deleted
from app.enums.rbac import PermissionScope
from app.exceptions import NotFoundException
from app.rbac.decorators import (
    permission_resource,
    MenuConfig,
    action_read,
    action_update,
    action_delete,
    auth_only,
)
from app.services.system.agent_assignment_service import AgentAssignmentService

logger = LogManager.get_logger("app")


class TenantOverrideRequest(PydanticBaseModel):
    """租户覆盖绑定请求"""
    agent_id: int | None = Field(None, description=_("system_agent_assignment.field.agent_id"))
    config: dict | None = Field(None, description=_("system_agent_assignment.field.config"))


def _build_resolve_result(assignment, feature_code: str) -> dict:
    """构建 resolve 响应"""
    if not assignment:
        return {
            "feature_code": feature_code,
            "agent_id": None,
            "agent_name": None,
            "config": None,
            "is_active": False,
        }
    agent_name = None
    try:
        agent_obj = getattr(assignment, "agent", None)
        if agent_obj is not None:
            agent_name = agent_obj.name
    except AttributeError:
        pass
    return {
        "feature_code": assignment.feature_code,
        "agent_id": assignment.agent_id,
        "agent_name": agent_name,
        "config": assignment.config,
        "is_active": assignment.is_active,
        "is_override": assignment.tenant_id is not None,
    }


def _build_assignment_item(assignment, global_default=None) -> dict:
    """构建绑定列表项（含全局默认对比）"""
    agent_name = None
    agent_avatar = None
    try:
        agent_obj = getattr(assignment, "agent", None)
        if agent_obj is not None:
            agent_name = agent_obj.name
            agent_avatar = agent_obj.avatar
    except AttributeError:
        pass

    is_override = assignment.tenant_id is not None

    # Resolve global default agent info
    gd_agent_id = None
    gd_agent_name = None
    if global_default:
        gd_agent_id = global_default.agent_id
        try:
            gd_agent_obj = getattr(global_default, "agent", None)
            if gd_agent_obj is not None:
                gd_agent_name = gd_agent_obj.name
        except AttributeError:
            pass
    elif not is_override:
        # Non-override item IS the global default
        gd_agent_id = assignment.agent_id
        gd_agent_name = agent_name

    return {
        "feature_code": assignment.feature_code,
        "feature_name": assignment.feature_name,
        "description": assignment.description,
        "agent_id": assignment.agent_id,
        "agent_name": agent_name,
        "agent_avatar": agent_avatar,
        "is_active": assignment.is_active,
        "is_override": is_override,
        "global_agent_id": gd_agent_id,
        "global_agent_name": gd_agent_name,
    }


@permission_resource(
    resource="tenant_agent_assignment",
    name="menu.tenant.agent_assignment",
    scope=PermissionScope.TENANT,
    menu=MenuConfig(
        icon="lucide:plug",
        path="/ai/agent-assignments",
        component="ai/agent-assignments/index",
        parent="ai_workspace",
        sort_order=15,
    ),
)
class TenantAgentAssignmentController(TenantController):
    """
    租户端系统智能体绑定控制器
    """

    prefix = "/ai/agent-assignments"
    tags = [_("menu.tags.tenant_agent_assignment")]

    def _register_routes(self) -> None:
        router = self.router

        @router.get("", summary="租户智能体绑定列表")
        @action_read("action.tenant_agent_assignment.list")
        async def list_assignments(
            request: Request,
            db: DbSession,
            admin: ActiveTenantAdmin,
        ):
            """
            获取所有绑定列表，含全局默认 + 租户覆盖对比
            """
            tenant_id = admin.tenant_id
            service = AgentAssignmentService(db)

            global_defaults = await service.get_all_global()
            tenant_overrides = await service.get_all_for_tenant(tenant_id)

            override_map = {o.feature_code: o for o in tenant_overrides}

            result = []
            for gd in global_defaults:
                override = override_map.get(gd.feature_code)
                if override:
                    result.append(_build_assignment_item(override, global_default=gd))
                else:
                    result.append(_build_assignment_item(gd))

            return success(data=result)

        @router.get("/resolve/{feature_code}", summary="解析功能绑定的智能体")
        @auth_only
        async def resolve_assignment(
            request: Request,
            db: DbSession,
            admin: ActiveTenantAdmin,
            feature_code: str,
        ):
            """
            按 feature_code 获取绑定的 agent_id

            Resolve 顺序：租户覆盖 → 全局默认
            """
            tenant_id = admin.tenant_id
            service = AgentAssignmentService(db)
            assignment = await service.resolve_for_tenant(feature_code, tenant_id)
            return success(data=_build_resolve_result(assignment, feature_code))

        @router.put("/{feature_code}", summary="设置租户覆盖")
        @action_update("action.tenant_agent_assignment.update")
        async def set_override(
            request: Request,
            db: DbSession,
            admin: ActiveTenantAdmin,
            feature_code: str,
            body: TenantOverrideRequest,
        ):
            """创建或更新租户覆盖绑定"""
            tenant_id = admin.tenant_id
            service = AgentAssignmentService(db)
            assignment = await service.set_tenant_override(
                feature_code, tenant_id, body.agent_id, body.config,
            )
            return success(data=_build_resolve_result(assignment, feature_code))

        @router.delete("/{feature_code}", summary="删除租户覆盖")
        @action_delete("action.tenant_agent_assignment.delete")
        async def delete_override(
            request: Request,
            db: DbSession,
            admin: ActiveTenantAdmin,
            feature_code: str,
        ):
            """删除租户覆盖（恢复全局默认）"""
            tenant_id = admin.tenant_id
            service = AgentAssignmentService(db)
            removed = await service.delete_tenant_override(feature_code, tenant_id)
            if not removed:
                raise NotFoundException(
                    message=_("system_agent_assignment.error.override_not_found"),
                )
            return deleted()


router = TenantAgentAssignmentController.get_router()

__all__ = ["router", "TenantAgentAssignmentController"]
