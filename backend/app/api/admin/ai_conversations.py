"""
平台端对话管理 API / Platform Conversation API

提供全企业对话列表和只读详情，用于审计和监控
Provides cross-tenant conversation list and read-only details for auditing and monitoring.
"""

from decimal import Decimal

from fastapi import Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.configs.service import PLATFORM_TENANT_ID
from app.core.base_controller import GlobalController
from app.core.deps import ActiveAdmin, DbSession, QueryParams
from app.core.i18n import _
from app.core.response import paginated, success
from app.enums.rbac import PermissionScope
from app.models.ai import AICallLog
from app.models.system.admin import Admin
from app.models.tenant.tenant import Tenant
from app.models.tenant.tenant_admin import TenantAdmin
from app.rbac.decorators import (
    MenuConfig,
    action_read,
    permission_resource,
)
from app.services.ai.conversation_service import ConversationService
from app.services.ai.monitoring_service import MonitoringService


def _safe_int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _safe_float(value) -> float:
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _resolve_conversation_usage(conv, usage: dict | None = None) -> tuple[int, float]:
    """
    Prefer the richer of conversation counters and call-log aggregates.
    优先使用对话统计与调用日志聚合中更可靠的一方。
    """
    conversation_tokens = _safe_int(getattr(conv, "token_count", 0))
    conversation_cost = _safe_float(getattr(conv, "cost", 0))
    if not usage:
        return conversation_tokens, conversation_cost

    return (
        max(conversation_tokens, _safe_int(usage.get("total_tokens"))),
        max(conversation_cost, _safe_float(usage.get("total_cost"))),
    )


def _build_admin_conversation_item(
    conv,
    tenant_map: dict[int, dict] | None = None,
    user_map: dict[str, dict] | None = None,
    usage_map: dict[int, dict] | None = None,
) -> dict:
    """从 ORM 对象构建管理端列表项字典 / Build admin list item dict from ORM object"""
    agent_name = None
    agent_avatar = None
    try:
        agent_obj = getattr(conv, "agent", None)
        if agent_obj is not None:
            agent_name = agent_obj.name
            agent_avatar = agent_obj.avatar
    except AttributeError:
        pass

    # 企业信息 / tenant info
    tenant_info = None
    if tenant_map and conv.tenant_id is not None:
        tenant_info = tenant_map.get(conv.tenant_id)

    # 用户信息 / user info
    user_info = None
    if user_map and conv.user_id is not None:
        key = f"{conv.tenant_id}:{conv.user_id}"
        user_info = user_map.get(key)

    token_count, cost = _resolve_conversation_usage(
        conv,
        usage_map.get(conv.id) if usage_map else None,
    )

    return {
        "id": conv.id,
        "tenant_id": conv.tenant_id,
        "agent_id": conv.agent_id,
        "user_id": conv.user_id,
        "title": conv.title,
        "status": conv.status,
        "token_count": token_count,
        "cost": cost,
        "agent_name": agent_name,
        "agent_avatar": agent_avatar,
        "tenant_name": tenant_info["name"] if tenant_info else None,
        "user_info": user_info,
        "created_at": conv.created_at,
        "updated_at": conv.updated_at,
    }


async def _batch_load_tenants(
    db: AsyncSession,
    tenant_ids: set[int],
) -> dict[int, dict]:
    """批量加载企业名称 / Batch load tenant names"""
    if not tenant_ids:
        return {}
    stmt = select(Tenant.id, Tenant.name, Tenant.code).where(
        Tenant.id.in_(tenant_ids),
        Tenant.is_deleted.is_(False),
    )
    result = await db.execute(stmt)
    return {row.id: {"name": row.name, "code": row.code} for row in result.all()}


async def _batch_load_users(
    db: AsyncSession,
    items: list,
) -> dict[str, dict]:
    """
    批量加载用户信息 / Batch load user info.
    tenant_id=PLATFORM_TENANT_ID → Admin 表 / Admin table，tenant_id>PLATFORM_TENANT_ID → TenantAdmin 表 / TenantAdmin table。
    返回 / Returns {'{tenant_id}:{user_id}': {username, nickname, avatar}} 映射 / mapping。
    """
    admin_ids: set[int] = set()
    tenant_admin_ids: set[int] = set()
    for conv in items:
        if conv.user_id is None:
            continue
        if conv.tenant_id == PLATFORM_TENANT_ID:
            admin_ids.add(conv.user_id)
        else:
            tenant_admin_ids.add(conv.user_id)

    user_map: dict[str, dict] = {}

    if admin_ids:
        stmt = select(
            Admin.id,
            Admin.username,
            Admin.nickname,
            Admin.avatar,
        ).where(Admin.id.in_(admin_ids), Admin.is_deleted.is_(False))
        result = await db.execute(stmt)
        for row in result.all():
            user_map[f"{PLATFORM_TENANT_ID}:{row.id}"] = {
                "username": row.username,
                "nickname": row.nickname,
                "avatar": row.avatar,
            }

    if tenant_admin_ids:
        stmt = select(
            TenantAdmin.id,
            TenantAdmin.tenant_id,
            TenantAdmin.username,
            TenantAdmin.nickname,
            TenantAdmin.avatar,
        ).where(
            TenantAdmin.id.in_(tenant_admin_ids),
            TenantAdmin.is_deleted.is_(False),
        )
        result = await db.execute(stmt)
        for row in result.all():
            user_map[f"{row.tenant_id}:{row.id}"] = {
                "username": row.username,
                "nickname": row.nickname,
                "avatar": row.avatar,
            }

    return user_map


