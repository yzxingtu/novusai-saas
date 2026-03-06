"""
租户端 AI 对话 API

提供 AI 对话（非流式/流式）、对话列表、删除等接口
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
)
from app.services.ai.agent_chat_service import AgentChatService
from app.services.ai.agent_service import AgentService
from app.services.ai.conversation_service import ConversationService


@permission_resource(
    resource="agent_chat",
    name="menu.tenant.agent_chat",
    scope=PermissionScope.ALL_TENANTS,
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
    租户 AI 对话控制器

    提供 AI 对话交互和对话管理
    """

    prefix = "/ai/agent-chat"
    tags = [_("menu.tags.tenant_agent_chat")]

    def _register_routes(self) -> None:
        """注册路由"""
        router = self.router

        # ========================================
        # 对话执行
        # ========================================

        async def _check_agent_access(
            db: AsyncSession,
            tenant_id: int,
            agent_id: int,
            user_id: int,
        ) -> None:
            """检查用户是否有权访问该智能体"""
            agent_service = AgentService(db, tenant_id)
            has_access = await agent_service.check_user_access(
                agent_id=agent_id,
                user_id=user_id,
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
            发送对话消息，等待完整响应返回

            - 新对话：不传 conversation_id
            - 续接对话：传 conversation_id

            权限: agent_chat:chat
            """
            await _check_agent_access(db, tenant_admin.tenant_id, agent_id, tenant_admin.id)

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
                permissions=user_perms,
                consented_actions=data.consented_actions,
                attachments=[a.model_dump() for a in data.attachments] if data.attachments else None,
                memory_scene=MemorySceneEnum.AI_CHAT_PAGE.value,
                memory_channel=MemoryChannelEnum.TENANT_CHAT.value,
                memory_source=MemorySceneEnum.AI_CHAT_PAGE.value,
                page_session_id=data.page_session_id,
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
            发送对话消息，通过 SSE 流式推送响应

            事件类型：
            - message: 内容增量
            - tool_call: 工具调用进度
            - done: 完成（含 conversation_id、total_tokens）
            - [DONE]: SSE 结束标记

            权限: agent_chat:stream
            """
            await _check_agent_access(db, tenant_admin.tenant_id, agent_id, tenant_admin.id)

            perm_service = PermissionService(db)
            user_perms = await perm_service.get_tenant_admin_permissions(tenant_admin)
            service = AgentChatService(db, tenant_admin.tenant_id)

            return await service.stream_chat(
                agent_id=agent_id,
                message=data.message,
                conversation_id=data.conversation_id,
                variables=data.variables,
                page_context=data.page_context,
                user_id=tenant_admin.id,
                knowledge_base_ids=data.knowledge_base_ids,
                user_role=UserRoleEnum.TENANT_ADMIN.value,
                permissions=user_perms,
                consented_actions=data.consented_actions,
                attachments=[a.model_dump() for a in data.attachments] if data.attachments else None,
                image_params=data.image_params.model_dump() if data.image_params else None,
                memory_scene=MemorySceneEnum.AI_CHAT_PAGE.value,
                memory_channel=MemoryChannelEnum.TENANT_CHAT.value,
                memory_source=MemorySceneEnum.AI_CHAT_PAGE.value,
                page_session_id=data.page_session_id,
            )

        # ========================================
        # 智能路由
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
            根据消息和页面上下文智能选择目标智能体

            路由优先级:
            1. pinned_agent_id 直通
            2. Router 智能体 AI 选择
            3. default_chat 降级

            权限: agent_chat:route
            """
            return await handle_route(
                db,
                tenant_id=tenant_admin.tenant_id,
                message=data.message,
                is_admin_context=False,
                page_context=data.page_context.model_dump() if data.page_context else None,
                pinned_agent_id=data.pinned_agent_id,
            )

        # ========================================
        # 操作确认
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
            处理 AI 操作确认或取消

            - action="confirm": 验证 confirm_id 并执行操作
            - action="cancel": 删除 confirm_id，取消操作

            权限: agent_chat:confirm
            """
            service = AgentChatService(db, tenant_admin.tenant_id)
            return await handle_confirm_or_cancel(
                service, data,
                tenant_id=tenant_admin.tenant_id,
                user_id=tenant_admin.id,
            )

        # ========================================
        # 对话管理
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
            获取当前用户所有智能体的对话列表

            用于 AI 面板的全局历史侧边栏，包含 agent_name 和 agent_avatar。

            权限: agent_chat:conversations
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
            获取对话详情（含消息列表）

            权限: agent_chat:conversation_detail
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
            删除对话（软删除）

            权限: agent_chat:delete_conversation
            """
            service = ConversationService(db, tenant_admin.tenant_id)
            await service.delete_accessible_conversation(
                conversation_id,
                user_id=tenant_admin.id,
            )
            await db.commit()
            return deleted(message=_("agent_chat.conversation_deleted"))

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
            获取当前会话的记忆状态（偏好/约束/任务/事实）
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
        @action_delete("action.agent_chat.delete_conversation")
        async def clear_conversation_memory(
            request: Request,
            db: DbSession,
            conversation_id: int,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            清空当前会话的记忆状态（仅当前租户当前用户）
            """
            service = ConversationService(db, tenant_admin.tenant_id)
            deleted_count = await service.clear_conversation_memory_state(
                conversation_id,
                user_id=tenant_admin.id,
            )
            return success(data={"deleted_count": deleted_count}, message=_("agent_chat.memory_cleared"))


# 导出路由器
router = TenantAgentChatController.get_router()

__all__ = ["router", "TenantAgentChatController"]
