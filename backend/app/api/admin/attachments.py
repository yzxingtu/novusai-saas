"""
平台端附件管理 API / Platform Attachment API

提供跨企业的附件管理接口（平台管理员专用）
Provides cross-tenant attachment management endpoints (platform admin only).
"""

from fastapi import File, Form, Query, Request, UploadFile
from fastapi.responses import RedirectResponse

from app.configs.service import ConfigService, PLATFORM_TENANT_ID
from app.core.base_controller import GlobalController
from app.core.base_schema import PageResponse
from app.core.deps import ActiveAdmin, DbSession, QueryParams
from app.core.i18n import _
from app.core.response import deleted, success
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
    AdminChunkUploadInitRequest,
    AttachmentAccessUrlResponse,
    AttachmentListItem,
    AttachmentPreflightRequest,
    AttachmentPreflightResponse,
    AttachmentResponse,
    AttachmentUploadResponse,
    BatchUploadItem,
    BatchUploadResponse,
    ChunkUploadInitResponse,
    ChunkUploadProgressResponse,
)
from app.services.system.attachment_service import AdminAttachmentService
from app.services.tenant.attachment_download_service import AttachmentDownloadService


def _with_preview_url(data: dict) -> dict:
    """为序列化后的附件字典注入 preview_url / Inject preview_url into serialized attachment dict."""
    data["preview_url"] = AttachmentDownloadService.build_preview_url(
        attachment_id=data["id"],
        tenant_id=data.get("tenant_id", PLATFORM_TENANT_ID),
        visibility=data.get("visibility", "private"),
    )
    return data


