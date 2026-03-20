"""
平台管理员 AI 智能体对话 API / Platform Admin AI Agent Chat API

允许平台管理员与任何企业的已发布智能体进行对话，用于测试和支持。
Allows platform administrators to chat with any tenant's published agents
for testing and support purposes.
"""

from fastapi import Request

from app.configs.service import PLATFORM_TENANT_ID
from app.core.base_controller import GlobalController
from app.core.deps import ActiveAdmin, DbSession, QueryParams
from app.core.i18n import _
from app.core.response import deleted, paginated, success
from app.enums.agent import (
    MemoryChannelEnum,
    MemorySceneEnum,
)
from app.enums.common import UserRoleEnum
from app.enums.rbac import PermissionScope
from app.rbac.decorators import (
    MenuConfig,
    action_create,
    action_delete,
    action_read,
    permission_resource,
)
from app.rbac.services.permission_service import PermissionService
from app.api.shared._agent_chat_helpers import (
    enrich_conversations_with_agent,
    handle_confirm_or_cancel,
    handle_route,
)
from app.schemas.ai.agent_chat import (
    AgentChatRequest,
    AgentConfirmRequest,
    AgentRouteRequest,
    UpdateConversationTitleRequest,
)
from app.services.ai.agent_chat_service import AgentChatService
from app.services.ai.conversation_service import ConversationService


