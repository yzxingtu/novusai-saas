"""
用户端附件上传 API / User Attachment Upload API

提供用户端头像等文件上传接口（精简版，仅上传+预检）
Provides user file upload endpoints for avatars etc. (simplified, upload + preflight only)
"""

from __future__ import annotations

from fastapi import APIRouter, File, Form, Query, Request, UploadFile
from fastapi.responses import RedirectResponse

from app.configs.service import ConfigService
from app.core.deps import ActiveTenantUser, DbSession
from app.core.i18n import _
from app.core.response import success
from app.enums.attachment import AttachmentSource, AttachmentVisibility
from app.exceptions import NotFoundException
from app.models.tenant.attachment import Attachment
from app.rbac.decorators import auth_only
from app.schemas.tenant.attachment import (
    AttachmentAccessUrlResponse,
    AttachmentPreflightRequest,
    AttachmentSafePreflightResponse,
    AttachmentSafeResponse,
    AttachmentSafeUploadResponse,
)
from app.services.tenant.attachment_download_service import AttachmentDownloadService
from app.services.tenant.attachment_service import AttachmentService

router = APIRouter(prefix="/attachments", tags=["User Attachments"])


def _with_preview_url(data: dict, tenant_id: int) -> dict:
    """Inject preview_url for user attachment payloads."""
    data["preview_url"] = AttachmentDownloadService.build_preview_url(
        attachment_id=data["id"],
        tenant_id=tenant_id,
        visibility=data.get("visibility", "private"),
    )
    return data


def _can_user_access_attachment(
    attachment: Attachment,
    current_user: ActiveTenantUser,
) -> bool:
    """Allow public files or the current user's own tenant_user uploads."""
    if attachment.visibility == AttachmentVisibility.PUBLIC.value:
        return True
    return (
        attachment.source == AttachmentSource.TENANT_USER.value
        and attachment.uploader_id == current_user.id
    )


async def _get_accessible_attachment(
    db: DbSession,
    current_user: ActiveTenantUser,
    attachment_id: int,
) -> tuple[AttachmentDownloadService, Attachment]:
    """Resolve a user-accessible attachment within the current tenant."""
    service = AttachmentDownloadService(db, current_user.tenant_id)
    attachment = await service.get_attachment(attachment_id)
    if not _can_user_access_attachment(attachment, current_user):
        raise NotFoundException(message=_("error.common.not_found"))
    return service, attachment


@router.post(
    "/preflight",
    summary="预检文件是否已存在（秒传） / Preflight check if file exists (instant upload)",
)
@auth_only
async def preflight_check(
    request: Request,
    db: DbSession,
    current_user: ActiveTenantUser,
    body: AttachmentPreflightRequest,
):
    """
    用户端预检文件是否已存在（秒传）/ User preflight file exists (instant upload).
    """
    raw_hash = body.hash
    if raw_hash.startswith("sha256:"):
        raw_hash = raw_hash[7:]

    service = AttachmentService(db, current_user.tenant_id)
    result = await service.preflight_check(
        file_hash=raw_hash,
        filename=body.filename,
        size=body.size,
        visibility=AttachmentVisibility(body.visibility)
        if body.visibility
        else AttachmentVisibility.PRIVATE,
    )
    resp = AttachmentSafePreflightResponse(
        exists=result["exists"],
        attachment=(
            AttachmentSafeResponse.model_validate(
                _with_preview_url(
                    AttachmentSafeResponse.model_validate(
                        result["attachment"],
                        from_attributes=True,
                    ).model_dump(),
                    current_user.tenant_id,
                )
            )
            if result["attachment"]
            else None
        ),
        url=result["url"],
        used_bytes=result["used_bytes"],
    )
    return success(data=resp, message=_("common.success"))


@router.post("/upload", summary="用户端上传附件 / User upload attachment")
@auth_only
async def upload_attachment(
    request: Request,
    db: DbSession,
    current_user: ActiveTenantUser,
    file: UploadFile = File(..., description=_("api.param.file")),
    visibility: str = Form("", description=_("api.param.visibility")),
):
    """
    用户端上传附件（头像等）/ User upload attachment (avatars etc.).
    """
    if not visibility:
        config_svc = ConfigService(db)
        visibility = await config_svc.get_platform_config(
            "platform_storage_default_visibility", default="private"
        )
    service = AttachmentService(db, current_user.tenant_id)
    result = await service.upload_file(
        content=file.file,
        filename=file.filename or "unnamed",
        file_size=file.size,
        mime_type=file.content_type,
        visibility=AttachmentVisibility(visibility),
        source=AttachmentSource.TENANT_USER,
        uploader_id=current_user.id,
    )
    return success(
        data=AttachmentSafeUploadResponse(
            attachment=AttachmentSafeResponse.model_validate(
                _with_preview_url(
                    AttachmentSafeResponse.model_validate(
                        result["attachment"],
                        from_attributes=True,
                    ).model_dump(),
                    current_user.tenant_id,
                )
            ),
            url=result["url"],
            used_bytes=result["used_bytes"],
        ),
        message=_("file.upload_success"),
    )


@router.get("/{attachment_id}", summary="获取附件详情 / Get attachment detail")
@auth_only
async def get_attachment(
    request: Request,
    db: DbSession,
    current_user: ActiveTenantUser,
    attachment_id: int,
):
    """Get a user-accessible attachment detail."""
    _service, attachment = await _get_accessible_attachment(
        db, current_user, attachment_id
    )
    data = _with_preview_url(
        AttachmentSafeResponse.model_validate(
            attachment,
            from_attributes=True,
        ).model_dump(),
        current_user.tenant_id,
    )
    return success(data=data, message=_("common.success"))


@router.get("/{attachment_id}/preview-url", summary="获取预览链接 / Get preview URL")
@auth_only
async def get_preview_url(
    request: Request,
    db: DbSession,
    current_user: ActiveTenantUser,
    attachment_id: int,
    expires: int = Query(3600, ge=60, le=86400),
):
    """Get signed preview URL for a user-accessible attachment."""
    service, attachment = await _get_accessible_attachment(
        db, current_user, attachment_id
    )
    data = await service.build_access_url(attachment, expires=expires, preview=True)
    return success(
        data=AttachmentAccessUrlResponse(**data), message=_("common.success")
    )


@router.get("/{attachment_id}/download", summary="下载附件 / Download attachment")
@auth_only
async def download_attachment(
    request: Request,
    db: DbSession,
    current_user: ActiveTenantUser,
    attachment_id: int,
    expires: int = Query(3600, ge=60, le=86400),
):
    """Download a user-accessible attachment."""
    service, attachment = await _get_accessible_attachment(
        db, current_user, attachment_id
    )
    if attachment.driver == "local":
        await service.record_download(attachment)
        return await service.get_download_response(attachment, preview=False)
    url = await service.get_redirect_url(attachment, expires=expires, preview=False)
    return RedirectResponse(url=url)


@router.get("/upload-rules", summary="获取上传规则 / Get upload rules")
@auth_only
async def get_upload_rules(
    request: Request,
    db: DbSession,
    current_user: ActiveTenantUser,
):
    """
    获取用户端上传规则 / Get user upload rules.
    """
    config_service = ConfigService(db)
    tid = current_user.tenant_id

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

    return success(
        data={
            "allowed_extensions": str(tenant_allowed) if tenant_allowed else "",
            "denied_extensions": str(tenant_denied) if tenant_denied else "",
            "max_file_size_mb": int(max_size) if max_size else 100,
        }
    )