@permission_resource(
    resource="attachment",
    name="menu.admin.attachment",
    scope=PermissionScope.ADMIN,
    parent_resource="system_config",
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
    平台端附件管理控制器 / Platform Attachment Management Controller

    提供跨企业的附件管理接口 / Provides cross-tenant attachment management endpoints
    """

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
            current_admin: ActiveAdmin,
        ):
            """
            获取平台上传规则（扩展名白名单、黑名单、大小限制）
            Get platform upload rules (extension whitelist, blacklist, size limit)

            前端用于预校验，避免无效上传。
            Used by frontend for pre-validation to avoid invalid uploads.

            权限 / Permission: attachment:upload_rules
            """
            from app.configs.service import ConfigService, PLATFORM_TENANT_ID
            config_service = ConfigService(db)

            allowed = await config_service.get_platform_config(
                "platform_storage_allowed_extensions", default=""
            )
            denied = await config_service.get_platform_config(
                "platform_storage_denied_extensions", default=""
            )
            max_size = await config_service.get_platform_config(
                "platform_storage_max_file_size_mb", default=100
            )

            return success(data={
                "allowed_extensions": str(allowed) if allowed else "",
                "denied_extensions": str(denied) if denied else "",
                "max_file_size_mb": int(max_size) if max_size else 100,
            })

        # ========== 预检接口（秒传） / Preflight (Instant Upload) ==========

        @router.post("/preflight", summary="预检文件是否已存在（秒传）")
        @action_create("action.attachment.upload")
        async def preflight_check(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            body: AttachmentPreflightRequest,
            tenant_id: int = Query(PLATFORM_TENANT_ID, ge=0, description=_("api.param.tenant_id")),
        ):
            """
            预检文件是否已存在 / Check if file already exists (preflight)

            前端计算文件 SHA-256 哈希后调用此接口，如果服务端已有相同文件，
            则直接返回已有附件信息（秒传），无需再次上传文件。
            Frontend computes file SHA-256 hash then calls this endpoint; if server already has
            the same file, returns existing attachment info (instant upload) without re-uploading.

            hash 格式 / format: sha256:{hex_digest}

            权限 / Permission: attachment:upload
            """
            raw_hash = body.hash
            if raw_hash.startswith("sha256:"):
                raw_hash = raw_hash[7:]

            service = AdminAttachmentService(db)
            result = await service.preflight_check(
                tenant_id=tenant_id,
                file_hash=raw_hash,
                filename=body.filename,
                size=body.size,
                visibility=AttachmentVisibility(body.visibility),
            )
            resp = AttachmentPreflightResponse(
                exists=result["exists"],
                attachment=(
                    AttachmentResponse.model_validate(result["attachment"], from_attributes=True)
                    if result["attachment"]
                    else None
                ),
                url=result["url"],
                used_bytes=0,
            )
            return success(data=resp, message=_("common.success"))

        # ========== 上传接口 / Upload Endpoints ==========

        @router.post("/upload", summary="上传附件")
        @action_create("action.attachment.upload")
        async def upload_attachment(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            file: UploadFile = File(..., description=_("api.param.file")),
            tenant_id: int = Form(PLATFORM_TENANT_ID, ge=0, description=_("api.param.tenant_id")),
            visibility: str = Form("", description=_("api.param.visibility")),
            business_type: str | None = Form(None, description=_("api.param.business_type")),
            business_id: int | None = Form(None, description=_("api.param.business_id")),
        ):
            """
            平台端上传附件 / Platform upload attachment

            - tenant_id=PLATFORM_TENANT_ID: 平台附件（站点 Logo、系统资源等） / Platform attachment (site logo, system resources, etc.)
            - tenant_id>PLATFORM_TENANT_ID: 代企业上传附件 / Upload on behalf of tenant

            不受企业配额限制，使用平台存储配置 / Not subject to tenant quota, uses platform storage config

            权限 / Permission: attachment:upload
            """
            # 未指定 visibility 时使用平台配置的默认值 / Use platform default when visibility not specified
            if not visibility:
                config_svc = ConfigService(db)
                visibility = await config_svc.get_platform_config(
                    "platform_storage_default_visibility", default="private"
                )
            service = AdminAttachmentService(db)
            result = await service.upload_file(
                tenant_id=tenant_id,
                content=file.file,
                filename=file.filename or "unnamed",
                file_size=file.size,
                mime_type=file.content_type,
                visibility=AttachmentVisibility(visibility),
                source=AttachmentSource.PLATFORM_ADMIN,
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
                    used_bytes=0,  # 平台端不追踪配额
                ),
                message=_("file.upload_success"),
            )

        @router.post("/batch-upload", summary="批量上传附件")
        @action_create("action.attachment.upload")
        async def batch_upload_attachments(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            files: list[UploadFile] = File(..., description=_("api.param.files")),
            tenant_id: int = Form(PLATFORM_TENANT_ID, ge=0, description=_("api.param.tenant_id")),
            visibility: str = Form("", description=_("api.param.visibility")),
            business_type: str | None = Form(None, description=_("api.param.business_type")),
            business_id: int | None = Form(None, description=_("api.param.business_id")),
        ):
            """
            平台端批量上传附件 / Platform batch upload attachments

            - 最多一次上传 20 个文件 / Max 20 files per batch
            - 单个文件失败不影响其他文件 / Single file failure doesn't affect others
            - 不受企业配额限制 / Not subject to tenant quota

            权限 / Permission: attachment:upload
            """
            if len(files) > 20:
                files = files[:20]
            if not visibility:
                config_svc = ConfigService(db)
                visibility = await config_svc.get_platform_config(
                    "platform_storage_default_visibility", default="private"
                )
            service = AdminAttachmentService(db)
            items: list[BatchUploadItem] = []
            for f in files:
                try:
                    result = await service.upload_file(
                        tenant_id=tenant_id,
                        content=f.file,
                        filename=f.filename or "unnamed",
                        file_size=f.size,
                        mime_type=f.content_type,
                        visibility=AttachmentVisibility(visibility),
                        source=AttachmentSource.PLATFORM_ADMIN,
                        uploader_id=current_admin.id,
                        business_type=business_type,
                        business_id=business_id,
                    )
                    items.append(BatchUploadItem(
                        filename=f.filename or "unnamed",
                        success=True,
                        attachment=AttachmentResponse.model_validate(
                            result["attachment"], from_attributes=True
                        ),
                        url=result["url"],
                    ))
                except Exception as exc:
                    items.append(BatchUploadItem(
                        filename=f.filename or "unnamed",
                        success=False,
                        error=str(exc),
                    ))
            success_count = sum(1 for i in items if i.success)
            return success(
                data=BatchUploadResponse(
                    items=items,
                    success_count=success_count,
                    failure_count=len(items) - success_count,
                    used_bytes=0,  # 平台端不追踪配额 / Platform doesn't track quota
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
            current_admin: ActiveAdmin,
            body: AdminChunkUploadInitRequest,
        ):
            """
            初始化分片上传会话（平台端） / Initialize chunk upload session (platform)

            - tenant_id=PLATFORM_TENANT_ID: 平台附件 / Platform attachment
            - tenant_id>PLATFORM_TENANT_ID: 代企业上传 / Upload on behalf of tenant

            权限 / Permission: attachment:chunk_init
            """
            service = AdminAttachmentService(db)
            result = await service.start_chunk_upload(
                tenant_id=body.tenant_id,
                filename=body.filename,
                total_size=body.total_size,
                chunk_size=body.chunk_size,
                mime_type=body.mime_type,
                visibility=AttachmentVisibility(body.visibility),
                source=AttachmentSource.PLATFORM_ADMIN,
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
            current_admin: ActiveAdmin,
            chunk_index: int = Form(..., ge=0, description=_("api.param.chunk_index")),
            file: UploadFile = File(..., description=_("api.param.chunk_data")),
        ):
            """
            上传分片数据 / Upload chunk data

            权限 / Permission: attachment:chunk_upload
            """
            service = AdminAttachmentService(db)
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
            current_admin: ActiveAdmin,
        ):
            """
            完成分片上传并合并文件 / Complete chunk upload and merge files

            权限 / Permission: attachment:chunk_complete
            """
            service = AdminAttachmentService(db)
            result = await service.complete_chunk_upload(upload_id)
            return success(
                data=AttachmentUploadResponse(
                    attachment=AttachmentResponse.model_validate(
                        result["attachment"], from_attributes=True
                    ),
                    url=result["url"],
                    used_bytes=0,
                ),
                message=_("file.upload_success"),
            )

        @router.get("/chunk/{upload_id}/status", summary="获取分片上传进度")
        @action_read("action.attachment.chunk_status")
        async def get_chunk_upload_status(
            request: Request,
            upload_id: str,
            db: DbSession,
            current_admin: ActiveAdmin,
        ):
            """
            获取分片上传进度 / Get chunk upload progress

            权限 / Permission: attachment:chunk_status
            """
            service = AdminAttachmentService(db)
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
            current_admin: ActiveAdmin,
        ):
            """
            取消分片上传并清理临时文件 / Abort chunk upload and clean up temp files

            权限 / Permission: attachment:chunk_abort
            """
            service = AdminAttachmentService(db)
            await service.abort_upload(upload_id)
            return success(message=_("common.success"))

        # ========== 附件管理接口 / Attachment Management Endpoints ==========

        @router.get("/select", summary="获取附件下拉选项")
        @action_read("action.attachment.select")
        async def select_attachments(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            search: str = Query("", description=_("api.param.search")),
            tenant_id: int | None = Query(None, description=_("api.param.tenant_id_filter")),
            page: int = Query(0, ge=0, description=_("api.param.page")),
            page_size: int = Query(20, ge=1, le=100, description=_("api.param.page_size")),
        ):
            """
            获取附件下拉选项 / Get attachment dropdown options

            用于从现有附件中选择文件 / For selecting files from existing attachments

            权限 / Permission: attachment:select
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
            tenant_id: int | None = Query(None, description=_("api.param.tenant_id_filter")),
        ):
            """
            获取附件存储统计 / Get attachment storage statistics

            - 不传 tenant_id: 统计所有企业 / Without tenant_id: stats for all tenants
            - 传入 tenant_id: 统计指定企业 / With tenant_id: stats for specified tenant

            权限 / Permission: attachment:stats
            """
            service = AdminAttachmentService(db)
            stats = await service.get_storage_stats(tenant_id)
            return success(data=stats, message=_("common.success"))

        @router.get("/stats/by-tenant", summary="获取按企业分组的附件统计")
        @action_read("action.attachment.stats_by_tenant")
        async def get_attachment_stats_by_tenant(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
        ):
            """
            获取按企业分组的存储统计 / Get storage statistics grouped by tenant

            返回各企业的附件数量和存储用量 / Returns attachment count and storage usage per tenant

            权限 / Permission: attachment:stats_by_tenant
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
            获取附件列表 / Get attachment list

            - 支持通用筛选 / General filtering: filter[field][op]=value
            - 支持按企业筛选 / Tenant filtering: filter[tenant_id][eq]=1
            - 支持排序 / Sorting: sort=-created_at,name
            - 支持分页 / Pagination: page[number]=1&page[size]=20

            权限 / Permission: attachment:list
            """
            service = AdminAttachmentService(db)
            items, total = await service.query_list(spec, scope="admin")
            serialized = [
                _with_preview_url(
                    AttachmentListItem.model_validate(item, from_attributes=True).model_dump()
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
            current_admin: ActiveAdmin,
        ):
            """
            获取附件详情 / Get attachment details

            权限 / Permission: attachment:detail
            """
            service = AdminAttachmentService(db)
            attachment = await service.get_by_id(attachment_id)
            if not attachment:
                raise NotFoundException(message=_("error.common.not_found"))
            data = _with_preview_url(
                AttachmentResponse.model_validate(attachment, from_attributes=True).model_dump()
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
            current_admin: ActiveAdmin,
        ):
            """
            删除附件（软删除 + 物理文件删除 + 依赖检查） / Delete attachment (soft delete + physical file deletion + dependency check)

            权限 / Permission: attachment:delete
            """
            service = AdminAttachmentService(db)
            await service.delete(attachment_id)
            return deleted()

        # ========== 附件访问接口 / Attachment Access Endpoints ==========

        @router.get("/{attachment_id}/download-url", summary="获取下载链接")
        @action_read("action.attachment.download_url")
        async def get_download_url(
            attachment_id: int,
            db: DbSession,
            current_admin: ActiveAdmin,
            expires: int = Query(3600, ge=60, le=86400),
        ):
            """
            获取附件下载 URL / Get attachment download URL

            权限 / Permission: attachment:download_url
            """
            # 平台端不做企业隔离，传入 None / Platform doesn't enforce tenant isolation, pass None
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
            获取附件预览 URL / Get attachment preview URL

            权限 / Permission: attachment:preview_url
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
            下载附件 / Download attachment

            权限 / Permission: attachment:download
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
            预览附件 / Preview attachment

            权限 / Permission: attachment:preview
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
