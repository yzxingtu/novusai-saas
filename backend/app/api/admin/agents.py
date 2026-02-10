"""
平台端智能体管理 API

提供跨租户智能体列表、详情、状态管理接口（平台管理员专用）
"""

from fastapi import Query, Request

from app.core.base_controller import GlobalController
from app.core.deps import DbSession, ActiveAdmin, QueryParams
from app.core.i18n import _
from app.core.logging import LogManager
from app.core.response import success, paginated
from app.enums.rbac import PermissionScope
from app.exceptions import NotFoundException
from app.rbac.decorators import (
    permission_resource,
    MenuConfig,
    action_read,
    action_update,
)
from app.services.ai.agent_service import AgentService, AdminAgentService

logger = LogManager.get_logger("ai")


def _build_admin_agent_item(agent) -> dict:
    """从 ORM 对象构建管理端列表项字典"""
    model_name = None
    try:
        model_obj = getattr(agent, "model", None)
        if model_obj is not None:
            model_name = model_obj.name
    except (AttributeError, Exception):
        pass

    return {
        "id": agent.id,
        "tenant_id": agent.tenant_id,
        "name": agent.name,
        "description": agent.description,
        "avatar": agent.avatar,
        "status": agent.status,
        "execution_mode": agent.execution_mode,
        "model_id": agent.model_id,
        "model_name": model_name,
        "published_version": agent.published_version,
        "created_at": agent.created_at,
        "updated_at": agent.updated_at,
    }


@permission_resource(
    resource="ai_agent",
    name="menu.admin.ai_agent",
    scope=PermissionScope.ADMIN,
    menu=MenuConfig(
        icon="lucide:bot",
        path="/ai/agents",
        component="ai/agents/index",
        parent="ai_mgmt",
        sort_order=60,
    ),
)
class AdminAgentController(GlobalController):
    """
    平台端智能体管理控制器

    跨租户只读查看 + 状态管理
    """

    prefix = "/ai/agents"
    tags = ["智能体管理（平台）"]

    def _register_routes(self) -> None:
        """注册路由"""
        router = self.router

        @router.get("", summary="全租户智能体列表")
        @action_read("action.ai_agent.list")
        async def list_agents(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
            query: QueryParams,
        ):
            """
            获取全租户智能体列表

            支持 JSON:API 风格筛选、排序、分页
            - filter[tenant_id][eq]=1  按租户筛选
            - filter[status][eq]=published  按状态筛选
            - filter[name][ilike]=xxx  按名称模糊搜索
            权限: ai_agent:list
            """
            service = AdminAgentService(db)
            items, total = await service.query_list(query)

            result = [_build_admin_agent_item(item) for item in items]

            return paginated(
                items=result,
                total=total,
                page=query.page,
                page_size=query.size,
            )

        @router.get("/{agent_id}", summary="智能体详情")
        @action_read("action.ai_agent.detail")
        async def get_agent(
            request: Request,
            db: DbSession,
            agent_id: int,
            admin: ActiveAdmin,
        ):
            """
            获取智能体详情（跨租户只读）

            权限: ai_agent:detail
            """
            admin_service = AdminAgentService(db)
            agent = await admin_service.get_by_id(agent_id)

            if not agent:
                raise NotFoundException(message=_("agent.error.not_found"))

            # 使用租户 Service 获取完整详情（含模型关联）
            service = AgentService(db, agent.tenant_id)
            detail = await service.get_agent_detail(agent_id)

            return success(data=detail)

        @router.put("/{agent_id}/status", summary="更新智能体状态")
        @action_update("action.ai_agent.update_status")
        async def update_agent_status(
            request: Request,
            db: DbSession,
            agent_id: int,
            admin: ActiveAdmin,
            status: str = Query(..., description="目标状态: disabled / draft / published"),
        ):
            """
            管理员更新智能体状态（启用/禁用）

            权限: ai_agent:update_status
            """
            service = AdminAgentService(db)
            updated = await service.update_status(agent_id, status)
            await db.commit()

            return success(
                data=_build_admin_agent_item(updated),
                message=_("common.success"),
            )


# 导出路由器
router = AdminAgentController.get_router()

__all__ = ["router", "AdminAgentController"]
