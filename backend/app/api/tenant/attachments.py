from fastapi import Query
from fastapi.responses import RedirectResponse

from app.core.base_controller import TenantController
from app.core.deps import DbSession, ActiveTenantAdmin
from app.core.i18n import _
from app.core.response import success
from app.enums.rbac import PermissionScope
from app.rbac.decorators import (
    permission_resource,
    MenuConfig,
    action_read,
)
from app.schemas.tenant.attachment import AttachmentAccessUrlResponse
from app.services.tenant.attachment_download_service import AttachmentDownloadService


@permission_resource(
    resource="attachment",
    name="menu.tenant.attachment",
    scope=PermissionScope.TENANT,
    menu=MenuConfig(hidden=True),
)
class TenantAttachmentController(TenantController):
    prefix = "/attachments"
    tags = ["附件"]

    def _register_routes(self) -> None:
        router = self.router

        @router.get("/{attachment_id}/download-url", summary="获取下载链接")
        @action_read("action.attachment.download_url")
        async def get_download_url(
            attachment_id: int,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
            expires: int = Query(3600, ge=60, le=86400),
        ):
            service = AttachmentDownloadService(db, current_admin.tenant_id)
            attachment = await service.get_attachment(attachment_id)
            data = await service.build_access_url(
                attachment, expires=expires, preview=False
            )
            return success(data=AttachmentAccessUrlResponse(**data), message=_("common.success"))

        @router.get("/{attachment_id}/preview-url", summary="获取预览链接")
        @action_read("action.attachment.preview_url")
        async def get_preview_url(
            attachment_id: int,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
            expires: int = Query(3600, ge=60, le=86400),
        ):
            service = AttachmentDownloadService(db, current_admin.tenant_id)
            attachment = await service.get_attachment(attachment_id)
            data = await service.build_access_url(
                attachment, expires=expires, preview=True
            )
            return success(data=AttachmentAccessUrlResponse(**data), message=_("common.success"))

        @router.get("/{attachment_id}/download", summary="下载附件")
        @action_read("action.attachment.download")
        async def download_attachment(
            attachment_id: int,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
            expires: int = Query(3600, ge=60, le=86400),
        ):
            service = AttachmentDownloadService(db, current_admin.tenant_id)
            attachment = await service.get_attachment(attachment_id)
            if attachment.driver == "local":
                await service.record_download(attachment)
                return await service.get_download_response(attachment, preview=False)
            url = await service.get_redirect_url(
                attachment, expires=expires, preview=False
            )
            return RedirectResponse(url=url)

        @router.get("/{attachment_id}/preview", summary="预览附件")
        @action_read("action.attachment.preview")
        async def preview_attachment(
            attachment_id: int,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
            expires: int = Query(3600, ge=60, le=86400),
        ):
            service = AttachmentDownloadService(db, current_admin.tenant_id)
            attachment = await service.get_attachment(attachment_id)
            if attachment.driver == "local":
                await service.record_download(attachment)
                return await service.get_download_response(attachment, preview=True)
            url = await service.get_redirect_url(
                attachment, expires=expires, preview=True
            )
            return RedirectResponse(url=url)


router = TenantAttachmentController.get_router()

__all__ = ["router", "TenantAttachmentController"]
