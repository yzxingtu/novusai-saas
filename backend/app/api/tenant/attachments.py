from fastapi import File, Form, Query, Request, UploadFile
from fastapi.responses import RedirectResponse

from app.configs.service import ConfigService
from app.core.base_controller import TenantController
from app.core.base_schema import PageResponse
from app.core.deps import ActiveTenantAdmin, DbSession, QueryParams
from app.core.i18n import _
from app.core.response import build_public_error_text, deleted, success
from app.enums.attachment import AttachmentSource, AttachmentVisibility
from app.enums.rbac import PermissionScope
from app.exceptions import NotFoundException
from app.rbac.decorators import (
    MenuConfig,
    action_create,
    action_delete,
    action_read,
    permission_resource,
)
from app.schemas.tenant.attachment import (
    AttachmentAccessUrlResponse,
    AttachmentPreflightRequest,
    AttachmentSafeListItem,
    AttachmentSafePreflightResponse,
    AttachmentSafeResponse,
    AttachmentSafeUploadResponse,
    BatchSafeUploadItem,
    BatchSafeUploadResponse,
    ChunkUploadInitRequest,
    ChunkUploadInitResponse,
    ChunkUploadProgressResponse,
    TenantStorageQuotaResponse,
)
from app.services.common import StorageQuotaService
from app.services.tenant.attachment_download_service import AttachmentDownloadService
from app.services.tenant.attachment_service import AttachmentService


def _with_preview_url(data: dict, tenant_id: int) -> dict:
    """为序列化后的附件字典注入 preview_url / Inject preview_url into serialized attachment dict."""
    data["preview_url"] = AttachmentDownloadService.build_preview_url(
        attachment_id=data["id"],
        tenant_id=tenant_id,
        visibility=data.get("visibility", "private"),
    )
    return data


