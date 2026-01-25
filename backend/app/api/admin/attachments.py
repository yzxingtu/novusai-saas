"""
平台端附件管理 API

提供跨租户的附件管理接口（平台管理员专用）
"""

from fastapi import Query, Request
from fastapi.responses import RedirectResponse

from app.core.base_controller import GlobalController
from app.core.base_schema import PageResponse
from app.core.deps import DbSession, QueryParams, ActiveAdmin
from app.core.i18n import _
from app.core.response import success
from app.enums.rbac import PermissionScope
from app.exceptions import NotFoundException
from app.rbac.decorators import (
    permission_resource,
    MenuConfig,
    action_read,
    action_delete,
)
from app.schemas.tenant.attachment import (
    AttachmentAccessUrlResponse,
    AttachmentResponse,
    AttachmentListItem,
)
from app.services.system.attachment_service import AdminAttachmentService
from app.services.tenant.attachment_download_service import AttachmentDownloadService


@permission_resource(
    resource="attachment",
    name="menu.admin.attachment",
    scope=PermissionScope.ADMIN,
    menu=MenuConfig(
        icon="lucide:paperclip",
        path="/system/attachments",
        component="admin/system/attachments/index",
        parent="system_mgmt",
        sort_order=50,
    ),
)
class AdminAttachmentController(GlobalController):
    """
    平台端附件管理控制器
    
    提供跨租户的附件管理接口
    """
    
    prefix = "/attachments"
    tags = ["附件管理"]

    def _register_routes(self) -> None:
        router = self.router

        # ========== 附件管理接口 ==========

        @router.get("/select", summary="获取附件下拉选项")
        @action_read("action.attachment.select")
        async def select_attachments(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            search: str = Query("", description="搜索关键词"),
            tenant_id: int | None = Query(None, description="租户 ID"),
            page: int = Query(0, ge=0, description="页码（0=不分页，>=1=分页）"),
            page_size: int = Query(20, ge=1, le=100, description="每页数量"),
        ):
            """
            获取附件下拉选项
            
            用于从现有附件中选择文件
            
            权限: attachment:select
            """
            service = AdminAttachmentService(db)
            filters = {}
            if tenant_id is not None:
                filters["tenant_id"] = tenant_id
            response = await service.get_select_options(
                search=search,
                limit=50,
                page=page,
                page_size=page_size,
                **filters,
            )
            return success(data=response, message=_("common.success"))

        @router.get("/stats", summary="获取附件统计")
        @action_read("action.attachment.stats")
        async def get_attachment_stats(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            tenant_id: int | None = Query(None, description="租户 ID"),
        ):
            """
            获取附件存储统计
            
            - 不传 tenant_id: 统计所有租户
            - 传入 tenant_id: 统计指定租户
            
            权限: attachment:stats
            """
            service = AdminAttachmentService(db)
            stats = await service.get_storage_stats(tenant_id)
            return success(data=stats, message=_("common.success"))

        @router.get("/stats/by-tenant", summary="获取按租户分组的附件统计")
        @action_read("action.attachment.stats_by_tenant")
        async def get_attachment_stats_by_tenant(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
        ):
            """
            获取按租户分组的存储统计
            
            返回各租户的附件数量和存储用量
            
            权限: attachment:stats_by_tenant
            """
            service = AdminAttachmentService(db)
            stats = await service.get_storage_stats_by_tenant()
            return success(data=stats, message=_("common.success"))

        @router.get("", summary="获取附件列表")
        @action_read("action.attachment.list")
        async def list_attachments(
            request: Request,
            db: DbSession,
            spec: QueryParams,
            current_admin: ActiveAdmin,
        ):
            """
            获取附件列表
            
            - 支持通用筛选: filter[field][op]=value
            - 支持按租户筛选: filter[tenant_id][eq]=1
            - 支持排序: sort=-created_at,name
            - 支持分页: page[number]=1&page[size]=20
            
            权限: attachment:list
            """
            service = AdminAttachmentService(db)
            items, total = await service.query_list(spec, scope="admin")
            return success(
                data=PageResponse.create(
                    items=[AttachmentListItem.model_validate(item, from_attributes=True) for item in items],
                    total=total,
                    page=spec.page,
                    page_size=spec.size,
                ),
                message=_("common.success"),
            )

        @router.get("/{attachment_id}", summary="获取附件详情")
        @action_read("action.attachment.detail")
        async def get_attachment(
            request: Request,
            attachment_id: int,
            db: DbSession,
            current_admin: ActiveAdmin,
        ):
            """
            获取附件详情
            
            权限: attachment:detail
            """
            service = AdminAttachmentService(db)
            attachment = await service.get_by_id(attachment_id)
            if not attachment:
                raise NotFoundException(message=_("error.common.not_found"))
            return success(
                data=AttachmentResponse.model_validate(attachment, from_attributes=True),
                message=_("common.success"),
            )

        @router.delete("/{attachment_id}", summary="删除附件")
        @action_delete("action.attachment.delete")
        async def delete_attachment(
            request: Request,
            attachment_id: int,
            db: DbSession,
            current_admin: ActiveAdmin,
        ):
            """
            删除附件（软删除）
            
            权限: attachment:delete
            """
            service = AdminAttachmentService(db)
            await service.soft_delete(attachment_id)
            return success(message=_("common.deleted"))

        # ========== 附件访问接口 ==========

        @router.get("/{attachment_id}/download-url", summary="获取下载链接")
        @action_read("action.attachment.download_url")
        async def get_download_url(
            attachment_id: int,
            db: DbSession,
            current_admin: ActiveAdmin,
            expires: int = Query(3600, ge=60, le=86400),
        ):
            """
            获取附件下载 URL
            
            权限: attachment:download_url
            """
            # 平台端不做租户隔离，传入 None
            service = AttachmentDownloadService(db, tenant_id=None)
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
            current_admin: ActiveAdmin,
            expires: int = Query(3600, ge=60, le=86400),
        ):
            """
            获取附件预览 URL
            
            权限: attachment:preview_url
            """
            service = AttachmentDownloadService(db, tenant_id=None)
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
            current_admin: ActiveAdmin,
            expires: int = Query(3600, ge=60, le=86400),
        ):
            """
            下载附件
            
            权限: attachment:download
            """
            service = AttachmentDownloadService(db, tenant_id=None)
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
            current_admin: ActiveAdmin,
            expires: int = Query(3600, ge=60, le=86400),
        ):
            """
            预览附件
            
            权限: attachment:preview
            """
            service = AttachmentDownloadService(db, tenant_id=None)
            attachment = await service.get_attachment(attachment_id)
            if attachment.driver == "local":
                await service.record_download(attachment)
                return await service.get_download_response(attachment, preview=True)
            url = await service.get_redirect_url(
                attachment, expires=expires, preview=True
            )
            return RedirectResponse(url=url)


router = AdminAttachmentController.get_router()

__all__ = ["router", "AdminAttachmentController"]
