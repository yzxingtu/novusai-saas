from fastapi import Query, Request, UploadFile, File, Form
from fastapi.responses import RedirectResponse

from app.core.base_controller import TenantController
from app.core.base_schema import PageResponse
from app.core.deps import DbSession, QueryParams, ActiveTenantAdmin
from app.core.i18n import _
from app.core.response import success
from app.enums.attachment import AttachmentSource, AttachmentVisibility
from app.enums.rbac import PermissionScope
from app.exceptions import NotFoundException
from app.rbac.decorators import (
    permission_resource,
    MenuConfig,
    action_read,
    action_create,
    action_delete,
)
from app.schemas.tenant.attachment import (
    AttachmentAccessUrlResponse,
    AttachmentResponse,
    AttachmentListItem,
    TenantStorageQuotaResponse,
    AttachmentUploadResponse,
    ChunkUploadInitRequest,
    ChunkUploadInitResponse,
    ChunkUploadProgressResponse,
)
from app.services.tenant.attachment_service import AttachmentService
from app.services.tenant.attachment_download_service import AttachmentDownloadService
from app.services.common import StorageQuotaService


@permission_resource(
    resource="attachment",
    name="menu.tenant.attachment",
    scope=PermissionScope.TENANT,
    menu=MenuConfig(
        icon="lucide:paperclip",
        path="/system/attachments",
        component="tenant/system/attachments/index",
        parent="system_mgmt",
        sort_order=50,
    ),
)
class TenantAttachmentController(TenantController):
    prefix = "/attachments"
    tags = ["附件管理"]

    def _register_routes(self) -> None:
        router = self.router

        # ========== 上传接口 ==========

        @router.post("/upload", summary="上传附件")
        @action_create("action.attachment.upload")
        async def upload_attachment(
            request: Request,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
            file: UploadFile = File(..., description="上传的文件"),
            visibility: str = Form("private", description="可见性 (private/public)"),
            business_type: str | None = Form(None, description="业务类型"),
            business_id: int | None = Form(None, description="业务 ID"),
        ):
            """
            上传附件（普通上传）
            
            适用于小文件上传，大文件建议使用分片上传接口
            
            权限: attachment:upload
            """
            service = AttachmentService(db, current_admin.tenant_id)
            result = await service.upload_file(
                content=file.file,
                filename=file.filename or "unnamed",
                file_size=file.size,
                mime_type=file.content_type,
                visibility=AttachmentVisibility(visibility),
                source=AttachmentSource.TENANT_ADMIN,
                uploader_id=current_admin.id,
                business_type=business_type,
                business_id=business_id,
            )
            return success(
                data=AttachmentUploadResponse(
                    attachment=AttachmentResponse.model_validate(
                        result["attachment"], from_attributes=True
                    ),
                    url=result["url"],
                    used_bytes=result["used_bytes"],
                ),
                message=_("文件上传成功"),
            )

        @router.post("/chunk/init", summary="初始化分片上传")
        @action_create("action.attachment.chunk_init")
        async def init_chunk_upload(
            request: Request,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
            body: ChunkUploadInitRequest,
        ):
            """
            初始化分片上传会话
            
            返回 upload_id 和分片信息，用于后续分片上传
            
            权限: attachment:chunk_init
            """
            service = AttachmentService(db, current_admin.tenant_id)
            result = await service.start_chunk_upload(
                filename=body.filename,
                total_size=body.total_size,
                chunk_size=body.chunk_size,
                mime_type=body.mime_type,
                visibility=AttachmentVisibility(body.visibility),
                source=AttachmentSource.TENANT_ADMIN,
                uploader_id=current_admin.id,
                business_type=body.business_type,
                business_id=body.business_id,
            )
            return success(
                data=ChunkUploadInitResponse(**result),
                message=_("common.success"),
            )

        @router.post("/chunk/{upload_id}", summary="上传分片")
        @action_create("action.attachment.chunk_upload")
        async def upload_chunk(
            request: Request,
            upload_id: str,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
            chunk_index: int = Form(..., ge=0, description="分片索引（从 0 开始）"),
            file: UploadFile = File(..., description="分片数据"),
        ):
            """
            上传分片数据
            
            权限: attachment:chunk_upload
            """
            service = AttachmentService(db, current_admin.tenant_id)
            result = await service.upload_chunk(
                upload_id=upload_id,
                chunk_index=chunk_index,
                content=file.file,
            )
            return success(
                data=ChunkUploadProgressResponse(**result),
                message=_("common.success"),
            )

        @router.post("/chunk/{upload_id}/complete", summary="完成分片上传")
        @action_create("action.attachment.chunk_complete")
        async def complete_chunk_upload(
            request: Request,
            upload_id: str,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
        ):
            """
            完成分片上传并合并文件
            
            所有分片上传完成后调用此接口
            
            权限: attachment:chunk_complete
            """
            service = AttachmentService(db, current_admin.tenant_id)
            result = await service.complete_chunk_upload(upload_id)
            return success(
                data=AttachmentUploadResponse(
                    attachment=AttachmentResponse.model_validate(
                        result["attachment"], from_attributes=True
                    ),
                    url=result["url"],
                    used_bytes=result["used_bytes"],
                ),
                message=_("file.upload_success"),
            )

        @router.get("/chunk/{upload_id}/status", summary="获取分片上传进度")
        @action_read("action.attachment.chunk_status")
        async def get_chunk_upload_status(
            request: Request,
            upload_id: str,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
        ):
            """
            获取分片上传进度
            
            用于断点续传场景
            
            权限: attachment:chunk_status
            """
            service = AttachmentService(db, current_admin.tenant_id)
            result = await service.get_upload_status(upload_id)
            return success(
                data=ChunkUploadProgressResponse(**result),
                message=_("common.success"),
            )

        @router.delete("/chunk/{upload_id}", summary="取消分片上传")
        @action_delete("action.attachment.chunk_abort")
        async def abort_chunk_upload(
            request: Request,
            upload_id: str,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
        ):
            """
            取消分片上传并清理临时文件
            
            权限: attachment:chunk_abort
            """
            service = AttachmentService(db, current_admin.tenant_id)
            await service.abort_upload(upload_id)
            return success(message=_("common.success"))

        # ========== 附件管理接口 ==========

        @router.get("/storage-quota", summary="获取存储配额")
        @action_read("action.attachment.storage_quota")
        async def get_storage_quota(
            request: Request,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
        ):
            """
            获取当前租户存储配额使用情况
            
            权限: attachment:storage_quota
            """
            quota_service = StorageQuotaService(db)
            stats = await quota_service.get_tenant_storage_stats(current_admin.tenant_id)
            
            return success(
                data=TenantStorageQuotaResponse(
                    used_bytes=stats["used_bytes"],
                    limit_bytes=stats["limit_bytes"],
                    limit_gb=stats["limit_gb"],
                    remaining_bytes=stats["remaining_bytes"],
                    usage_percent=stats["usage_percent"],
                    total_count=stats["file_count"],
                    max_file_size_mb=stats["max_file_size_mb"],
                    unlimited=stats["unlimited"],
                ),
                message=_("common.success"),
            )

        @router.get("/select", summary="获取附件下拉选项")
        @action_read("action.attachment.select")
        async def select_attachments(
            request: Request,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
            search: str = Query("", description="搜索关键词"),
            page: int = Query(0, ge=0, description="页码（0=不分页，>=1=分页）"),
            page_size: int = Query(20, ge=1, le=100, description="每页数量"),
        ):
            """
            获取附件下拉选项
            
            用于从现有附件中选择文件
            
            权限: attachment:select
            """
            service = AttachmentService(db, current_admin.tenant_id)
            response = await service.get_select_options(
                search=search,
                limit=50,
                page=page,
                page_size=page_size,
            )
            return success(data=response, message=_("common.success"))

        @router.get("", summary="获取附件列表")
        @action_read("action.attachment.list")
        async def list_attachments(
            request: Request,
            db: DbSession,
            spec: QueryParams,
            current_admin: ActiveTenantAdmin,
        ):
            """
            获取附件列表
            
            - 支持通用筛选: filter[field][op]=value
            - 支持排序: sort=-created_at,name
            - 支持分页: page[number]=1&page[size]=20
            
            权限: attachment:list
            """
            service = AttachmentService(db, current_admin.tenant_id)
            items, total = await service.query_list(spec, scope="tenant")
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
            current_admin: ActiveTenantAdmin,
        ):
            """
            获取附件详情
            
            权限: attachment:detail
            """
            service = AttachmentService(db, current_admin.tenant_id)
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
            current_admin: ActiveTenantAdmin,
        ):
            """
            删除附件（软删除）
            
            权限: attachment:delete
            """
            service = AttachmentService(db, current_admin.tenant_id)
            await service.soft_delete(attachment_id)
            return success(message=_("common.deleted"))

        # ========== 附件访问接口 ==========

        @router.get("/{attachment_id}/download-url", summary="获取下载链接")
        @action_read("action.attachment.download_url")
        async def get_download_url(
            attachment_id: int,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
            expires: int = Query(3600, ge=60, le=86400),
        ):
            """
            获取附件下载 URL
            
            权限: attachment:download_url
            """
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
            """
            获取附件预览 URL
            
            权限: attachment:preview_url
            """
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
            """
            下载附件
            
            权限: attachment:download
            """
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
            """
            预览附件
            
            权限: attachment:preview
            """
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