@permission_resource(
    resource="admin_agent_chat",
    name="menu.admin.admin_agent_chat",
    scope=PermissionScope.ADMIN_ONLY,
    parent_resource="ai_agent_mgmt",
    menu=MenuConfig(
        icon="lucide:message-square-text",
        path="/ai/chat",
        parent="ai_app",
        sort_order=40,
        hidden=True,
    ),
)
class AdminAgentChatController(GlobalController):
    """
    平台管理员智能体对话控制器 / Platform Admin Agent Chat Controller

    允许管理员测试/交互任何企业的已发布智能体，但管理端执行上下文固定使用平台租户哨兵值。
    Allows admins to test / interact with any published agent while always using
    the platform tenant sentinel as the admin execution context.
    """

    prefix = "/ai/agent-chat"
    tags = [_("menu.tags.admin_agent_chat")]

    def _register_routes(self) -> None:
        """注册路由 / Register routes"""
        router = self.router

        # ========================================
        # 对话执行 / Chat Execution
        # ========================================

        @router.post("/{agent_id}/chat", summary="Send chat message (non-streaming)")
        @action_create("action.admin_agent_chat.chat")
        async def chat(
            request: Request,
            db: DbSession,
            agent_id: int,
            data: AgentChatRequest,
            admin: ActiveAdmin,
        ):
            """
            发送对话消息并等待完整响应 / Send a chat message and wait for full response.

            - 新对话：省略 conversation_id / New conversation: omit conversation_id
            - 继续对话：传入 conversation_id / Continue conversation: pass conversation_id

            权限 / Permission: admin_agent_chat:chat
            """
            perm_service = PermissionService(db)
            user_perms = await perm_service.get_admin_permissions(admin)
            service = AgentChatService(db, PLATFORM_TENANT_ID)
            result = await service.chat(
                agent_id=agent_id,
                message=data.message,
                conversation_id=data.conversation_id,
                variables=data.variables,
                page_context=data.page_context,
                user_id=admin.id,
                knowledge_base_ids=data.knowledge_base_ids,
                user_role=UserRoleEnum.PLATFORM_ADMIN.value,
                permissions=user_perms,
                consented_actions=data.consented_actions,
                attachments=[a.model_dump() for a in data.attachments] if data.attachments else None,
                memory_scene=MemorySceneEnum.ADMIN_CHAT.value,
                memory_channel=MemoryChannelEnum.ADMIN_CHAT.value,
                memory_source=MemorySceneEnum.ADMIN_CHAT.value,
                page_session_id=data.page_session_id,
                route_source=data.route_source,
            )
            return success(data=result.model_dump())

        @router.post("/{agent_id}/chat/stream", summary="Send chat message (SSE streaming)")
        @action_create("action.admin_agent_chat.stream")
        async def stream_chat(
            request: Request,
            db: DbSession,
            agent_id: int,
            data: AgentChatRequest,
            admin: ActiveAdmin,
        ):
            """
            发送对话消息并通过 SSE 流式返回响应 / Send a chat message and stream the response via SSE.

            事件类型 / Event types:
            - message: 内容增量 / content delta
            - tool_call: 工具调用进度 / tool call progress
            - done: 完成（含 conversation_id, total_tokens） / completion
            - [DONE]: SSE 结束标记 / SSE end marker

            权限 / Permission: admin_agent_chat:stream
            """
            perm_service = PermissionService(db)
            user_perms = await perm_service.get_admin_permissions(admin)
            service = AgentChatService(db, PLATFORM_TENANT_ID)
            return await service.stream_chat(
                agent_id=agent_id,
                message=data.message or "",
                messages=data.messages,
                conversation_id=data.conversation_id,
                variables=data.variables,
                page_context=data.page_context,
                user_id=admin.id,
                knowledge_base_ids=data.knowledge_base_ids,
                user_role=UserRoleEnum.PLATFORM_ADMIN.value,
                permissions=user_perms,
                consented_actions=data.consented_actions,
                attachments=[a.model_dump() for a in data.attachments] if data.attachments else None,
                image_params=data.image_params.model_dump() if data.image_params else None,
                memory_scene=MemorySceneEnum.ADMIN_CHAT.value,
                memory_channel=MemoryChannelEnum.ADMIN_CHAT.value,
                memory_source=MemorySceneEnum.ADMIN_CHAT.value,
                page_session_id=data.page_session_id,
                route_source=data.route_source,
            )

        # ========================================
        # 智能路由 / Intelligent Routing
        # ========================================

        @router.post("/route", summary="Intelligent agent routing", response_model=None)
        @action_create("action.admin_agent_chat.route")
        async def route_agent(
            request: Request,
            db: DbSession,
            data: AgentRouteRequest,
            admin: ActiveAdmin,
        ):
            """
            基于消息和页面上下文智能选择目标智能体 / Intelligently select target agent based on message and page context.

            优先级 / Priority:
            1. pinned_agent_id 直通 / pinned_agent_id pass-through
            2. Router 智能体 AI 选择 / Router agent AI selection
            3. default_chat 回退 / default_chat fallback

            权限 / Permission: admin_agent_chat:route
            """
            return await handle_route(
                db,
                tenant_id=PLATFORM_TENANT_ID,
                message=data.message,
                user_role=UserRoleEnum.PLATFORM_ADMIN.value,
                page_context=data.page_context.model_dump() if data.page_context else None,
                pinned_agent_id=data.pinned_agent_id,
                user_id=admin.id,
            )

        # ========================================
        # 操作确认 / Action Confirmation
        # ========================================

        @router.post("/confirm", summary="Confirm/cancel AI action")
        @action_create("action.admin_agent_chat.confirm")
        async def confirm_action(
            request: Request,
            db: DbSession,
            data: AgentConfirmRequest,
            admin: ActiveAdmin,
        ):
            """
            处理 AI 操作确认或取消 / Handle AI action confirmation or cancellation.

            - action="confirm": 验证 confirm_id 并执行 / validate confirm_id and execute
            - action="cancel": 移除 confirm_id，取消操作 / remove confirm_id, cancel operation

            权限 / Permission: admin_agent_chat:confirm
            """
            # 该接口与具体智能体无关，使用平台租户哨兵值 / Agent-agnostic endpoint uses platform tenant sentinel
            service = AgentChatService(db, PLATFORM_TENANT_ID)
            return await handle_confirm_or_cancel(
                service,
                data,
                tenant_id=PLATFORM_TENANT_ID,
                user_id=admin.id,
            )

        # ========================================
        # 对话管理 / Conversation Management
        # ========================================

        @router.get("/conversations", summary="List all conversations (global)")
        @action_read("action.admin_agent_chat.conversations")
        async def list_all_conversations(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
            query: QueryParams,
        ):
            """
            列出管理端上下文中所有智能体的对话 / List conversations across all agents for the admin context.

            用于 AI 面板的全局历史侧边栏，为每个对话添加 agent_name 和 agent_avatar。
            Used by the AI panel's global history sidebar.
            Enriches each conversation with agent_name and agent_avatar.

            权限 / Permission: admin_agent_chat:conversations
            """
            service = ConversationService(db, PLATFORM_TENANT_ID)
            items, total = await service.query_list(spec=query)
            return paginated(
                items=enrich_conversations_with_agent(items),
                total=total,
                page=query.page,
                page_size=query.size,
            )

        @router.get(
            "/conversations/{conversation_id}",
            summary="Get conversation detail",
        )
        @action_read("action.admin_agent_chat.conversation_detail")
        async def get_conversation_detail(
            request: Request,
            db: DbSession,
            conversation_id: int,
            admin: ActiveAdmin,
        ):
            """
            获取对话详情（含消息列表） / Get conversation detail including message list.

            权限 / Permission: admin_agent_chat:conversation_detail
            """
            service, _ = await ConversationService.get_service_for_conversation(
                db,
                conversation_id,
            )
            result = await service.get_conversation_detail(conversation_id)
            return success(data=result)

        @router.delete(
            "/conversations/{conversation_id}",
            summary="Delete conversation",
        )
        @action_delete("action.admin_agent_chat.delete_conversation")
        async def delete_conversation(
            request: Request,
            db: DbSession,
            conversation_id: int,
            admin: ActiveAdmin,
        ):
            """
            删除对话（软删除） / Delete a conversation (soft delete).

            权限 / Permission: admin_agent_chat:delete_conversation
            """
            service, _ = await ConversationService.get_service_for_conversation(
                db,
                conversation_id,
            )
            await service.delete_accessible_conversation(conversation_id)
            await db.commit()
            return deleted(message=_("agent_chat.conversation_deleted"))

        @router.patch(
            "/conversations/{conversation_id}",
            summary="Update conversation title",
        )
        @action_create("action.admin_agent_chat.update_conversation")
        async def update_conversation_title(
            request: Request,
            db: DbSession,
            conversation_id: int,
            data: UpdateConversationTitleRequest,
            admin: ActiveAdmin,
        ):
            """更新对话标题 / Update conversation title"""
            service, _ = await ConversationService.get_service_for_conversation(
                db,
                conversation_id,
            )
            conv = await service.update_conversation_title(
                conversation_id,
                title=data.title,
                user_id=None,
            )
            await db.commit()
            return success(data={"id": conv.id, "title": conv.title})

        @router.get(
            "/conversations/{conversation_id}/memory-state",
            summary="Get conversation memory state",
        )
        @action_read("action.admin_agent_chat.read_conversation")
        async def get_conversation_memory(
            request: Request,
            db: DbSession,
            conversation_id: int,
            admin: ActiveAdmin,
        ):
            """
            获取指定对话的记忆状态 / Get memory state for a specific conversation.
            """
            service, _ = await ConversationService.get_service_for_conversation(
                db,
                conversation_id,
            )
            state = await service.get_conversation_memory_state(conversation_id)
            return success(data=state)

        @router.delete(
            "/conversations/{conversation_id}/memory-state",
            summary="Clear conversation memory",
        )
        @action_delete("action.admin_agent_chat.clear_memory")
        async def clear_conversation_memory(
            request: Request,
            db: DbSession,
            conversation_id: int,
            admin: ActiveAdmin,
        ):
            """
            清除指定对话的记忆状态 / Clear memory state for a specific conversation.
            """
            service, _ = await ConversationService.get_service_for_conversation(
                db,
                conversation_id,
            )
            deleted_count = await service.clear_conversation_memory_state(conversation_id)
            return success(data={"deleted_count": deleted_count})


# 导出路由 / Export router
router = AdminAgentChatController.get_router()

__all__ = ["router", "AdminAgentChatController"]

