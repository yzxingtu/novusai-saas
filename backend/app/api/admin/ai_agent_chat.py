"""
Platform admin AI agent chat API

Allows platform administrators to chat with any tenant's published agents
for testing and support purposes.
"""

from fastapi import Request

from app.core.base_controller import GlobalController
from app.core.deps import DbSession, ActiveAdmin, QueryParams
from app.core.i18n import _
from app.core.response import success, deleted, paginated
from app.enums.rbac import PermissionScope
from app.exceptions import NotFoundException
from app.rbac.decorators import (
    permission_resource,
    MenuConfig,
    action_read,
    action_create,
    action_delete,
)
from app.rbac.services.permission_service import PermissionService
from app.enums.agent import ConfirmActionEnum
from app.schemas.ai.agent_chat import AgentChatRequest, AgentConfirmRequest
from app.services.ai.agent_chat_service import AgentChatService
from app.services.ai.agent_service import AdminAgentService
from app.services.ai.conversation_service import ConversationService


async def _get_agent_tenant_id(db: "AsyncSession", agent_id: int) -> int:
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
    scope=PermissionScope.ADMIN,
    menu=MenuConfig(
        icon="lucide:message-square-text",
        path="/ai/chat",
        component="ai/chat/index",
        parent="ai_app",
        sort_order=40,
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
        # Chat execution
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
                user_id=admin.id,
                knowledge_base_ids=data.knowledge_base_ids,
                user_role="platform_admin",
                permissions=user_perms,
                consented_actions=data.consented_actions,
                attachments=[a.model_dump() for a in data.attachments] if data.attachments else None,
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
                user_id=admin.id,
                knowledge_base_ids=data.knowledge_base_ids,
                user_role="platform_admin",
                permissions=user_perms,
                consented_actions=data.consented_actions,
                attachments=[a.model_dump() for a in data.attachments] if data.attachments else None,
            )

        # ========================================
        # Action confirmation
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
            # confirm endpoint is agent-agnostic; use sentinel tenant_id=0
            service = AgentChatService(db, 0)

            if data.action == ConfirmActionEnum.CANCEL.value:
                result = await service.cancel_action(data.confirm_id)
                msg_key = (
                    _("agent_confirm.cancelled")
                    if result["status"] == "cancelled"
                    else _("agent_confirm.cancel_failed")
                )
                return success(data=result, message=msg_key)

            # confirm
            result = await service.confirm_action(
                confirm_id=data.confirm_id,
                tenant_id=0,
                user_id=admin.id,
            )
            return success(data=result)

        # ========================================
        # Conversation management
        # ========================================

        @router.get("/{agent_id}/conversations", summary="List agent conversations")
        @action_read("action.admin_agent_chat.conversations")
        async def list_conversations(
            request: Request,
            db: DbSession,
            agent_id: int,
            admin: ActiveAdmin,
            query: QueryParams,
        ):
            """
            List conversations for the specified agent.

            Supports JSON:API pagination, filtering, sorting.

            Permission: admin_agent_chat:conversations
            """
            tenant_id = await _get_agent_tenant_id(db, agent_id)
            service = ConversationService(db, tenant_id)
            from app.schemas.common.query import FilterRule
            forced = [FilterRule(field="agent_id", operator="eq", value=agent_id)]
            items, total = await service.query_list(
                spec=query,
                forced_filters=forced,
            )
            return paginated(
                items=[item.to_dict() for item in items],
                total=total,
                page=query.page,
                page_size=query.size,
            )

        @router.get(
            "/{agent_id}/conversations/{conversation_id}",
            summary="Get conversation detail",
        )
        @action_read("action.admin_agent_chat.conversation_detail")
        async def get_conversation_detail(
            request: Request,
            db: DbSession,
            agent_id: int,
            conversation_id: int,
            admin: ActiveAdmin,
        ):
            """
            Get conversation detail including message list.

            Permission: admin_agent_chat:conversation_detail
            """
            tenant_id = await _get_agent_tenant_id(db, agent_id)
            service = ConversationService(db, tenant_id)
            conversation = await service.get_by_id(conversation_id)
            if not conversation or conversation.agent_id != agent_id:
                raise NotFoundException(
                    message=_("agent_chat.error.conversation_not_found"),
                )
            result = await service.get_conversation_detail(conversation_id)
            return success(data=result)

        @router.delete(
            "/{agent_id}/conversations/{conversation_id}",
            summary="Delete conversation",
        )
        @action_delete("action.admin_agent_chat.delete_conversation")
        async def delete_conversation(
            request: Request,
            db: DbSession,
            agent_id: int,
            conversation_id: int,
            admin: ActiveAdmin,
        ):
            """
            Delete a conversation (soft delete).

            Permission: admin_agent_chat:delete_conversation
            """
            tenant_id = await _get_agent_tenant_id(db, agent_id)
            service = ConversationService(db, tenant_id)

            conversation = await service.get_by_id(conversation_id)
            if not conversation or conversation.agent_id != agent_id:
                raise NotFoundException(
                    message=_("agent_chat.error.conversation_not_found"),
                )

            await service.delete(conversation_id)
            await db.commit()

            return deleted(message=_("agent_chat.conversation_deleted"))


# Export router
router = AdminAgentChatController.get_router()

__all__ = ["router", "AdminAgentChatController"]
