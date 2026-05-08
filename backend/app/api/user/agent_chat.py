"""
用户端 AI 对话 API / User AI Chat API

提供面向终端用户（TenantUser）的 AI 对话接口。
Provides AI chat endpoints for end users (TenantUser).
所有 AI 用量（Token、配额、统计）自动归属用户所在的企业。
All AI usage (tokens, quotas, statistics) is automatically attributed to the user's tenant.
复用现有 AgentChatService / ConversationService / shared helpers。
Reuses existing AgentChatService / ConversationService / shared helpers.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.shared._agent_chat_helpers import (
    enrich_conversations_with_agent,
    handle_route,
)
from app.core.base_controller import BaseController
from app.core.deps import ActiveTenantUser, DbSession, QueryParams
from app.core.i18n import _
from app.core.response import deleted, paginated, success
from app.enums.agent import (
    ConversationOwnerTypeEnum,
    MemoryChannelEnum,
    MemorySceneEnum,
)
from app.enums.common import UserRoleEnum
from app.enums.rbac import PermissionScope
from app.rbac.decorators import (
    auth_only,
    permission_resource,
)
from app.rbac.services.permission_service import PermissionService
from app.schemas.ai.agent_chat import (
    AgentChatRequest,
    AgentRouteRequest,
    UpdateConversationTitleRequest,
)
from app.schemas.common.query import FilterRule
from app.services.ai.account_ai_access_service import AccountAIAccessService
from app.services.ai.agent_chat_service import AgentChatService
from app.services.ai.agent_service import AgentService
from app.services.ai.conversation_service import ConversationService


@permission_resource(
    resource="user_agent_chat",
    name="menu.user.ai_chat",
    scope=PermissionScope.USER,
    parent_resource="menu",
)
class UserAgentChatController(BaseController):
    """
    用户端 AI 对话控制器 / User AI Chat Controller

    所有端点使用 @auth_only（登录即可访问）。
    All endpoints use @auth_only (accessible after login).
    计量通过 tenant_user.tenant_id 自动归属企业。
    Metering is automatically attributed to the tenant via tenant_user.tenant_id.
    """

    prefix = "/ai/agent-chat"
    tags = ["AI Chat (User)"]

    def _register_routes(self) -> None:
        """注册路由 / Register routes"""
        router = self.router

        # ========================================
        # 内部工具函数 / Internal utility functions
        # ========================================

        async def _check_agent_access(
            db: AsyncSession,
            tenant_id: int,
            agent_id: int,
            user_id: int,
            role_id: int | None,
        ) -> None:
            """检查用户是否有权访问该智能体 / Check if user has access to the agent"""
            agent_service = AgentService(db, tenant_id)
            has_access = await agent_service.check_user_access(
                agent_id=agent_id,
                user_id=user_id,
                user_role=UserRoleEnum.TENANT_USER.value,
                user_role_id=role_id,
            )
            if not has_access:
                from app.exceptions import AuthorizationException

                raise AuthorizationException(
                    message=_("agent.access.error.no_permission"),
                )

        async def _ensure_ai_chat_enabled(
            db: DbSession,
            current_user: ActiveTenantUser,
        ) -> None:
            await AccountAIAccessService(db).require_tenant_user_ai_access(current_user)

        # ========================================
        # 对话执行 / Chat execution
        # ========================================

        @router.post(
            "/{agent_id}/chat",
            summary="发送对话消息（非流式） / Send chat message (non-streaming)",
        )
        @auth_only
        async def chat(
            db: DbSession,
            agent_id: int,
            data: AgentChatRequest,
            current_user: ActiveTenantUser,
        ):
            """
            发送对话消息，等待完整响应返回
            Send chat message and wait for complete response

            - 新对话：不传 conversation_id / New conversation: omit conversation_id
            - 续接对话：传 conversation_id / Continue conversation: pass conversation_id
            """
            await _ensure_ai_chat_enabled(db, current_user)
            await _check_agent_access(
                db,
                current_user.tenant_id,
                agent_id,
                current_user.id,
                current_user.role_id,
            )

            perm_service = PermissionService(db)
            user_perms = await perm_service.get_tenant_user_permissions(current_user)
            service = AgentChatService(db, current_user.tenant_id)
            result = await service.chat(
                agent_id=agent_id,
                message=data.message,
                conversation_id=data.conversation_id,
                variables=data.variables,
                user_id=current_user.id,
                knowledge_base_ids=data.knowledge_base_ids,
                user_role=UserRoleEnum.TENANT_USER.value,
                user_role_id=current_user.role_id,
                permissions=user_perms,
                consented_actions=data.consented_actions,
                attachments=[a.model_dump() for a in data.attachments]
                if data.attachments
                else None,
                memory_scene=MemorySceneEnum.AI_CHAT_PAGE.value,
                memory_channel=MemoryChannelEnum.USER_CHAT.value,
                memory_source=MemorySceneEnum.AI_CHAT_PAGE.value,
                interaction_updates=[
                    item.model_dump() for item in data.interaction_updates
                ]
                if data.interaction_updates
                else None,
                trust_policy_ref=data.trust_policy_ref.model_dump()
                if data.trust_policy_ref
                else None,
            )

            return success(data=result.model_dump())

        @router.post(
            "/{agent_id}/chat/stream",
            summary="发送对话消息（SSE 流式） / Send chat message (SSE streaming)",
        )
        @auth_only
        async def stream_chat(
            db: DbSession,
            agent_id: int,
            data: AgentChatRequest,
            current_user: ActiveTenantUser,
        ):
            """
            发送对话消息，通过 SSE 流式推送响应
            Send chat message with SSE streaming response

            事件类型 / Event types:
            - message: 内容增量 / content delta
            - tool_call: 工具调用进度 / tool call progress
            - done: 完成（含 conversation_id、total_tokens） / complete (includes conversation_id, total_tokens)
            - [DONE]: SSE 结束标记 / SSE end marker
            """
            await _ensure_ai_chat_enabled(db, current_user)
            await _check_agent_access(
                db,
                current_user.tenant_id,
                agent_id,
                current_user.id,
                current_user.role_id,
            )

            perm_service = PermissionService(db)
            user_perms = await perm_service.get_tenant_user_permissions(current_user)
            service = AgentChatService(db, current_user.tenant_id)

            return await service.stream_chat(
                agent_id=agent_id,
                message=data.message or "",
                conversation_id=data.conversation_id,
                variables=data.variables,
                user_id=current_user.id,
                knowledge_base_ids=data.knowledge_base_ids,
                user_role=UserRoleEnum.TENANT_USER.value,
                user_role_id=current_user.role_id,
                permissions=user_perms,
                consented_actions=data.consented_actions,
                attachments=[a.model_dump() for a in data.attachments]
                if data.attachments
                else None,
                image_params=data.image_params.model_dump()
                if data.image_params
                else None,
                memory_scene=MemorySceneEnum.AI_CHAT_PAGE.value,
                memory_channel=MemoryChannelEnum.USER_CHAT.value,
                memory_source=MemorySceneEnum.AI_CHAT_PAGE.value,
                interaction_updates=[
                    item.model_dump() for item in data.interaction_updates
                ]
                if data.interaction_updates
                else None,
                trust_policy_ref=data.trust_policy_ref.model_dump()
                if data.trust_policy_ref
                else None,
            )

        # ========================================
        # 智能路由 / Smart routing
        # ========================================

        @router.post(
            "/route", summary="智能体路由 / Agent routing", response_model=None
        )
        @auth_only
        async def route_agent(
            db: DbSession,
            data: AgentRouteRequest,
            current_user: ActiveTenantUser,
        ):
            """
            根据消息、附件类型和当前对话智能选择目标智能体
            Intelligently select target agent from message, attachment flags, and conversation state

            路由优先级 / Routing priority:
            1. pinned_agent_id 直通 / pinned_agent_id pass-through
            2. Router 智能体 AI 选择 / Router agent AI selection
            3. default_chat 降级 / default_chat fallback
            """
            await _ensure_ai_chat_enabled(db, current_user)
            return await handle_route(
                db,
                tenant_id=current_user.tenant_id,
                message=data.message,
                conversation_id=data.conversation_id,
                user_role=UserRoleEnum.TENANT_USER.value,
                user_role_id=current_user.role_id,
                pinned_agent_id=data.pinned_agent_id,
                user_id=current_user.id,
                force_reroute=data.force_reroute,
                has_image_attachments=data.has_image_attachments,
                has_audio_attachments=data.has_audio_attachments,
                has_video_attachments=data.has_video_attachments,
                has_file_attachments=data.has_file_attachments,
            )

        # ========================================
        # 对话管理 / Conversation management
        # ========================================

        @router.get(
            "/conversations", summary="获取 AI 对话列表 / Get AI conversation list"
        )
        @auth_only
        async def list_conversations(
            db: DbSession,
            current_user: ActiveTenantUser,
            query: QueryParams,
        ):
            """
            获取当前用户的所有对话列表 / Get current user conversation list.

            仅返回当前用户自己的对话，不可查看其他用户的。
            Only returns the current user's own conversations, cannot view others'.
            """
            await _ensure_ai_chat_enabled(db, current_user)
            service = ConversationService(db, current_user.tenant_id)
            forced = [
                FilterRule(field="user_id", operator="eq", value=current_user.id),
                FilterRule(
                    field="owner_type",
                    operator="eq",
                    value=ConversationOwnerTypeEnum.TENANT_USER.value,
                ),
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
            summary="获取对话详情 / Get conversation detail",
        )
        @auth_only
        async def get_conversation_detail(
            db: DbSession,
            conversation_id: int,
            current_user: ActiveTenantUser,
        ):
            """获取对话详情（含消息列表） / Get conversation detail (with message list)"""
            await _ensure_ai_chat_enabled(db, current_user)
            service = ConversationService(db, current_user.tenant_id)
            result = await service.get_conversation_detail(
                conversation_id,
                user_id=current_user.id,
                owner_type=ConversationOwnerTypeEnum.TENANT_USER.value,
            )
            return success(data=result)

        @router.get(
            "/conversations/{conversation_id}/compact",
            summary="获取上下文压缩快照 / Get conversation compaction snapshot",
        )
        @auth_only
        async def get_conversation_compact_snapshot(
            db: DbSession,
            conversation_id: int,
            current_user: ActiveTenantUser,
        ):
            await _ensure_ai_chat_enabled(db, current_user)
            service = ConversationService(db, current_user.tenant_id)
            await service.get_accessible_conversation(
                conversation_id,
                user_id=current_user.id,
                owner_type=ConversationOwnerTypeEnum.TENANT_USER.value,
            )
            snapshot = await service.get_context_compaction_snapshot(conversation_id)
            return success(data={"snapshot": snapshot})

        @router.get(
            "/conversations/{conversation_id}/timeline",
            summary="获取对话时间线 / Get conversation timeline",
        )
        @auth_only
        async def get_conversation_timeline(
            db: DbSession,
            conversation_id: int,
            current_user: ActiveTenantUser,
        ):
            await _ensure_ai_chat_enabled(db, current_user)
            service = ConversationService(db, current_user.tenant_id)
            timeline = await service.get_conversation_timeline(
                conversation_id,
                user_id=current_user.id,
                owner_type=ConversationOwnerTypeEnum.TENANT_USER.value,
            )
            return success(data={"timeline": timeline})

        @router.patch(
            "/conversations/{conversation_id}",
            summary="更新对话标题 / Update conversation title",
        )
        @auth_only
        async def update_conversation_title(
            db: DbSession,
            conversation_id: int,
            data: UpdateConversationTitleRequest,
            current_user: ActiveTenantUser,
        ):
            """更新对话标题 / Update conversation title"""
            await _ensure_ai_chat_enabled(db, current_user)
            service = ConversationService(db, current_user.tenant_id)
            conv = await service.update_conversation_title(
                conversation_id,
                title=data.title,
                user_id=current_user.id,
                owner_type=ConversationOwnerTypeEnum.TENANT_USER.value,
            )
            await db.commit()
            return success(data={"id": conv.id, "title": conv.title})

        @router.delete(
            "/conversations/{conversation_id}",
            summary="删除对话 / Delete conversation",
        )
        @auth_only
        async def delete_conversation(
            db: DbSession,
            conversation_id: int,
            current_user: ActiveTenantUser,
        ):
            """删除对话（软删除） / Delete conversation (soft delete)"""
            await _ensure_ai_chat_enabled(db, current_user)
            service = ConversationService(db, current_user.tenant_id)
            await service.delete_accessible_conversation(
                conversation_id,
                user_id=current_user.id,
                owner_type=ConversationOwnerTypeEnum.TENANT_USER.value,
            )
            await db.commit()
            return deleted(message=_("agent_chat.conversation_deleted"))

        # ========================================
        # 记忆管理 / Memory management
        # ========================================

        @router.get(
            "/conversations/{conversation_id}/memory-state",
            summary="获取本会话记忆状态 / Get conversation memory state",
        )
        @auth_only
        async def get_conversation_memory(
            db: DbSession,
            conversation_id: int,
            current_user: ActiveTenantUser,
        ):
            """获取当前会话的记忆状态（偏好/约束/任务/事实） / Get current conversation memory state (preferences/constraints/tasks/facts)"""
            await _ensure_ai_chat_enabled(db, current_user)
            service = ConversationService(db, current_user.tenant_id)
            state = await service.get_conversation_memory_state(
                conversation_id,
                user_id=current_user.id,
                owner_type=ConversationOwnerTypeEnum.TENANT_USER.value,
            )
            return success(data=state)

        @router.delete(
            "/conversations/{conversation_id}/memory-state",
            summary="清空本会话记忆 / Clear conversation memory",
        )
        @auth_only
        async def clear_conversation_memory(
            db: DbSession,
            conversation_id: int,
            current_user: ActiveTenantUser,
        ):
            """清空当前会话的记忆状态 / Clear current conversation memory state"""
            await _ensure_ai_chat_enabled(db, current_user)
            service = ConversationService(db, current_user.tenant_id)
            deleted_count = await service.clear_conversation_memory_state(
                conversation_id,
                user_id=current_user.id,
                owner_type=ConversationOwnerTypeEnum.TENANT_USER.value,
            )
            await db.commit()
            return success(
                data={"deleted_count": deleted_count},
                message=_("agent_chat.memory_cleared"),
            )

        @router.post(
            "/conversations/{conversation_id}/compact",
            summary="重建会话上下文压缩快照 / Rebuild compaction snapshot",
        )
        @auth_only
        async def rebuild_conversation_compaction(
            db: DbSession,
            conversation_id: int,
            current_user: ActiveTenantUser,
        ):
            await _ensure_ai_chat_enabled(db, current_user)
            service = ConversationService(db, current_user.tenant_id)
            snapshot = await service.rebuild_context_compaction_snapshot(
                conversation_id,
                user_id=current_user.id,
                owner_type=ConversationOwnerTypeEnum.TENANT_USER.value,
            )
            await db.commit()
            return success(data=snapshot or {})

        @router.get(
            "/conversations/{conversation_id}/timeline",
            summary="获取会话运行时间线 / Get conversation run timeline",
        )
        @auth_only
        async def get_conversation_run_timeline(
            db: DbSession,
            conversation_id: int,
            current_user: ActiveTenantUser,
        ):
            await _ensure_ai_chat_enabled(db, current_user)
            service = ConversationService(db, current_user.tenant_id)
            items = await service.get_conversation_timeline(
                conversation_id,
                user_id=current_user.id,
                owner_type=ConversationOwnerTypeEnum.TENANT_USER.value,
            )
            return success(data=items)


# 导出路由器 / Export router
router = UserAgentChatController.get_router()

__all__ = ["router", "UserAgentChatController"]
