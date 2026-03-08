"""
用户端 AI 对话 API

提供面向终端用户（TenantUser）的 AI 对话接口。
所有 AI 用量（Token、配额、统计）自动归属用户所在的租户。
复用现有 AgentChatService / ConversationService / shared helpers。
"""

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.shared._agent_chat_helpers import (
    enrich_conversations_with_agent,
    handle_confirm_or_cancel,
    handle_route,
)
from app.core.base_controller import BaseController
from app.core.deps import ActiveTenantUser, DbSession, QueryParams
from app.core.i18n import _
from app.core.response import deleted, paginated, success
from app.enums.agent import MemoryChannelEnum, MemorySceneEnum
from app.enums.common import UserRoleEnum
from app.enums.rbac import PermissionScope
from app.rbac.decorators import (
    MenuConfig,
    auth_only,
    permission_resource,
)
from app.schemas.ai.agent_chat import (
    AgentChatRequest,
    AgentConfirmRequest,
    AgentRouteRequest,
)
from app.schemas.common.query import FilterRule
from app.services.ai.agent_chat_service import AgentChatService
from app.services.ai.agent_service import AgentService
from app.services.ai.conversation_service import ConversationService


@permission_resource(
    resource="user_agent_chat",
    name="menu.user.ai_chat",
    scope=PermissionScope.TENANT_USER,
    parent_resource="menu",
    menu=MenuConfig(
        icon="lucide:message-square",
        path="/ai-chat",
        parent="menu",
        sort_order=20,
        hidden=True,
    ),
)
class UserAgentChatController(BaseController):
    """
    用户端 AI 对话控制器

    所有端点使用 @auth_only（登录即可访问）。
    计量通过 tenant_user.tenant_id 自动归属租户。
    """

    prefix = "/ai/agent-chat"
    tags = ["AI Chat (User)"]

    def _register_routes(self) -> None:
        """注册路由"""
        router = self.router

        # ========================================
        # 内部工具函数
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

        # ========================================
        # 对话执行
        # ========================================

        @router.post("/{agent_id}/chat", summary="发送对话消息（非流式）")
        @auth_only
        async def chat(
            request: Request,
            db: DbSession,
            agent_id: int,
            data: AgentChatRequest,
            current_user: ActiveTenantUser,
        ):
            """
            发送对话消息，等待完整响应返回

            - 新对话：不传 conversation_id
            - 续接对话：传 conversation_id
            """
            await _check_agent_access(db, current_user.tenant_id, agent_id, current_user.id)

            service = AgentChatService(db, current_user.tenant_id)
            result = await service.chat(
                agent_id=agent_id,
                message=data.message,
                conversation_id=data.conversation_id,
                variables=data.variables,
                page_context=data.page_context,
                user_id=current_user.id,
                knowledge_base_ids=data.knowledge_base_ids,
                user_role=UserRoleEnum.TENANT_USER.value,
                permissions=[],
                consented_actions=data.consented_actions,
                attachments=[a.model_dump() for a in data.attachments] if data.attachments else None,
                memory_scene=MemorySceneEnum.AI_CHAT_PAGE.value,
                memory_channel=MemoryChannelEnum.USER_CHAT.value,
                memory_source=MemorySceneEnum.AI_CHAT_PAGE.value,
                page_session_id=data.page_session_id,
            )

            return success(data=result.model_dump())

        @router.post("/{agent_id}/chat/stream", summary="发送对话消息（SSE 流式）")
        @auth_only
        async def stream_chat(
            request: Request,
            db: DbSession,
            agent_id: int,
            data: AgentChatRequest,
            current_user: ActiveTenantUser,
        ):
            """
            发送对话消息，通过 SSE 流式推送响应

            事件类型：
            - message: 内容增量
            - tool_call: 工具调用进度
            - done: 完成（含 conversation_id、total_tokens）
            - [DONE]: SSE 结束标记
            """
            await _check_agent_access(db, current_user.tenant_id, agent_id, current_user.id)

            service = AgentChatService(db, current_user.tenant_id)

            return await service.stream_chat(
                agent_id=agent_id,
                message=data.message,
                conversation_id=data.conversation_id,
                variables=data.variables,
                page_context=data.page_context,
                user_id=current_user.id,
                knowledge_base_ids=data.knowledge_base_ids,
                user_role=UserRoleEnum.TENANT_USER.value,
                permissions=[],
                consented_actions=data.consented_actions,
                attachments=[a.model_dump() for a in data.attachments] if data.attachments else None,
                image_params=data.image_params.model_dump() if data.image_params else None,
                memory_scene=MemorySceneEnum.AI_CHAT_PAGE.value,
                memory_channel=MemoryChannelEnum.USER_CHAT.value,
                memory_source=MemorySceneEnum.AI_CHAT_PAGE.value,
                page_session_id=data.page_session_id,
            )

        # ========================================
        # 智能路由
        # ========================================

        @router.post("/route", summary="智能体路由", response_model=None)
        @auth_only
        async def route_agent(
            request: Request,
            db: DbSession,
            data: AgentRouteRequest,
            current_user: ActiveTenantUser,
        ):
            """
            根据消息和页面上下文智能选择目标智能体

            路由优先级:
            1. pinned_agent_id 直通
            2. Router 智能体 AI 选择
            3. default_chat 降级
            """
            return await handle_route(
                db,
                tenant_id=current_user.tenant_id,
                message=data.message,
                is_admin_context=False,
                page_context=data.page_context.model_dump() if data.page_context else None,
                pinned_agent_id=data.pinned_agent_id,
            )

        # ========================================
        # 操作确认
        # ========================================

        @router.post("/confirm", summary="确认/取消 AI 操作")
        @auth_only
        async def confirm_action(
            request: Request,
            db: DbSession,
            data: AgentConfirmRequest,
            current_user: ActiveTenantUser,
        ):
            """
            处理 AI 操作确认或取消

            - action="confirm": 验证 confirm_id 并执行操作
            - action="cancel": 删除 confirm_id，取消操作
            """
            service = AgentChatService(db, current_user.tenant_id)
            return await handle_confirm_or_cancel(
                service, data,
                tenant_id=current_user.tenant_id,
                user_id=current_user.id,
            )

        # ========================================
        # 对话管理
        # ========================================

        @router.get("/conversations", summary="获取 AI 对话列表")
        @auth_only
        async def list_conversations(
            request: Request,
            db: DbSession,
            current_user: ActiveTenantUser,
            query: QueryParams,
        ):
            """
            获取当前用户的所有对话列表

            仅返回当前用户自己的对话，不可查看其他用户的。
            """
            service = ConversationService(db, current_user.tenant_id)
            forced = [
                FilterRule(field="user_id", operator="eq", value=current_user.id),
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
        @auth_only
        async def get_conversation_detail(
            request: Request,
            db: DbSession,
            conversation_id: int,
            current_user: ActiveTenantUser,
        ):
            """获取对话详情（含消息列表）"""
            service = ConversationService(db, current_user.tenant_id)
            result = await service.get_conversation_detail(
                conversation_id,
                user_id=current_user.id,
            )
            return success(data=result)

        @router.delete(
            "/conversations/{conversation_id}",
            summary="删除对话",
        )
        @auth_only
        async def delete_conversation(
            request: Request,
            db: DbSession,
            conversation_id: int,
            current_user: ActiveTenantUser,
        ):
            """删除对话（软删除）"""
            service = ConversationService(db, current_user.tenant_id)
            await service.delete_accessible_conversation(
                conversation_id,
                user_id=current_user.id,
            )
            await db.commit()
            return deleted(message=_("agent_chat.conversation_deleted"))

        # ========================================
        # 记忆管理
        # ========================================

        @router.get(
            "/conversations/{conversation_id}/memory-state",
            summary="获取本会话记忆状态",
        )
        @auth_only
        async def get_conversation_memory(
            request: Request,
            db: DbSession,
            conversation_id: int,
            current_user: ActiveTenantUser,
        ):
            """获取当前会话的记忆状态（偏好/约束/任务/事实）"""
            service = ConversationService(db, current_user.tenant_id)
            state = await service.get_conversation_memory_state(
                conversation_id,
                user_id=current_user.id,
            )
            return success(data=state)

        @router.delete(
            "/conversations/{conversation_id}/memory-state",
            summary="清空本会话记忆",
        )
        @auth_only
        async def clear_conversation_memory(
            request: Request,
            db: DbSession,
            conversation_id: int,
            current_user: ActiveTenantUser,
        ):
            """清空当前会话的记忆状态"""
            service = ConversationService(db, current_user.tenant_id)
            deleted_count = await service.clear_conversation_memory_state(
                conversation_id,
                user_id=current_user.id,
            )
            return success(data={"deleted_count": deleted_count}, message=_("agent_chat.memory_cleared"))


# 导出路由器
router = UserAgentChatController.get_router()

__all__ = ["router", "UserAgentChatController"]
