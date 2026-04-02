"""
平台端系统智能体绑定管理 API / Platform System Agent Assignment Management API

管理功能代码与智能体的映射关系
Manages the mapping between feature codes and agents.
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
from app.core.base_controller import GlobalController
from app.core.deps import ActiveAdmin, DbSession, SuperAdmin
from app.core.i18n import _
from app.core.logging import LogManager
from app.core.response import success
from app.enums.rbac import PermissionScope
from app.exceptions import NotFoundException
from app.rbac.decorators import (
    MenuConfig,
    action_read,
    action_update,
    auth_only,
    permission_resource,
)
from app.services.system.agent_assignment_service import AgentAssignmentService

logger = LogManager.get_logger("app")


class AgentAssignmentUpdate(PydanticBaseModel):
    """更新绑定请求 / Update assignment request"""
    agent_id: int | None = Field(None, description=_("system_agent_assignment.field.agent_id"))
    config: dict | None = Field(None, description=_("system_agent_assignment.field.config"))
    is_active: bool | None = Field(None, description=_("system_agent_assignment.field.is_active"))


@permission_resource(
    resource="agent_assignment",
    name="menu.admin.agent_assignment",
    scope=PermissionScope.ADMIN,
    parent_resource="ai_agent_mgmt",
    menu=MenuConfig(
        icon="lucide:plug",
        path="/ai/agent-assignments",
        component="ai/agent-assignments/index",
        parent="ai_app",
        sort_order=15,
    ),
)
class AdminAgentAssignmentController(GlobalController):
    """
    平台端系统智能体绑定管理控制器 / Platform System Agent Assignment Management Controller
    """

    prefix = "/ai/agent-assignments"
    tags = [_("menu.tags.admin_agent_assignment_mgmt")]

    def _register_routes(self) -> None:
        router = self.router

        @router.get("", summary="系统智能体绑定列表")
        @action_read("action.agent_assignment.list")
        async def list_assignments(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
        ):
            """获取所有全局默认系统智能体绑定 / Get all global default system agent assignments"""
            service = AgentAssignmentService(db)
            all_items = await service.get_all_global()

            # 构建插件 feature 多语言映射 / Build plugin feature i18n mapping
            i18n_map = await _build_plugin_feature_i18n_map(db)

            result = [_build_assignment_item(item, i18n_map=i18n_map) for item in all_items]
            return success(data={"items": result, "total": len(result)})

        @router.get("/resolve/{feature_code}", summary="解析功能绑定的智能体")
        @auth_only
        async def resolve_assignment(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
            feature_code: str,
        ):
            """
            公共 resolve API：按 feature_code 获取绑定的 agent_id / Public resolve: get bound agent_id by feature_code.

            仅需登录，无需特殊权限。返回 agent_id + agent_name + config。
            Login required only, no special permissions needed. Returns agent_id + agent_name + config.
            """
            service = AgentAssignmentService(db)
            assignment = await service.resolve(feature_code)
            if not assignment:
                return success(data={
                    "feature_code": feature_code,
                    "agent_id": None,
                    "agent_name": None,
                    "config": None,
                    "is_active": False,
                })
            agent_name = None
            try:
                agent_obj = getattr(assignment, "agent", None)
                if agent_obj is not None and not getattr(agent_obj, "is_deleted", False):
                    agent_name = agent_obj.name
            except AttributeError:
                pass
            return success(data={
                "feature_code": assignment.feature_code,
                "agent_id": assignment.agent_id,
                "agent_name": agent_name,
                "config": assignment.config,
                "is_active": assignment.is_active,
            })

        @router.get("/{feature_code}", summary="按功能代码获取绑定")
        @action_read("action.agent_assignment.detail")
        async def get_assignment(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
            feature_code: str,
        ):
            """按 feature_code 获取绑定详情 / Get assignment details by feature_code"""
            service = AgentAssignmentService(db)
            assignment = await service.get_assignment_by_feature_code(feature_code)
            if not assignment:
                raise NotFoundException(
                    message=_("system_agent_assignment.error.not_found"),
                )
            i18n_map = await _build_plugin_feature_i18n_map(db)
            return success(data=_build_assignment_item(assignment, i18n_map=i18n_map))

        @router.put("/{feature_code}", summary="更新绑定")
        @action_update("action.agent_assignment.update")
        async def update_assignment(
            request: Request,
            db: DbSession,
            admin: SuperAdmin,
            feature_code: str,
            body: AgentAssignmentUpdate,
        ):
            """更新绑定（agent_id, config, is_active） / Update assignment (agent_id, config, is_active)"""
            service = AgentAssignmentService(db)
            assignment = await service.get_assignment_by_feature_code(feature_code)
            if not assignment:
                raise NotFoundException(
                    message=_("system_agent_assignment.error.not_found"),
                )

            update_data = body.model_dump(exclude_unset=True)
            i18n_map = await _build_plugin_feature_i18n_map(db)
            if update_data:
                # 功能分配仅允许平台级全局共享智能体（与全企业调用一致） / Feature binding: platform global-shared agents only
                if "agent_id" in update_data:
                    await service.validate_agent_id(
                        update_data["agent_id"],
                        for_platform_feature_binding=True,
                    )
                # 启用时校验已绑定的 agent 仍可用且仍符合全局共享规则 / Re-validate on enable
                elif update_data.get("is_active") is True and assignment.agent_id:
                    await service.validate_agent_id(
                        assignment.agent_id,
                        for_platform_feature_binding=True,
                    )
                updated = await service.update(assignment.id, update_data)
                return success(data=_build_assignment_item(updated, i18n_map=i18n_map))

            return success(data=_build_assignment_item(assignment, i18n_map=i18n_map))


router = AdminAgentAssignmentController.get_router()

__all__ = ["router", "AdminAgentAssignmentController"]
