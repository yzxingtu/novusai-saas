import time
from collections import defaultdict
from typing import Literal

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response

from app.core.deps import DbSession
from app.core.i18n import _
from app.rbac.decorators import public
from app.services.common import ImageProcessService
from app.services.tenant.attachment_download_service import AttachmentDownloadService

router = APIRouter(prefix="/attachments", tags=["公开附件 / Public Attachments"])

# In-memory IP rate limiter for image processing
_image_rate_buckets: dict[str, list[float]] = defaultdict(list)
_IMAGE_RATE_WINDOW = 60  # seconds
_last_eviction = 0.0


def _check_image_rate_limit(client_ip: str, limit: int = 60) -> bool:
    global _last_eviction
    now = time.monotonic()
    cutoff = now - _IMAGE_RATE_WINDOW

    # Periodic eviction of stale IPs (every 5 minutes)
    if now - _last_eviction > 300:
        stale = [ip for ip, ts in _image_rate_buckets.items() if not ts or ts[-1] < cutoff]
        for ip in stale:
            del _image_rate_buckets[ip]
        _last_eviction = now

    bucket = _image_rate_buckets[client_ip]
    _image_rate_buckets[client_ip] = [t for t in bucket if t > cutoff]
    if len(_image_rate_buckets[client_ip]) >= limit:
        return False
    _image_rate_buckets[client_ip].append(now)
    return True


@router.get("/{attachment_id}/access", summary="访问附件")
@public
async def access_attachment(
    attachment_id: int,
    db: DbSession,
    token: str | None = None,
    preview: bool = Query(False),
    exp: str | None = Query(None, description=_("api.param.sig_exp")),
    sign: str | None = Query(None, description=_("api.param.sig_hmac")),
):
    if sign or exp:
        AttachmentDownloadService.verify_access_sign(attachment_id, exp, sign)
    service = AttachmentDownloadService(db)
    attachment = await service.get_attachment(attachment_id)
    await service.validate_access(attachment, token)

    # Local files: stream directly from disk
    if attachment.driver == "local":
        await service.record_download(attachment)
        return await service.get_download_response(attachment, preview=preview)

    # Cloud files: generate redirect URL
    url = await service.get_redirect_url(attachment, expires=3600, preview=preview)

    # Guard against self-redirect loop: if _get_access_url fell back to
    # an API proxy URL (private file with config mismatch), return 404
    # instead of redirecting to ourselves.
    if url.startswith("/api/"):
        return JSONResponse(
            status_code=404,
            content={"code": 4040, "message": "File storage config unavailable"},
        )

    return RedirectResponse(url=url)


@router.get("/{attachment_id}/image", summary="图片处理")
@public
async def get_processed_image(
    request: Request,
    attachment_id: int,
    db: DbSession,
    token: str | None = None,
    exp: str | None = Query(None, description=_("api.param.sig_exp")),
    sign: str | None = Query(None, description=_("api.param.sig_hmac")),
    w: int | None = Query(None, ge=1, le=4096, description=_("api.param.img_width")),
    h: int | None = Query(None, ge=1, le=4096, description=_("api.param.img_height")),
    q: int | None = Query(None, ge=1, le=100, description=_("api.param.img_quality")),
    f: Literal["jpg", "png", "webp", "gif"] | None = Query(None, description=_("api.param.img_format")),
    m: Literal["fit", "fill", "crop", "pad"] | None = Query(None, description=_("api.param.img_mode")),
    p: str | None = Query(None, description=_("api.param.img_preset")),
):
    """
    动态图片处理端点 / Dynamic image processing endpoint

    支持通过 URL 参数进行图片缩放、裁剪、格式转换等处理。
    Supports image resizing, cropping, format conversion via URL parameters.

    **参数说明 / Parameters:**
    - `w`: 宽度 / Width (1-4096)
    - `h`: 高度 / Height (1-4096)
    - `q`: 质量 / Quality (1-100, default 85)
    - `f`: 输出格式 / Output format (jpg/png/webp/gif)
    - `m`: 缩放模式 / Resize mode
      - `fit`: 等比缩放，限制在指定宽高内 / Scale proportionally within specified dimensions
      - `fill`: 等比缩放并居中裁剪 / Scale and center crop
      - `crop`: 裁剪指定区域 / Crop specified area
      - `pad`: 等比缩放并填充背景 / Scale and pad background
    - `p`: 预设名称 / Preset name (thumb/avatar/preview/banner/small/medium/large)

    **预设配置 / Preset configurations:**
    - `thumb`: 150x150 fill
    - `avatar`: 200x200 fill
    - `preview`: 800x600 fit
    - `banner`: 1200x400 fill
    - `small`: 320px 宽 / wide fit
    - `medium`: 640px 宽 / wide fit
    - `large`: 1024px 宽 / wide fit
    """
    if sign or exp:
        AttachmentDownloadService.verify_access_sign(attachment_id, exp, sign)

    # IP rate limiting (read configurable limit)
    from app.configs.service import ConfigService
    config_svc = ConfigService(db)
    rate_limit = int(await config_svc.get_platform_config(
        "platform_image_process_rate_limit", default=60
    ))
    client_ip = request.client.host if request.client else "unknown"
    if not _check_image_rate_limit(client_ip, limit=rate_limit):
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many image processing requests. Please try again later."},
        )

    # 验证访问权限 / Validate access permissions
    download_service = AttachmentDownloadService(db)
    attachment = await download_service.get_attachment(attachment_id)
    await download_service.validate_access(attachment, token)

    # 图片处理服务 / Image processing service
    image_service = ImageProcessService(db, tenant_id=attachment.tenant_id)

    # 检查图片处理功能是否启用 / Check if image processing is enabled
    if not await image_service.is_enabled():
        # 未启用，直接重定向到原始文件 / Not enabled, redirect to original file
        url = await download_service.get_redirect_url(attachment, expires=3600, preview=True)
        return RedirectResponse(url=url)

    params = await image_service.parse_params(
        width=w,
        height=h,
        quality=q,
        format=f,
        mode=m,
        preset=p,
    )

    # 如果无需处理，重定向到原始访问 URL / If no processing needed, redirect to original access URL
    if params.is_empty():
        url = await download_service.get_redirect_url(attachment, expires=3600, preview=True)
        return RedirectResponse(url=url)

    # 通过服务层获取处理后的图片 / Get processed image via service layer
    result = await image_service.get_processed_image_response(attachment, params)

    # 如果返回 URL，重定向（云存储原生处理） / If URL returned, redirect (cloud storage native processing)
    if isinstance(result, str):
        return RedirectResponse(url=result)

    # 返回处理后的图片数据（本地处理） / Return processed image data (local processing)
    data, mime_type = result
    return Response(
        content=data,
        media_type=mime_type,
        headers={
            "Cache-Control": "public, max-age=31536000",
            "Content-Disposition": "inline",
        },
    )


__all__ = ["router"]
