"""
租户端对话管理 API

提供对话列表、详情、搜索、归档、批量归档、删除和导出接口
"""

from fastapi import Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_controller import TenantController
from app.core.deps import ActiveTenantAdmin, DbSession, QueryParams
from app.core.i18n import _
from app.core.response import deleted, paginated, success
from app.enums.rbac import PermissionScope
from app.exceptions import NotFoundException
from app.models.tenant.tenant_admin import TenantAdmin
from app.rbac.decorators import (
    MenuConfig,
    action_delete,
    action_read,
    action_update,
    permission_resource,
)
from app.services.ai.conversation_service import ConversationService

# ============================================
# 请求 Schema
# ============================================

class BatchArchiveRequest(BaseModel):
    """批量归档请求"""
    agent_id: int | None = Field(None, description=_("conversation.agent_id"))
    before_days: int = Field(90, ge=1, le=365, description=_("conversation.before_days"))


# ============================================
# 列表项辅助函数
# ============================================

def _build_conversation_list_item(
    conv,
    user_map: dict[int, dict] | None = None,
) -> dict:
    """从 ORM 对象构建列表项字典"""
    agent_name = None
    agent_avatar = None
    try:
        agent_obj = getattr(conv, "agent", None)
        if agent_obj is not None:
            agent_name = agent_obj.name
            agent_avatar = agent_obj.avatar
    except AttributeError:
        pass

    user_info = None
    if user_map and conv.user_id is not None:
        user_info = user_map.get(conv.user_id)

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
        "agent_avatar": agent_avatar,
        "user_info": user_info,
        "created_at": conv.created_at,
        "updated_at": conv.updated_at,
    }


async def _batch_load_tenant_users(
    db: AsyncSession, user_ids: set[int],
) -> dict[int, dict]:
    """批量加载租户管理员信息"""
    if not user_ids:
        return {}
    stmt = select(
        TenantAdmin.id, TenantAdmin.username,
        TenantAdmin.nickname, TenantAdmin.avatar,
    ).where(
        TenantAdmin.id.in_(user_ids),
        TenantAdmin.is_deleted.is_(False),
    )
    result = await db.execute(stmt)
    return {
        row.id: {
            "id": row.id,
            "username": row.username,
            "nickname": row.nickname,
            "avatar": row.avatar,
        }
        for row in result.all()
    }


# ============================================
# Controller
# ============================================

@permission_resource(
    resource="agent_conversation",
    name="menu.tenant.agent_conversation",
    scope=PermissionScope.ALL_TENANTS,
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
    租户端对话管理控制器

    提供对话列表、详情、搜索、归档、批量归档、删除和导出操作
    """

    prefix = "/ai/conversations"
    tags = [_("tag.conversation_management")]

    def _register_routes(self) -> None:
        """注册路由"""
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
            获取对话列表

            支持 JSON:API 分页、筛选、排序
            权限: agent_conversation:list
            """
            service = ConversationService(db, tenant_admin.tenant_id)
            items, total = await service.query_list(spec=query)

            # 批量加载用户信息
            user_ids = {c.user_id for c in items if c.user_id is not None}
            user_map = await _batch_load_tenant_users(db, user_ids)

            result = [
                _build_conversation_list_item(item, user_map)
                for item in items
            ]

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
            跨对话全文搜索消息内容

            权限: agent_conversation:search
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
            获取对话详情（含分页消息列表）

            权限: agent_conversation:detail
            """
            service = ConversationService(db, tenant_admin.tenant_id)
            result = await service.get_conversation_detail(
                conversation_id=conversation_id,
                message_skip=message_skip,
                message_limit=message_limit,
            )

            # 补充 agent avatar
            conv = await service.get_by_id(conversation_id)
            if conv:
                agent_obj = getattr(conv, "agent", None)
                result["agent_avatar"] = agent_obj.avatar if agent_obj else None

                # 补充 user info
                if conv.user_id is not None:
                    u_map = await _batch_load_tenant_users(
                        db, {conv.user_id},
                    )
                    result["user_info"] = u_map.get(conv.user_id)
                else:
                    result["user_info"] = None

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
            归档对话

            权限: agent_conversation:archive
            """
            service = ConversationService(db, tenant_admin.tenant_id)
            conv = await service.archive_conversation(conversation_id)
            await db.commit()

            return success(
                data=conv.to_dict(),
                message=_("conversation.archived"),
            )

        @router.post("/batch-archive", summary="批量归档对话")
        @action_update("action.agent_conversation.batch_archive")
        async def batch_archive(
            request: Request,
            db: DbSession,
            data: BatchArchiveRequest,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            批量归档 N 天前的对话

            权限: agent_conversation:batch_archive
            """
            service = ConversationService(db, tenant_admin.tenant_id)
            count = await service.batch_archive(
                agent_id=data.agent_id,
                before_days=data.before_days,
            )
            await db.commit()

            return success(
                data={"archived_count": count},
                message=_("conversation.batch_archived"),
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
            删除对话（软删除）

            权限: agent_conversation:delete
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
            导出对话数据（JSON / Markdown）

            权限: agent_conversation:export
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


# 导出路由器
router = TenantConversationController.get_router()

__all__ = ["router", "TenantConversationController"]
