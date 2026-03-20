"""
企业端 AI 对话 API / Tenant AI Chat API

提供 AI 对话（非流式/流式）、对话列表、删除等接口
Provides AI chat (non-streaming/streaming), conversation list, delete endpoints
"""

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_controller import TenantController
from app.core.deps import ActiveTenantAdmin, DbSession, QueryParams
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
from app.services.ai.agent_service import AgentService
from app.services.ai.conversation_service import ConversationService


@permission_resource(
    resource="agent_chat",
    name="menu.tenant.agent_chat",
    scope=PermissionScope.TENANT,
    parent_resource="ai_workspace",
    menu=MenuConfig(
        icon="lucide:message-square",
        path="/ai/chat",
        parent="ai_workspace",
        sort_order=20,
        hidden=True,
    ),
)
class TenantAgentChatController(TenantController):
    """
    企业 AI 对话控制器 / Tenant AI Chat Controller

    提供 AI 对话交互和对话管理
    Provides AI chat interaction and conversation management
    """

    prefix = "/ai/agent-chat"
    tags = [_("menu.tags.tenant_agent_chat")]

    def _register_routes(self) -> None:
        """注册路由 / Register routes"""
        router = self.router

        # ========================================
        # 对话执行 / Chat Execution
        # ========================================

        async def _check_agent_access(
            db: AsyncSession,
            tenant_id: int,
            agent_id: int,
            user_id: int,
            role_id: int | None,
        ) -> None:
            """检查用户是否有权访问该智能体 / Check if user has access to this agent"""
            agent_service = AgentService(db, tenant_id)
            has_access = await agent_service.check_user_access(
                agent_id=agent_id,
                user_id=user_id,
                user_role=UserRoleEnum.TENANT_ADMIN.value,
                user_role_id=role_id,
            )
            if not has_access:
                from app.exceptions import AuthorizationException
                raise AuthorizationException(
                    message=_("agent.access.error.no_permission"),
                )

        @router.post("/{agent_id}/chat", summary="发送对话消息（非流式）")
        @action_create("action.agent_chat.chat")
        async def chat(
            request: Request,
            db: DbSession,
            agent_id: int,
            data: AgentChatRequest,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            发送对话消息，等待完整响应返回 / Send chat message, wait for complete response

            - 新对话：不传 conversation_id / New conversation: omit conversation_id
            - 续接对话：传 conversation_id / Continue conversation: pass conversation_id

            权限 / Permission: agent_chat:chat
            """
            await _check_agent_access(
                db, tenant_admin.tenant_id, agent_id, tenant_admin.id, tenant_admin.role_id
            )

            perm_service = PermissionService(db)
            user_perms = await perm_service.get_tenant_admin_permissions(tenant_admin)
            service = AgentChatService(db, tenant_admin.tenant_id)
            result = await service.chat(
                agent_id=agent_id,
                message=data.message,
                conversation_id=data.conversation_id,
                variables=data.variables,
                page_context=data.page_context,
                user_id=tenant_admin.id,
                knowledge_base_ids=data.knowledge_base_ids,
                user_role=UserRoleEnum.TENANT_ADMIN.value,
                user_role_id=tenant_admin.role_id,
                permissions=user_perms,
                consented_actions=data.consented_actions,
                attachments=[a.model_dump() for a in data.attachments] if data.attachments else None,
                memory_scene=MemorySceneEnum.AI_CHAT_PAGE.value,
                memory_channel=MemoryChannelEnum.TENANT_CHAT.value,
                memory_source=MemorySceneEnum.AI_CHAT_PAGE.value,
                page_session_id=data.page_session_id,
                route_source=data.route_source,
            )

            return success(data=result.model_dump())

        @router.post("/{agent_id}/chat/stream", summary="发送对话消息（SSE 流式）")
        @action_create("action.agent_chat.stream")
        async def stream_chat(
            request: Request,
            db: DbSession,
            agent_id: int,
            data: AgentChatRequest,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            发送对话消息，通过 SSE 流式推送响应 / Send chat message, stream response via SSE

            事件类型 / Event types：
            - message: 内容增量 / content delta
            - tool_call: 工具调用进度 / tool call progress
            - done: 完成（含 conversation_id、total_tokens） / complete (with conversation_id, total_tokens)
            - [DONE]: SSE 结束标记 / SSE end marker

            权限 / Permission: agent_chat:stream
            """
            await _check_agent_access(
                db, tenant_admin.tenant_id, agent_id, tenant_admin.id, tenant_admin.role_id
            )

            perm_service = PermissionService(db)
            user_perms = await perm_service.get_tenant_admin_permissions(tenant_admin)
            service = AgentChatService(db, tenant_admin.tenant_id)

            return await service.stream_chat(
                agent_id=agent_id,
                message=data.message or "",
                messages=data.messages,
                conversation_id=data.conversation_id,
                variables=data.variables,
                page_context=data.page_context,
                user_id=tenant_admin.id,
                knowledge_base_ids=data.knowledge_base_ids,
                user_role=UserRoleEnum.TENANT_ADMIN.value,
                user_role_id=tenant_admin.role_id,
                permissions=user_perms,
                consented_actions=data.consented_actions,
                attachments=[a.model_dump() for a in data.attachments] if data.attachments else None,
                image_params=data.image_params.model_dump() if data.image_params else None,
                memory_scene=MemorySceneEnum.AI_CHAT_PAGE.value,
                memory_channel=MemoryChannelEnum.TENANT_CHAT.value,
                memory_source=MemorySceneEnum.AI_CHAT_PAGE.value,
                page_session_id=data.page_session_id,
                route_source=data.route_source,
            )

        # ========================================
        # 智能路由 / Smart Routing
        # ========================================

        @router.post("/route", summary="智能体路由", response_model=None)
        @action_create("action.agent_chat.route")
        async def route_agent(
            request: Request,
            db: DbSession,
            data: AgentRouteRequest,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            根据消息和页面上下文智能选择目标智能体 / Smart select target agent based on message and page context

            路由优先级 / Routing priority:
            1. pinned_agent_id 直通 / pinned_agent_id direct pass
            2. Router 智能体 AI 选择 / Router agent AI selection
            3. default_chat 降级 / default_chat fallback

            权限 / Permission: agent_chat:route
            """
            return await handle_route(
                db,
                tenant_id=tenant_admin.tenant_id,
                message=data.message,
                user_role=UserRoleEnum.TENANT_ADMIN.value,
                user_role_id=tenant_admin.role_id,
                page_context=data.page_context.model_dump() if data.page_context else None,
                pinned_agent_id=data.pinned_agent_id,
                user_id=tenant_admin.id,
                has_image_attachments=data.has_image_attachments,
            )

        # ========================================
        # 操作确认 / Action Confirmation
        # ========================================

        @router.post("/confirm", summary="确认/取消 AI 操作")
        @action_create("action.agent_chat.confirm")
        async def confirm_action(
            request: Request,
            db: DbSession,
            data: AgentConfirmRequest,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            处理 AI 操作确认或取消 / Handle AI action confirmation or cancellation

            - action="confirm": 验证 confirm_id 并执行操作 / Verify confirm_id and execute action
            - action="cancel": 删除 confirm_id，取消操作 / Delete confirm_id, cancel action

            权限 / Permission: agent_chat:confirm
            """
            service = AgentChatService(db, tenant_admin.tenant_id)
            return await handle_confirm_or_cancel(
                service, data,
                tenant_id=tenant_admin.tenant_id,
                user_id=tenant_admin.id,
            )

        # ========================================
        # 对话管理 / Conversation Management
        # ========================================

        @router.get("/conversations", summary="获取全局 AI 对话列表")
        @action_read("action.agent_chat.conversations")
        async def list_all_conversations(
            request: Request,
            db: DbSession,
            tenant_admin: ActiveTenantAdmin,
            query: QueryParams,
        ):
            """
            获取当前用户所有智能体的对话列表 / Get all agent conversation list for current user

            用于 AI 面板的全局历史侧边栏，包含 agent_name 和 agent_avatar。
            Used for AI panel global history sidebar, includes agent_name and agent_avatar.

            权限 / Permission: agent_chat:conversations
            """
            service = ConversationService(db, tenant_admin.tenant_id)
            from app.schemas.common.query import FilterRule
            forced = [
                FilterRule(field="user_id", operator="eq", value=tenant_admin.id),
            ]
            items, total = await service.query_list(
                spec=query,
                forced_filters=forced,
            )
            return paginated(
                items=enrich_conversations_with_agent(items),
                total=total,
                page=query.page,
                page_size=query.size,
            )

        @router.get(
            "/conversations/{conversation_id}",
            summary="获取对话详情",
        )
        @action_read("action.agent_chat.conversation_detail")
        async def get_conversation_detail(
            request: Request,
            db: DbSession,
            conversation_id: int,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            获取对话详情（含消息列表） / Get conversation details (with message list)

            权限 / Permission: agent_chat:conversation_detail
            """
            service = ConversationService(db, tenant_admin.tenant_id)
            result = await service.get_conversation_detail(
                conversation_id,
                user_id=tenant_admin.id,
            )
            return success(data=result)

        @router.delete(
            "/conversations/{conversation_id}",
            summary="删除对话",
        )
        @action_delete("action.agent_chat.delete_conversation")
        async def delete_conversation(
            request: Request,
            db: DbSession,
            conversation_id: int,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            删除对话（软删除） / Delete conversation (soft delete)

            权限 / Permission: agent_chat:delete_conversation
            """
            service = ConversationService(db, tenant_admin.tenant_id)
            await service.delete_accessible_conversation(
                conversation_id,
                user_id=tenant_admin.id,
            )
            await db.commit()
            return deleted(message=_("agent_chat.conversation_deleted"))

        @router.patch(
            "/conversations/{conversation_id}",
            summary="更新对话标题",
        )
        @action_create("action.agent_chat.update_conversation")
        async def update_conversation_title(
            request: Request,
            db: DbSession,
            conversation_id: int,
            data: UpdateConversationTitleRequest,
            tenant_admin: ActiveTenantAdmin,
        ):
            """更新对话标题 / Update conversation title"""
            service = ConversationService(db, tenant_admin.tenant_id)
            conv = await service.update_conversation_title(
                conversation_id,
                title=data.title,
                user_id=tenant_admin.id,
            )
            await db.commit()
            return success(data={"id": conv.id, "title": conv.title})

        @router.get(
            "/conversations/{conversation_id}/memory-state",
            summary="获取本会话记忆状态",
        )
        @action_read("action.agent_chat.read_conversation")
        async def get_conversation_memory(
            request: Request,
            db: DbSession,
            conversation_id: int,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            获取当前会话的记忆状态（偏好/约束/任务/事实） / Get current conversation memory state (preferences/constraints/tasks/facts)
            """
            service = ConversationService(db, tenant_admin.tenant_id)
            state = await service.get_conversation_memory_state(
                conversation_id,
                user_id=tenant_admin.id,
            )
            return success(data=state)

        @router.delete(
            "/conversations/{conversation_id}/memory-state",
            summary="清空本会话记忆",
        )
        @action_delete("action.agent_chat.clear_memory")
        async def clear_conversation_memory(
            request: Request,
            db: DbSession,
            conversation_id: int,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            清空当前会话的记忆状态（仅当前企业当前用户） / Clear current conversation memory state (current tenant and user only)
            """
            service = ConversationService(db, tenant_admin.tenant_id)
            deleted_count = await service.clear_conversation_memory_state(
                conversation_id,
                user_id=tenant_admin.id,
            )
            return success(data={"deleted_count": deleted_count}, message=_("agent_chat.memory_cleared"))


# 导出路由器 / Export router
router = TenantAgentChatController.get_router()

__all__ = ["router", "TenantAgentChatController"]