async def _batch_load_conversation_usage(
    db: AsyncSession,
    conversation_ids: set[int],
) -> dict[int, dict]:
    """Batch load aggregated call-log usage by conversation / 批量加载按对话聚合的调用用量。"""
    if not conversation_ids:
        return {}

    stmt = (
        select(
            AICallLog.conversation_id,
            func.coalesce(func.sum(AICallLog.total_tokens), 0).label("total_tokens"),
            func.coalesce(func.sum(AICallLog.cost), 0).label("total_cost"),
        )
        .where(
            AICallLog.conversation_id.in_(conversation_ids),
            AICallLog.is_deleted.is_(False),
        )
        .group_by(AICallLog.conversation_id)
    )
    result = await db.execute(stmt)
    return {
        row.conversation_id: {
            "total_tokens": _safe_int(row.total_tokens),
            "total_cost": _safe_float(row.total_cost),
        }
        for row in result.all()
        if row.conversation_id is not None
    }


async def _load_single_user_info(
    db: AsyncSession,
    tenant_id: int,
    user_id: int | None,
) -> dict | None:
    """加载单个用户信息（用于详情页） / Load single user info (for detail page)"""
    if user_id is None:
        return None
    if tenant_id == PLATFORM_TENANT_ID:
        stmt = select(
            Admin.id,
            Admin.username,
            Admin.nickname,
            Admin.avatar,
        ).where(Admin.id == user_id, Admin.is_deleted.is_(False))
    else:
        stmt = select(
            TenantAdmin.id,
            TenantAdmin.username,
            TenantAdmin.nickname,
            TenantAdmin.avatar,
        ).where(TenantAdmin.id == user_id, TenantAdmin.is_deleted.is_(False))
    result = await db.execute(stmt)
    row = result.first()
    if not row:
        return None
    return {
        "id": row.id,
        "username": row.username,
        "nickname": row.nickname,
        "avatar": row.avatar,
    }


@permission_resource(
    resource="ai_conversation",
    name="menu.admin.ai_conversation",
    scope=PermissionScope.ADMIN,
    parent_resource="ai_quota_mgmt",
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
    平台端对话管理控制器 / Platform Conversation Management Controller

    全企业只读审计 / Cross-tenant read-only audit
    """

    prefix = "/ai/conversations"
    tags = [_("menu.tags.admin_ai_conversation")]

    def _register_routes(self) -> None:
        """注册路由 / Register routes"""
        router = self.router

        @router.get("", summary="全企业对话列表")
        @action_read("action.ai_conversation.list")
        async def list_conversations(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
            query: QueryParams,
            tenant_id: int | None = Query(
                None, description=_("api.param.tenant_id_filter")
            ),
        ):
            """
            获取全企业对话列表 / Get cross-tenant conversation list

            支持 tenant_id 筛选和 JSON:API 分页排序 / Supports tenant_id filtering and JSON:API pagination/sorting
            权限 / Permission: ai_conversation:list
            """
            _admin = admin
            monitoring = MonitoringService(db)
            result, total = await monitoring.list_conversations(
                monitoring.admin_scope(),
                query,
            )

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
            获取对话详情（只读审计） / Get conversation details (read-only audit)

            先从全局 Repo 查找对话取 tenant_id，再通过 Service 获取完整详情
            First find conversation from global Repo to get tenant_id, then get full details via Service
            权限 / Permission: ai_conversation:detail
            """
            _admin = admin
            monitoring = MonitoringService(db)
            detail = await monitoring.get_conversation_detail(
                monitoring.admin_scope(),
                conversation_id=conversation_id,
                message_skip=message_skip,
                message_limit=message_limit,
            )
            return success(data=detail)

        @router.get("/{conversation_id}/compact", summary="对话上下文压缩快照")
        @action_read("action.ai_conversation.detail")
        async def get_conversation_compact_snapshot(
            request: Request,
            db: DbSession,
            conversation_id: int,
            admin: ActiveAdmin,
        ):
            _admin = admin
            service, _ = await ConversationService.get_service_for_conversation(
                db,
                conversation_id,
            )
            snapshot = await service.get_context_compaction_snapshot(conversation_id)
            return success(data={"snapshot": snapshot})

        @router.get("/{conversation_id}/timeline", summary="对话时间线")
        @action_read("action.ai_conversation.detail")
        async def get_conversation_timeline(
            request: Request,
            db: DbSession,
            conversation_id: int,
            admin: ActiveAdmin,
        ):
            _admin = admin
            service, _ = await ConversationService.get_service_for_conversation(
                db,
                conversation_id,
            )
            timeline = await service.get_conversation_timeline(conversation_id)
            return success(data={"timeline": timeline})


# 导出路由器 / Export router
router = AdminAIConversationController.get_router()

__all__ = ["router", "AdminAIConversationController"]
