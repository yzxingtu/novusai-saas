"""
公告管理管理 API / Announcement management admin API.
"""

from fastapi import Request

from app.core.base_controller import GlobalController
from app.core.base_schema import PageResponse
from app.core.deps import ActiveAdmin, DbSession, QueryParams
from app.core.i18n import _
from app.core.response import success
from app.enums.rbac import PermissionScope
from app.exceptions import NotFoundException
from app.rbac.decorators import (
    MenuConfig,
    action_create,
    action_delete,
    action_read,
    action_update,
    auth_only,
    permission_resource,
)
from app.schemas.tenant.announcement import (
    AdminAnnouncementResponse,
    AnnouncementAnswerSubmit,
    AnnouncementCreate,
    AnnouncementDeliveryResponse,
    AnnouncementSubmitResult,
    AnnouncementUpdate,
    CurrentAnnouncementResponse,
    PendingAnnouncementResponse,
)
from app.services.tenant.announcement_service import AdminAnnouncementService


@permission_resource(
    resource="announcement",
    name="menu.admin.announcement",
    scope=PermissionScope.ADMIN,
    parent_resource="system_mgmt",
    menu=MenuConfig(
        icon="lucide:megaphone",
        path="/system/announcements",
        component="system/announcements/index",
        parent="system_mgmt",
        sort_order=42,
    ),
)
class AdminAnnouncementController(GlobalController):
    """公告管理管理控制器 / Announcement management admin controller."""

    prefix = "/announcements"
    tags = ["Announcement Management"]
    service_class = AdminAnnouncementService

    def _register_routes(self) -> None:
        router = self.router

        @router.get("/pending", summary=_("action.announcement.pending"))
        @auth_only
        async def list_pending(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
        ):
            service = AdminAnnouncementService(db)
            deliveries = await service.list_pending_for_user(current_admin.id)
            return success(
                data=[PendingAnnouncementResponse.from_delivery(i) for i in deliveries],
                message=_("common.success"),
            )

        @router.get("/{id}/mine", summary=_("action.announcement.mine"))
        @auth_only
        async def get_my_announcement(
            request: Request,
            db: DbSession,
            id: int,
            current_admin: ActiveAdmin,
        ):
            service = AdminAnnouncementService(db)
            delivery = await service.get_for_current_user(id, current_admin.id)
            return success(
                data=CurrentAnnouncementResponse.from_delivery(delivery),
                message=_("common.success"),
            )

        @router.get("/select", summary=_("action.announcement.select"))
        @action_read("action.announcement.select")
        async def select_items(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            search: str = "",
            page: int = 0,
            page_size: int = 20,
        ):
            service = AdminAnnouncementService(db)
            response = await service.get_select_options(
                search=search, page=page, page_size=page_size
            )
            return success(data=response, message=_("common.success"))

        @router.get("", summary=_("action.announcement.list"))
        @action_read("action.announcement.list")
        async def list_items(
            request: Request,
            db: DbSession,
            spec: QueryParams,
            current_admin: ActiveAdmin,
        ):
            service = AdminAnnouncementService(db)
            items, total = await service.query_list(spec, scope="admin")
            return success(
                data=PageResponse.create(
                    items=[AdminAnnouncementResponse.from_model(i) for i in items],
                    total=total,
                    page=spec.page,
                    page_size=spec.size,
                ),
                message=_("common.success"),
            )

        @router.get("/{id}", summary=_("action.announcement.detail"))
        @action_read("action.announcement.detail")
        async def get_item(
            request: Request,
            db: DbSession,
            id: int,
            current_admin: ActiveAdmin,
        ):
            service = AdminAnnouncementService(db)
            item = await service.get_by_id(id)
            if not item:
                raise NotFoundException(message=_("tenant.announcement.not_found"))
            return success(
                data=AdminAnnouncementResponse.from_model(item),
                message=_("common.success"),
            )

        @router.post("", summary=_("action.announcement.create"))
        @action_create("action.announcement.create")
        async def create_item(
            request: Request,
            db: DbSession,
            data: AnnouncementCreate,
            current_admin: ActiveAdmin,
        ):
            service = AdminAnnouncementService(db)
            item = await service.create(data.model_dump(exclude_none=True))
            await db.commit()
            return success(
                data=AdminAnnouncementResponse.from_model(item),
                message=_("tenant.announcement.created"),
            )

        @router.put("/{id}", summary=_("action.announcement.update"))
        @action_update("action.announcement.update")
        async def update_item(
            request: Request,
            db: DbSession,
            id: int,
            data: AnnouncementUpdate,
            current_admin: ActiveAdmin,
        ):
            service = AdminAnnouncementService(db)
            item = await service.update(id, data.model_dump(exclude_none=True))
            await db.commit()
            if not item:
                raise NotFoundException(message=_("tenant.announcement.not_found"))
            return success(
                data=AdminAnnouncementResponse.from_model(item),
                message=_("tenant.announcement.updated"),
            )

        @router.delete("/{id}", summary=_("action.announcement.delete"))
        @action_delete("action.announcement.delete")
        async def delete_item(
            request: Request,
            db: DbSession,
            id: int,
            current_admin: ActiveAdmin,
        ):
            service = AdminAnnouncementService(db)
            await service.delete(id)
            await db.commit()
            return success(message=_("common.deleted"))

        @router.post("/{id}/publish", summary=_("action.announcement.publish"))
        @action_update("action.announcement.publish")
        async def publish_item(
            request: Request,
            db: DbSession,
            id: int,
            current_admin: ActiveAdmin,
        ):
            service = AdminAnnouncementService(db)
            item = await service.publish(id, current_admin.id)
            await db.commit()
            return success(
                data=AdminAnnouncementResponse.from_model(item),
                message=_("tenant.announcement.published"),
            )

        @router.get("/{id}/responses", summary=_("action.announcement.responses"))
        @action_read("action.announcement.responses")
        async def list_responses(
            request: Request,
            db: DbSession,
            id: int,
            current_admin: ActiveAdmin,
        ):
            service = AdminAnnouncementService(db)
            deliveries = await service.list_responses(id)
            return success(
                data=[AnnouncementDeliveryResponse.from_delivery(i) for i in deliveries],
                message=_("common.success"),
            )

        @router.post("/{id}/response", summary=_("action.announcement.response"))
        @auth_only
        async def submit_response(
            request: Request,
            db: DbSession,
            id: int,
            data: AnnouncementAnswerSubmit,
            current_admin: ActiveAdmin,
        ):
            service = AdminAnnouncementService(db)
            delivery = await service.submit_response(
                id,
                current_admin.id,
                data.answers,
            )
            await db.commit()
            return success(
                data=AnnouncementSubmitResult.from_delivery(delivery),
                message=_("tenant.announcement.submitted"),
            )

        @router.post("/{id}/read", summary=_("action.announcement.read"))
        @auth_only
        async def mark_read(
            request: Request,
            db: DbSession,
            id: int,
            current_admin: ActiveAdmin,
        ):
            service = AdminAnnouncementService(db)
            delivery = await service.mark_read(id, current_admin.id)
            await db.commit()
            return success(
                data=AnnouncementSubmitResult.from_delivery(delivery),
                message=_("tenant.announcement.read"),
            )


router = AdminAnnouncementController.get_router()

__all__ = ["router", "AdminAnnouncementController"]
