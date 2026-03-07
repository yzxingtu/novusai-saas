"""
Platform admin AI agent chat API

Allows platform administrators to chat with any tenant's published agents
for testing and support purposes.
"""

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

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
from app.exceptions import NotFoundException
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
)
from app.services.ai.agent_chat_service import AgentChatService
from app.services.ai.agent_service import AdminAgentService
from app.services.ai.conversation_service import ConversationService


async def _get_agent_tenant_id(db: AsyncSession, agent_id: int) -> int:
    """Load agent via AdminAgentService and return its tenant_id.

    For global/admin agents where tenant_id is NULL, returns 0
    as a sentinel value for admin-context conversations.

    Raises NotFoundException if agent does not exist.
    """
    service = AdminAgentService(db)
    agent = await service.get_by_id(agent_id)
    if not agent:
        raise NotFoundException(message=_("agent.error.not_found"))
    return agent.tenant_id or 0


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
    Platform admin agent chat controller

    Allows admins to test / interact with any tenant's published agents.
    The agent's own tenant_id is resolved automatically.
    """

    prefix = "/ai/agent-chat"
    tags = [_("menu.tags.admin_agent_chat")]

    def _register_routes(self) -> None:
        """Register routes"""
        router = self.router

        # ========================================
        # 对话执行
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
            Send a chat message and wait for full response.

            - New conversation: omit conversation_id
            - Continue conversation: pass conversation_id

            Permission: admin_agent_chat:chat
            """
            tenant_id = await _get_agent_tenant_id(db, agent_id)
            perm_service = PermissionService(db)
            user_perms = await perm_service.get_admin_permissions(admin)
            service = AgentChatService(db, tenant_id)
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
                memory_source=MemoryChannelEnum.ADMIN_CHAT.value,
                page_session_id=data.page_session_id,
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
            Send a chat message and stream the response via SSE.

            Event types:
            - message: content delta
            - tool_call: tool call progress
            - done: completion (contains conversation_id, total_tokens)
            - [DONE]: SSE end marker

            Permission: admin_agent_chat:stream
            """
            tenant_id = await _get_agent_tenant_id(db, agent_id)
            perm_service = PermissionService(db)
            user_perms = await perm_service.get_admin_permissions(admin)
            service = AgentChatService(db, tenant_id)
            return await service.stream_chat(
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
                image_params=data.image_params.model_dump() if data.image_params else None,
                memory_scene=MemorySceneEnum.ADMIN_CHAT.value,
                memory_channel=MemoryChannelEnum.ADMIN_CHAT.value,
                memory_source=MemoryChannelEnum.ADMIN_CHAT.value,
                page_session_id=data.page_session_id,
            )

        # ========================================
        # 智能路由
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
            Intelligently select target agent based on message and page context.

            Priority:
            1. pinned_agent_id pass-through
            2. Router agent AI selection
            3. default_chat fallback

            Permission: admin_agent_chat:route
            """
            return await handle_route(
                db,
                tenant_id=None,
                message=data.message,
                is_admin_context=True,
                page_context=data.page_context.model_dump() if data.page_context else None,
                pinned_agent_id=data.pinned_agent_id,
            )

        # ========================================
        # 操作确认
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
            Handle AI action confirmation or cancellation.

            - action="confirm": validate confirm_id and execute
            - action="cancel": remove confirm_id, cancel operation

            Permission: admin_agent_chat:confirm
            """
            # 该接口与具体智能体无关，使用租户哨兵值 0
            service = AgentChatService(db, 0)
            return await handle_confirm_or_cancel(
                service, data, tenant_id=0, user_id=admin.id,
            )

        # ========================================
        # 对话管理
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
            List conversations across all agents for the admin context.

            Used by the AI panel's global history sidebar.
            Enriches each conversation with agent_name and agent_avatar.

            Permission: admin_agent_chat:conversations
            """
            service = ConversationService(db, 0)
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
            Get conversation detail including message list.

            Permission: admin_agent_chat:conversation_detail
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
            Delete a conversation (soft delete).

            Permission: admin_agent_chat:delete_conversation
            """
            service, _ = await ConversationService.get_service_for_conversation(
                db,
                conversation_id,
            )
            await service.delete_accessible_conversation(conversation_id)
            await db.commit()
            return deleted(message=_("agent_chat.conversation_deleted"))

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
            Get memory state for a specific conversation.
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
        @action_delete("action.admin_agent_chat.delete_conversation")
        async def clear_conversation_memory(
            request: Request,
            db: DbSession,
            conversation_id: int,
            admin: ActiveAdmin,
        ):
            """
            Clear memory state for a specific conversation.
            """
            service, _ = await ConversationService.get_service_for_conversation(
                db,
                conversation_id,
            )
            deleted_count = await service.clear_conversation_memory_state(conversation_id)
            return success(data={"deleted_count": deleted_count})


# 导出路由
router = AdminAgentChatController.get_router()

__all__ = ["router", "AdminAgentChatController"]
