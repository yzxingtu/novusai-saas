"""
平台管理端通知 API / Platform Admin Notification API

提供管理员通知列表、未读计数、已读、全部已读、删除接口。
Provides admin notification list, unread count, mark read, mark all read, and delete endpoints.
"""

from fastapi import APIRouter, Query

from app.core.deps import ActiveAdmin, DbSession
from app.core.i18n import _
from app.core.response import success
from app.exceptions import NotFoundException
from app.rbac.decorators import auth_only
from app.services.common.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["通知管理"])


@router.get("", summary="通知列表")
@auth_only
async def list_notifications(
    db: DbSession,
    admin: ActiveAdmin,
    category: str = Query("", description="分类筛选"),
    is_read: str = Query("", description="已读筛选: true/false/空"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """获取当前管理员的通知列表（分页） / Get current admin's notification list (paginated)"""
    service = NotificationService(db)

    read_filter = None
    if is_read == "true":
        read_filter = True
    elif is_read == "false":
        read_filter = False

    items, total = await service.get_notifications(
        user_type="admin",
        user_id=admin.id,
        category=category or None,
        is_read=read_filter,
        page=page,
        page_size=page_size,
    )

    return success(data={
        "items": [
            {
                "id": n.id,
                "template_code": n.template_code,
                "category": n.category,
                "title": n.title,
                "body": n.body,
                "data": n.data,
                "link": n.link,
                "priority": n.priority,
                "is_read": n.is_read,
                "read_at": n.read_at.isoformat() if n.read_at else None,
                "created_at": n.created_at.isoformat() if n.created_at else None,
            }
            for n in items
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    })


@router.get("/unread-count", summary="未读通知数量")
@auth_only
async def get_unread_count(
    db: DbSession,
    admin: ActiveAdmin,
):
    """获取当前管理员的未读通知数量 / Get current admin's unread notification count"""
    service = NotificationService(db)
    count = await service.get_unread_count("admin", admin.id)
    return success(data={"count": count})


@router.put("/{notification_id}/read", summary="标记已读")
@auth_only
async def mark_read(
    db: DbSession,
    admin: ActiveAdmin,
    notification_id: int,
):
    """标记单条通知已读 / Mark single notification as read"""
    service = NotificationService(db)
    found = await service.mark_read(notification_id, "admin", admin.id)
    if not found:
        raise NotFoundException(message=_("common.not_found"))
    return success()


@router.put("/read-all", summary="全部已读")
@auth_only
async def mark_all_read(
    db: DbSession,
    admin: ActiveAdmin,
    category: str = Query("", description="可选分类筛选"),
):
    """标记全部通知已读 / Mark all notifications as read"""
    service = NotificationService(db)
    count = await service.mark_all_read("admin", admin.id, category or None)
    return success(data={"count": count})


@router.delete("/{notification_id}", summary="删除通知")
@auth_only
async def delete_notification(
    db: DbSession,
    admin: ActiveAdmin,
    notification_id: int,
):
    """删除单条通知（软删除） / Delete single notification (soft delete)"""
    service = NotificationService(db)
    found = await service.delete_notification(notification_id, "admin", admin.id)
    if not found:
        raise NotFoundException(message=_("common.not_found"))
    return success()