@permission_resource(
    resource="attachment",
    name="menu.tenant.attachment",
    scope=PermissionScope.TENANT,
    parent_resource="system_mgmt",
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
    tags = ["Attachment Management"]

    def _register_routes(self) -> None:
        router = self.router

        # ========== 上传规则 / Upload Rules ==========

        @router.get("/upload-rules", summary="获取上传规则")
        @action_read("action.attachment.upload_rules")
        async def get_upload_rules(
            request: Request,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
        ):
            """
            获取企业上传规则（扩展名白名单、黑名单、大小限制） / Get tenant upload rules (extension whitelist, blacklist, size limits)

            优先使用企业配置，留空则回退平台配置。
            Uses tenant config first, falls back to platform config if empty.

            权限 / Permission: attachment:upload_rules
            """
            from app.configs.service import ConfigService
            config_service = ConfigService(db)
            tid = current_admin.tenant_id

            tenant_allowed = await config_service.get_tenant_config(
                tid, "tenant_storage_allowed_extensions", default=""
            )
            tenant_denied = await config_service.get_tenant_config(
                tid, "tenant_storage_denied_extensions", default=""
            )

            if not tenant_allowed:
                tenant_allowed = await config_service.get_platform_config(
                    "platform_storage_allowed_extensions", default=""
                )
            if not tenant_denied:
                tenant_denied = await config_service.get_platform_config(
                    "platform_storage_denied_extensions", default=""
                )

            max_size = await config_service.get_platform_config(
                "platform_storage_max_file_size_mb", default=100
            )

            return success(data={
                "allowed_extensions": str(tenant_allowed) if tenant_allowed else "",
                "denied_extensions": str(tenant_denied) if tenant_denied else "",
                "max_file_size_mb": int(max_size) if max_size else 100,
            })

        # ========== 预检接口（秒传） / Preflight (Fast Upload) ==========

        @router.post("/preflight", summary="预检文件是否已存在（秒传）")
        @action_create("action.attachment.upload")
        async def preflight_check(
            request: Request,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
            body: AttachmentPreflightRequest,
        ):
            """
            预检文件是否已存在 / Preflight check if file already exists

            前端计算文件 SHA-256 哈希后调用此接口，如果服务端已有相同文件，
            则直接返回已有附件信息（秒传），无需再次上传文件。
            Frontend computes file SHA-256 hash then calls this endpoint. If server
            already has the same file, returns existing attachment info (fast upload).

            hash 格式 / hash format: sha256:{hex_digest}

            权限 / Permission: attachment:upload
            """
            raw_hash = body.hash
            if raw_hash.startswith("sha256:"):
                raw_hash = raw_hash[7:]

            service = AttachmentService(db, current_admin.tenant_id)
            result = await service.preflight_check(
                file_hash=raw_hash,
                filename=body.filename,
                size=body.size,
                visibility=AttachmentVisibility(body.visibility) if body.visibility else AttachmentVisibility.PRIVATE,
            )
            resp = AttachmentSafePreflightResponse(
                exists=result["exists"],
                attachment=(
                    AttachmentSafeResponse.model_validate(result["attachment"], from_attributes=True)
                    if result["attachment"]
                    else None
                ),
                url=result["url"],
                used_bytes=result["used_bytes"],
            )
            return success(data=resp, message=_("common.success"))

        # ========== 上传接口 / Upload Endpoints ==========

        @router.post("/upload", summary="上传附件")
        @action_create("action.attachment.upload")
        async def upload_attachment(
            request: Request,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
            file: UploadFile = File(..., description=_("api.param.file")),
            visibility: str = Form("", description=_("api.param.visibility")),
            business_type: str | None = Form(None, description=_("api.param.business_type")),
            business_id: int | None = Form(None, description=_("api.param.business_id")),
        ):
            """
            上传附件（普通上传） / Upload attachment (standard upload)

            适用于小文件上传，大文件建议使用分片上传接口
            Suitable for small files, large files should use chunked upload endpoint

            权限 / Permission: attachment:upload
            """
            # 未指定 visibility 时使用平台配置的默认值 / Use platform default when visibility not specified
            if not visibility:
                config_svc = ConfigService(db)
                visibility = await config_svc.get_platform_config(
                    "platform_storage_default_visibility", default="private"
                )
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
                data=AttachmentSafeUploadResponse(
                    attachment=AttachmentSafeResponse.model_validate(
                        result["attachment"], from_attributes=True
                    ),
                    url=result["url"],
                    used_bytes=result["used_bytes"],
                ),
                message=_("file.upload_success"),
            )

        @router.post("/batch-upload", summary="批量上传附件")
        @action_create("action.attachment.upload")
        async def batch_upload_attachments(
            request: Request,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
            files: list[UploadFile] = File(..., description=_("api.param.files")),
            visibility: str = Form("", description=_("api.param.visibility")),
            business_type: str | None = Form(None, description=_("api.param.business_type")),
            business_id: int | None = Form(None, description=_("api.param.business_id")),
        ):
            """
            批量上传附件（普通上传，每文件独立处理） / Batch upload attachments (standard upload, each file processed independently)

            - 最多一次上传 20 个文件 / Max 20 files per upload
            - 单个文件失败不影响其他文件 / Single file failure does not affect others
            - 返回每个文件的成功/失败状态 / Returns success/failure status for each file

            权限 / Permission: attachment:upload
            """
            if len(files) > 20:
                files = files[:20]
            if not visibility:
                config_svc = ConfigService(db)
                visibility = await config_svc.get_platform_config(
                    "platform_storage_default_visibility", default="private"
                )
            service = AttachmentService(db, current_admin.tenant_id)
            items: list[BatchSafeUploadItem] = []
            for f in files:
                try:
                    result = await service.upload_file(
                        content=f.file,
                        filename=f.filename or "unnamed",
                        file_size=f.size,
                        mime_type=f.content_type,
                        visibility=AttachmentVisibility(visibility),
                        source=AttachmentSource.TENANT_ADMIN,
                        uploader_id=current_admin.id,
                        business_type=business_type,
                        business_id=business_id,
                    )
                    items.append(BatchSafeUploadItem(
                        filename=f.filename or "unnamed",
                        success=True,
                        attachment=AttachmentSafeResponse.model_validate(
                            result["attachment"], from_attributes=True
                        ),
                        url=result["url"],
                    ))
                except Exception as exc:
                    items.append(BatchSafeUploadItem(
                        filename=f.filename or "unnamed",
                        success=False,
                        error=build_public_error_text(
                            exc=exc,
                            message=_("common.server_error"),
                        ),
                    ))
            success_count = sum(1 for i in items if i.success)
            used_bytes = await service.repo.sum_size()
            return success(
                data=BatchSafeUploadResponse(
                    items=items,
                    success_count=success_count,
                    failure_count=len(items) - success_count,
                    used_bytes=used_bytes,
                ),
                message=_(
                    "file.upload_success"
                    if success_count == len(items)
                    else "file.partial_upload_success"
                ),
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
            初始化分片上传会话 / Initialize chunked upload session

            返回 upload_id 和分片信息，用于后续分片上传
            Returns upload_id and chunk info for subsequent chunk uploads

            权限 / Permission: attachment:chunk_init
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
            chunk_index: int = Form(..., ge=0, description=_("api.param.chunk_index")),
            file: UploadFile = File(..., description=_("api.param.chunk_data")),
        ):
            """
            上传分片数据 / Upload chunk data

            权限 / Permission: attachment:chunk_upload
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
            完成分片上传并合并文件 / Complete chunked upload and merge file

            所有分片上传完成后调用此接口
            Call this endpoint after all chunks are uploaded

            权限 / Permission: attachment:chunk_complete
            """
            service = AttachmentService(db, current_admin.tenant_id)
            result = await service.complete_chunk_upload(upload_id)
            return success(
                data=AttachmentSafeUploadResponse(
                    attachment=AttachmentSafeResponse.model_validate(
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
            获取分片上传进度 / Get chunked upload progress

            用于断点续传场景
            Used for resumable upload scenarios

            权限 / Permission: attachment:chunk_status
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
            取消分片上传并清理临时文件 / Cancel chunked upload and clean up temp files

            权限 / Permission: attachment:chunk_abort
            """
            service = AttachmentService(db, current_admin.tenant_id)
            await service.abort_upload(upload_id)
            return success(message=_("common.success"))

        # ========== 附件管理接口 / Attachment Management Endpoints ==========

        @router.get("/storage-quota", summary="获取存储配额")
        @action_read("action.attachment.storage_quota")
        async def get_storage_quota(
            request: Request,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
        ):
            """
            获取当前企业存储配额使用情况 / Get current tenant storage quota usage

            权限 / Permission: attachment:storage_quota
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
            search: str = Query("", description=_("api.param.search")),
            page: int = Query(0, ge=0, description=_("api.param.page")),
            page_size: int = Query(20, ge=1, le=100, description=_("api.param.page_size")),
        ):
            """
            获取附件下拉选项 / Get attachment dropdown options

            用于从现有附件中选择文件
            Used to select files from existing attachments

            权限 / Permission: attachment:select
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
            获取附件列表 / Get attachment list

            - 支持通用筛选 / Supports filtering: filter[field][op]=value
            - 支持排序 / Supports sorting: sort=-created_at,name
            - 支持分页 / Supports pagination: page[number]=1&page[size]=20

            权限 / Permission: attachment:list
            """
            service = AttachmentService(db, current_admin.tenant_id)
            items, total = await service.query_list(spec, scope="tenant")
            serialized = [
                _with_preview_url(
                    AttachmentSafeListItem.model_validate(item, from_attributes=True).model_dump(),
                    tenant_id=current_admin.tenant_id,
                )
                for item in items
            ]
            return success(
                data=PageResponse.create(
                    items=serialized,
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
            获取附件详情 / Get attachment details

            权限 / Permission: attachment:detail
            """
            service = AttachmentService(db, current_admin.tenant_id)
            attachment = await service.get_by_id(attachment_id)
            if not attachment:
                raise NotFoundException(message=_("error.common.not_found"))
            data = _with_preview_url(
                AttachmentSafeResponse.model_validate(attachment, from_attributes=True).model_dump(),
                tenant_id=current_admin.tenant_id,
            )
            return success(
                data=data,
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
            删除附件（软删除 + 物理文件删除 + 依赖检查） / Delete attachment (soft delete + physical file removal + dependency check)

            权限 / Permission: attachment:delete
            """
            service = AttachmentService(db, current_admin.tenant_id)
            await service.delete(attachment_id)
            return deleted()

        # ========== 附件访问接口 / Attachment Access Endpoints ==========

        @router.get("/{attachment_id}/download-url", summary="获取下载链接")
        @action_read("action.attachment.download_url")
        async def get_download_url(
            attachment_id: int,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
            expires: int = Query(3600, ge=60, le=86400),
        ):
            """
            获取附件下载 URL / Get attachment download URL

            权限 / Permission: attachment:download_url
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
            获取附件预览 URL / Get attachment preview URL

            权限 / Permission: attachment:preview_url
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
            下载附件 / Download attachment

            权限 / Permission: attachment:download
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
            预览附件 / Preview attachment

            权限 / Permission: attachment:preview
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
