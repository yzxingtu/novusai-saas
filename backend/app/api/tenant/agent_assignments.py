"""
企业端系统智能体绑定 API / Tenant Agent Assignment API

提供功能代码到智能体的映射解析 + 企业级覆盖管理
Provides feature code to agent mapping resolution + tenant-level override management
"""

from fastapi import Request
from pydantic import BaseModel as PydanticBaseModel
from pydantic import Field

from app.api.shared._agent_assignment_helpers import (
    build_assignment_item as _build_assignment_item,
)
from app.api.shared._agent_assignment_helpers import (
    build_plugin_feature_i18n_map as _build_plugin_feature_i18n_map,
)
from app.core.base_controller import TenantController
from app.core.deps import ActiveTenantAdmin, DbSession
from app.core.i18n import _
from app.core.logging import LogManager
from app.core.response import deleted, success
from app.enums.rbac import PermissionScope
from app.exceptions import NotFoundException
from app.rbac.decorators import (
    MenuConfig,
    action_delete,
    action_read,
    action_update,
    auth_only,
    permission_resource,
)
from app.services.system.agent_assignment_service import AgentAssignmentService

logger = LogManager.get_logger("app")


class TenantOverrideRequest(PydanticBaseModel):
    """企业覆盖绑定请求 / Tenant override binding request"""
    agent_id: int | None = Field(None, description=_("system_agent_assignment.field.agent_id"))
    config: dict | None = Field(None, description=_("system_agent_assignment.field.config"))


def _build_resolve_result(assignment, feature_code: str) -> dict:
    """构建 resolve 响应 / Build resolve response"""
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
        if agent_obj is not None and not getattr(agent_obj, "is_deleted", False):
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


@permission_resource(
    resource="tenant_agent_assignment",
    name="menu.tenant.agent_assignment",
    scope=PermissionScope.ALL_TENANTS,
    parent_resource="ai_workspace",
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
    企业端系统智能体绑定控制器 / Tenant Agent Assignment Controller
    """

    prefix = "/ai/agent-assignments"
    tags = [_("menu.tags.tenant_agent_assignment")]

    def _register_routes(self) -> None:
        router = self.router

        @router.get("", summary="企业智能体绑定列表")
        @action_read("action.tenant_agent_assignment.list")
        async def list_assignments(
            request: Request,
            db: DbSession,
            admin: ActiveTenantAdmin,
        ):
            """
            获取所有绑定列表，含全局默认 + 企业覆盖对比 / Get all assignment list with global defaults + tenant override comparison
            """
            tenant_id = admin.tenant_id
            service = AgentAssignmentService(db)

            global_defaults = await service.get_all_global()
            tenant_overrides = await service.get_all_for_tenant(tenant_id)

            override_map = {o.feature_code: o for o in tenant_overrides}

            i18n_map = await _build_plugin_feature_i18n_map(db)

            result = []
            for gd in global_defaults:
                override = override_map.get(gd.feature_code)
                if override:
                    result.append(_build_assignment_item(override, global_default=gd, i18n_map=i18n_map))
                else:
                    result.append(_build_assignment_item(gd, i18n_map=i18n_map))

            return success(data={"items": result, "total": len(result)})

        @router.get("/resolve/{feature_code}", summary="解析功能绑定的智能体")
        @auth_only
        async def resolve_assignment(
            request: Request,
            db: DbSession,
            admin: ActiveTenantAdmin,
            feature_code: str,
        ):
            """
            按 feature_code 获取绑定的 agent_id / Get bound agent_id by feature_code

            Resolve 顺序 / Resolve order：企业覆盖 → 全局默认 / Tenant override → Global default
            """
            tenant_id = admin.tenant_id
            service = AgentAssignmentService(db)
            assignment = await service.resolve_for_tenant(feature_code, tenant_id)
            return success(data=_build_resolve_result(assignment, feature_code))

        @router.put("/{feature_code}", summary="设置企业覆盖")
        @action_update("action.tenant_agent_assignment.update")
        async def set_override(
            request: Request,
            db: DbSession,
            admin: ActiveTenantAdmin,
            feature_code: str,
            body: TenantOverrideRequest,
        ):
            """创建或更新企业覆盖绑定 / Create or update tenant override binding"""
            tenant_id = admin.tenant_id
            service = AgentAssignmentService(db)
            assignment = await service.set_tenant_override(
                feature_code, tenant_id, body.agent_id, body.config,
            )
            i18n_map = await _build_plugin_feature_i18n_map(db)
            return success(data=_build_assignment_item(assignment, i18n_map=i18n_map))

        @router.delete("/{feature_code}", summary="删除企业覆盖")
        @action_delete("action.tenant_agent_assignment.delete")
        async def delete_override(
            request: Request,
            db: DbSession,
            admin: ActiveTenantAdmin,
            feature_code: str,
        ):
            """删除企业覆盖（恢复全局默认） / Delete tenant override (restore global default)"""
            tenant_id = admin.tenant_id
            service = AgentAssignmentService(db)
            removed = await service.delete_tenant_override(feature_code, tenant_id)
            if not removed:
                raise NotFoundException(
                    message=_("system_agent_assignment.error.override_not_found"),
                )
            return deleted()


# 导出路由器 / Export router
router = TenantAgentAssignmentController.get_router()

__all__ = ["router", "TenantAgentAssignmentController"]
