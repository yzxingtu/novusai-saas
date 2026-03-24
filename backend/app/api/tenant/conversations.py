"""
企业端对话管理 API / Tenant Conversation Management API

提供对话列表、详情、搜索、归档、删除和导出接口
Provides conversation list, details, search, archive, delete and export endpoints
"""

from fastapi import Query, Request

from app.core.base_controller import TenantController
from app.core.deps import ActiveTenantAdmin, DbSession, QueryParams
from app.core.i18n import _
from app.core.response import deleted, paginated, success
from app.enums.rbac import PermissionScope
from app.exceptions import NotFoundException
from app.rbac.decorators import (
    MenuConfig,
    action_delete,
    action_read,
    action_update,
    permission_resource,
)
from app.services.ai.conversation_service import ConversationService


# ============================================
# Controller / 控制器
# ============================================

@permission_resource(
    resource="agent_conversation",
    name="menu.tenant.agent_conversation",
    scope=PermissionScope.TENANT,
    parent_resource="ai_analytics",
    menu=MenuConfig(
        icon="lucide:message-square-text",
        path="/ai/conversations",
        component="ai/conversations/index",
        parent="ai_analytics",
        sort_order=20,
    ),
)
class TenantConversationController(TenantController):
    """
    企业端对话管理控制器 / Tenant Conversation Management Controller

    提供对话列表、详情、搜索、归档、删除和导出操作
    Provides conversation list, details, search, archive, delete and export operations
    """

    prefix = "/ai/conversations"
    tags = [_("tag.conversation_management")]

    def _register_routes(self) -> None:
        """注册路由 / Register routes"""
        router = self.router

        @router.get("", summary="获取对话列表")
        @action_read("action.agent_conversation.list")
        async def list_conversations(
            request: Request,
            db: DbSession,
            tenant_admin: ActiveTenantAdmin,
            query: QueryParams,
        ):
            """
            获取对话列表 / Get conversation list

            支持 JSON:API 分页、筛选、排序 / Supports JSON:API pagination, filtering, sorting
            权限 / Permission: agent_conversation:list
            """
            service = ConversationService(db, tenant_admin.tenant_id)
            items, total = await service.query_list(spec=query)
            result = await service.enrich_conversation_list(
                items, include_user_info=True,
            )
            return paginated(
                items=result,
                total=total,
                page=query.page,
                page_size=query.size,
            )

        @router.get("/search", summary="搜索对话消息")
        @action_read("action.agent_conversation.search")
        async def search_messages(
            request: Request,
            db: DbSession,
            tenant_admin: ActiveTenantAdmin,
            keyword: str = Query(..., min_length=1, max_length=200),
            page: int = Query(1, ge=1),
            page_size: int = Query(20, ge=1, le=100),
        ):
            """
            跨对话全文搜索消息内容 / Full-text search message content across conversations

            权限 / Permission: agent_conversation:search
            """
            service = ConversationService(db, tenant_admin.tenant_id)
            result = await service.search_messages(
                keyword=keyword,
                page=page,
                page_size=page_size,
            )

            return success(data=result)

        @router.get("/{conversation_id}", summary="获取对话详情")
        @action_read("action.agent_conversation.detail")
        async def get_conversation(
            request: Request,
            db: DbSession,
            conversation_id: int,
            tenant_admin: ActiveTenantAdmin,
            message_skip: int = Query(0, ge=0),
            message_limit: int = Query(50, ge=1, le=200),
        ):
            """
            获取对话详情（含分页消息列表） / Get conversation details (with paginated message list)

            权限 / Permission: agent_conversation:detail
            """
            service = ConversationService(db, tenant_admin.tenant_id)
            result = await service.get_conversation_detail(
                conversation_id=conversation_id,
                message_skip=message_skip,
                message_limit=message_limit,
            )

            conv = await service.get_by_id(conversation_id)
            if conv:
                result = await service.enrich_conversation_detail(result, conv)

            return success(data=result)

        @router.post("/{conversation_id}/archive", summary="归档对话")
        @action_update("action.agent_conversation.archive")
        async def archive_conversation(
            request: Request,
            db: DbSession,
            conversation_id: int,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            归档对话 / Archive conversation

            权限 / Permission: agent_conversation:archive
            """
            service = ConversationService(db, tenant_admin.tenant_id)
            conv = await service.archive_conversation(conversation_id)
            await db.commit()

            return success(
                data=conv.to_dict(),
                message=_("conversation.archived"),
            )

        @router.delete("/{conversation_id}", summary="删除对话")
        @action_delete("action.agent_conversation.delete")
        async def delete_conversation(
            request: Request,
            db: DbSession,
            conversation_id: int,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            删除对话（软删除） / Delete conversation (soft delete)

            权限 / Permission: agent_conversation:delete
            """
            service = ConversationService(db, tenant_admin.tenant_id)

            conv = await service.get_by_id(conversation_id)
            if not conv:
                raise NotFoundException(message=_("conversation.not_found"))

            await service.delete(conversation_id)
            await db.commit()

            return deleted(message=_("conversation.deleted"))

        @router.get("/{conversation_id}/export", summary="导出对话")
        @action_read("action.agent_conversation.export")
        async def export_conversation(
            request: Request,
            db: DbSession,
            conversation_id: int,
            tenant_admin: ActiveTenantAdmin,
            format: str = Query("json", pattern="^(json|markdown)$"),
        ):
            """
            导出对话数据（JSON / Markdown） / Export conversation data (JSON / Markdown)

            权限 / Permission: agent_conversation:export
            """
            service = ConversationService(db, tenant_admin.tenant_id)
            result = await service.export_conversation(
                conversation_id=conversation_id,
                export_format=format,
            )

            return success(
                data=result,
                message=_("conversation.exported"),
            )


# 导出路由器 / Export router
router = TenantConversationController.get_router()

__all__ = ["router", "TenantConversationController"]
