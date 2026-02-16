"""
平台端系统智能体绑定管理 API

管理功能代码与智能体的映射关系
"""

from fastapi import Request
from pydantic import BaseModel as PydanticBaseModel, Field

from app.core.base_controller import GlobalController
from app.core.deps import DbSession, ActiveAdmin, SuperAdmin
from app.core.i18n import _
from app.core.logging import LogManager
from app.core.response import success
from app.enums.rbac import PermissionScope
from app.exceptions import NotFoundException
from app.rbac.decorators import (
    permission_resource,
    MenuConfig,
    action_read,
    action_update,
    auth_only,
)
from app.services.system.agent_assignment_service import AgentAssignmentService

logger = LogManager.get_logger("app")


class AgentAssignmentUpdate(PydanticBaseModel):
    """更新绑定请求"""
    agent_id: int | None = Field(None, description=_("system_agent_assignment.field.agent_id"))
    config: dict | None = Field(None, description=_("system_agent_assignment.field.config"))
    is_active: bool | None = Field(None, description=_("system_agent_assignment.field.is_active"))


def _build_assignment_item(assignment) -> dict:
    """构建绑定列表项"""
    agent_name = None
    agent_avatar = None
    try:
        agent_obj = getattr(assignment, "agent", None)
        if agent_obj is not None:
            agent_name = agent_obj.name
            agent_avatar = agent_obj.avatar
    except (AttributeError, Exception):
        pass

    return {
        "id": assignment.id,
        "feature_code": assignment.feature_code,
        "feature_name": assignment.feature_name,
        "description": assignment.description,
        "agent_id": assignment.agent_id,
        "agent_name": agent_name,
        "agent_avatar": agent_avatar,
        "config": assignment.config,
        "is_active": assignment.is_active,
        "created_at": assignment.created_at,
        "updated_at": assignment.updated_at,
    }


@permission_resource(
    resource="agent_assignment",
    name="menu.admin.agent_assignment",
    scope=PermissionScope.ADMIN,
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
    平台端系统智能体绑定管理控制器
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
            """获取所有全局默认系统智能体绑定"""
            service = AgentAssignmentService(db)
            all_items = await service.get_all_global()
            result = [_build_assignment_item(item) for item in all_items]
            return success(data=result)

        @router.get("/resolve/{feature_code}", summary="解析功能绑定的智能体")
        @auth_only
        async def resolve_assignment(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
            feature_code: str,
        ):
            """
            公共 resolve API：按 feature_code 获取绑定的 agent_id

            仅需登录，无需特殊权限。返回 agent_id + agent_name + config。
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
                if agent_obj is not None:
                    agent_name = agent_obj.name
            except (AttributeError, Exception):
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
            """按 feature_code 获取绑定详情"""
            service = AgentAssignmentService(db)
            assignment = await service.repo.get_by_feature_code(feature_code)
            if not assignment:
                raise NotFoundException(
                    message=_("system_agent_assignment.error.not_found"),
                )
            return success(data=_build_assignment_item(assignment))

        @router.put("/{feature_code}", summary="更新绑定")
        @action_update("action.agent_assignment.update")
        async def update_assignment(
            request: Request,
            db: DbSession,
            admin: SuperAdmin,
            feature_code: str,
            body: AgentAssignmentUpdate,
        ):
            """更新绑定（agent_id, config, is_active）"""
            service = AgentAssignmentService(db)
            assignment = await service.repo.get_by_feature_code(feature_code)
            if not assignment:
                raise NotFoundException(
                    message=_("system_agent_assignment.error.not_found"),
                )

            update_data = body.model_dump(exclude_unset=True)
            if update_data:
                updated = await service.update(assignment.id, update_data)
                return success(data=_build_assignment_item(updated))

            return success(data=_build_assignment_item(assignment))


router = AdminAgentAssignmentController.get_router()

__all__ = ["router", "AdminAgentAssignmentController"]
