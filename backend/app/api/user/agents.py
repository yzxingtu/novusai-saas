"""
用户端智能体列表 API

提供面向终端用户（TenantUser）的可用智能体查询接口。
仅返回已发布、当前用户有权访问的智能体。
"""

from fastapi import Request

from app.api.shared._agent_helpers import build_agent_base_item
from app.core.base_controller import BaseController
from app.core.deps import ActiveTenantUser, DbSession, QueryParams
from app.core.response import paginated
from app.enums.rbac import PermissionScope
from app.rbac.decorators import (
    auth_only,
    permission_resource,
)
from app.services.ai.agent_service import AgentService


def _build_user_agent_item(agent) -> dict:
    """构建用户端智能体列表项"""
    item = build_agent_base_item(agent)
    item["visibility"] = agent.visibility
    return item


@permission_resource(
    resource="user_agents",
    name="menu.user.ai_chat",
    scope=PermissionScope.TENANT_USER,
    parent_resource="menu",
)
class UserAgentController(BaseController):
    """
    用户端智能体列表控制器

    仅提供查询接口，不提供管理操作。
    """

    prefix = "/ai/agents"
    tags = ["AI Agents (User)"]

    def _register_routes(self) -> None:
        """注册路由"""
        router = self.router

        @router.get("", summary="获取可用智能体列表")
        @auth_only
        async def list_agents(
            request: Request,
            db: DbSession,
            current_user: ActiveTenantUser,
            query: QueryParams,
        ):
            """
            获取当前用户可访问的已发布智能体列表

            自动过滤：
            - 仅已发布状态
            - 排除路由智能体
            - 按 visibility + access_type 权限过滤
            """
            service = AgentService(db, current_user.tenant_id)
            items, total = await service.list_user_accessible_agents(
                user_id=current_user.id,
                spec=query,
            )
            result = [_build_user_agent_item(item) for item in items]

            return paginated(
                items=result,
                total=total,
                page=query.page,
                page_size=query.size,
            )


# 导出路由器
router = UserAgentController.get_router()

__all__ = ["router", "UserAgentController"]
