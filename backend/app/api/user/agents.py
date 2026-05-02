"""
用户端智能体列表 API / User Agent List API

提供面向终端用户（TenantUser）的可用智能体查询接口。
Provides available agent query endpoints for end users (TenantUser).
仅返回已发布、当前用户有权访问的智能体。
Only returns published agents accessible to the current user.
"""

from fastapi import Request

from app.api.shared._agent_helpers import build_agent_base_item
from app.core.base_controller import BaseController
from app.core.deps import ActiveTenantUser, DbSession, QueryParams
from app.core.response import paginated, success
from app.enums.rbac import PermissionScope
from app.rbac.decorators import (
    auth_only,
    permission_resource,
)
from app.services.ai.account_ai_access_service import AccountAIAccessService
from app.services.ai.agent_kb_binding_service import AgentKBBindingService
from app.services.ai.agent_service import AgentService


def _build_user_agent_item(agent) -> dict:
    """构建用户端智能体列表项 / Build user agent list item"""
    item = build_agent_base_item(agent)
    item["visibility"] = agent.visibility
    return item


@permission_resource(
    resource="user_agents",
    name="menu.user.ai_chat",
    scope=PermissionScope.USER,
    parent_resource="menu",
)
class UserAgentController(BaseController):
    """
    用户端智能体列表控制器 / User Agent List Controller

    仅提供查询接口，不提供管理操作。
    Only provides query endpoints, no management operations.
    """

    prefix = "/ai/agents"
    tags = ["AI Agents (User)"]

    def _register_routes(self) -> None:
        """注册路由 / Register routes"""
        router = self.router

        async def _ensure_ai_chat_enabled(
            db: DbSession,
            current_user: ActiveTenantUser,
        ) -> None:
            await AccountAIAccessService(db).require_tenant_user_ai_access(
                current_user
            )

        @router.get(
            "/{agent_id}/knowledge-bases",
            summary="获取智能体知识库绑定 / Get agent knowledge base bindings",
        )
        @auth_only
        async def get_agent_kbs(
            request: Request,
            db: DbSession,
            agent_id: int,
            current_user: ActiveTenantUser,
        ):
            """
            获取智能体绑定的启用知识库列表（用于聊天界面展示 RAG 指示器）/ Get agent bound KB list (for RAG indicator).
            """
            await _ensure_ai_chat_enabled(db, current_user)
            kb_service = AgentKBBindingService(db, current_user.tenant_id)
            result = await kb_service.get_agent_kb_bindings(
                agent_id, merge_platform_bindings=True
            )
            return success(data=result)

        @router.get("", summary="获取可用智能体列表 / Get available agent list")
        @auth_only
        async def list_agents(
            request: Request,
            db: DbSession,
            current_user: ActiveTenantUser,
            query: QueryParams,
        ):
            """
            获取当前用户可访问的已发布智能体列表 / Get published agent list for current user.

            自动过滤 / Auto filters:
            - 仅已发布状态 / Published status only
            - 排除路由智能体 / Exclude router agents
            - 按 visibility + access_type 权限过滤 / Filter by visibility + access_type permissions
            """
            await _ensure_ai_chat_enabled(db, current_user)
            service = AgentService(db, current_user.tenant_id)
            items, total = await service.list_user_accessible_agents(
                user_id=current_user.id,
                user_role_id=current_user.role_id,
                spec=query,
            )
            result = [_build_user_agent_item(item) for item in items]

            return paginated(
                items=result,
                total=total,
                page=query.page,
                page_size=query.size,
            )


# 导出路由器 / Export router
router = UserAgentController.get_router()

__all__ = ["router", "UserAgentController"]
