"""
平台端对话监控 API

提供全租户对话列表和只读详情，用于审计和监控
"""

from fastapi import Query, Request

from app.core.base_controller import GlobalController
from app.core.deps import DbSession, ActiveAdmin, QueryParams
from app.core.i18n import _
from app.core.response import success, paginated
from app.enums.rbac import PermissionScope
from app.exceptions import NotFoundException
from app.rbac.decorators import (
    permission_resource,
    MenuConfig,
    action_read,
)
from app.repositories.ai.agent_conversation_repository import (
    AgentConversationRepository,
    AdminAgentConversationRepository,
)
from app.services.ai.conversation_service import ConversationService


def _build_admin_conversation_item(conv) -> dict:
    """从 ORM 对象构建管理端列表项字典"""
    agent_name = None
    try:
        agent_obj = getattr(conv, "agent", None)
        if agent_obj is not None:
            agent_name = agent_obj.name
    except AttributeError:
        pass

    return {
        "id": conv.id,
        "tenant_id": conv.tenant_id,
        "agent_id": conv.agent_id,
        "user_id": conv.user_id,
        "title": conv.title,
        "status": conv.status,
        "token_count": conv.token_count,
        "cost": float(conv.cost) if conv.cost else 0,
        "agent_name": agent_name,
        "created_at": conv.created_at,
        "updated_at": conv.updated_at,
    }


@permission_resource(
    resource="ai_conversation",
    name="menu.admin.ai_conversation",
    scope=PermissionScope.ADMIN,
    menu=MenuConfig(
        icon="lucide:message-square-text",
        path="/ai/conversations",
        component="ai/conversations/index",
        parent="ai_ops",
        sort_order=20,
    ),
)
class AdminAIConversationController(GlobalController):
    """
    平台端对话监控控制器

    全租户只读审计
    """

    prefix = "/ai/conversations"
    tags = [_("menu.tags.admin_ai_conversation")]

    def _register_routes(self) -> None:
        """注册路由"""
        router = self.router

        @router.get("", summary="全租户对话列表")
        @action_read("action.ai_conversation.list")
        async def list_conversations(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
            query: QueryParams,
            tenant_id: int | None = Query(None, description="按租户筛选"),
        ):
            """
            获取全租户对话列表

            支持 tenant_id 筛选和 JSON:API 分页排序
            权限: ai_conversation:list
            """
            if tenant_id:
                service = ConversationService(db, tenant_id)
                items, total = await service.query_list(spec=query)
            else:
                # 全租户查询：使用 BaseRepository（无 tenant 过滤）
                repo = AdminAgentConversationRepository(db)
                items, total = await repo.query_list(query)

            result = [_build_admin_conversation_item(item) for item in items]

            return paginated(
                items=result,
                total=total,
                page=query.page,
                page_size=query.size,
            )

        @router.get("/{conversation_id}", summary="对话详情（只读）")
        @action_read("action.ai_conversation.detail")
        async def get_conversation(
            request: Request,
            db: DbSession,
            conversation_id: int,
            admin: ActiveAdmin,
            message_skip: int = Query(0, ge=0),
            message_limit: int = Query(50, ge=1, le=200),
        ):
            """
            获取对话详情（只读审计）

            先从全局 Repo 查找对话取 tenant_id，再通过 Service 获取完整详情
            权限: ai_conversation:detail
            """
            repo = AdminAgentConversationRepository(db)
            conversation = await repo.get_by_id(conversation_id)

            if not conversation:
                raise NotFoundException(message=_("conversation.not_found"))

            service = ConversationService(db, conversation.tenant_id)
            detail = await service.get_conversation_detail(
                conversation_id=conversation_id,
                message_skip=message_skip,
                message_limit=message_limit,
            )

            return success(data=detail)


# 导出路由器
router = AdminAIConversationController.get_router()

__all__ = ["router", "AdminAIConversationController"]
