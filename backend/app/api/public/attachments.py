import time
from collections import defaultdict
from typing import Literal

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response

from app.core.deps import DbSession
from app.rbac.decorators import public
from app.services.common import ImageProcessService
from app.services.tenant.attachment_download_service import AttachmentDownloadService

router = APIRouter(prefix="/attachments", tags=["公开附件"])

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
):
    service = AttachmentDownloadService(db)
    attachment = await service.get_attachment(attachment_id)
    await service.validate_access(attachment, token)
    if attachment.driver == "local":
        await service.record_download(attachment)
        return await service.get_download_response(attachment, preview=preview)
    url = await service.get_redirect_url(attachment, expires=3600, preview=preview)
    return RedirectResponse(url=url)


@router.get("/{attachment_id}/image", summary="图片处理")
@public
async def get_processed_image(
    request: Request,
    attachment_id: int,
    db: DbSession,
    token: str | None = None,
    # 图片处理参数
    w: int | None = Query(None, ge=1, le=4096, description="宽度"),
    h: int | None = Query(None, ge=1, le=4096, description="高度"),
    q: int | None = Query(None, ge=1, le=100, description="质量"),
    f: Literal["jpg", "png", "webp", "gif"] | None = Query(None, description="格式"),
    m: Literal["fit", "fill", "crop", "pad"] | None = Query(None, description="模式"),
    p: str | None = Query(None, description="预设 (thumb/avatar/preview/banner/small/medium/large)"),
):
    """
    动态图片处理端点
    
    支持通过 URL 参数进行图片缩放、裁剪、格式转换等处理。
    
    **参数说明:**
    - `w`: 宽度 (1-4096)
    - `h`: 高度 (1-4096)
    - `q`: 质量 (1-100，默认 85)
    - `f`: 输出格式 (jpg/png/webp/gif)
    - `m`: 缩放模式
      - `fit`: 等比缩放，限制在指定宽高内
      - `fill`: 等比缩放并居中裁剪
      - `crop`: 裁剪指定区域
      - `pad`: 等比缩放并填充背景
    - `p`: 预设名称 (thumb/avatar/preview/banner/small/medium/large)
    
    **预设配置:**
    - `thumb`: 150x150 fill
    - `avatar`: 200x200 fill
    - `preview`: 800x600 fit
    - `banner`: 1200x400 fill
    - `small`: 320px 宽 fit
    - `medium`: 640px 宽 fit
    - `large`: 1024px 宽 fit
    """
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

    # 验证访问权限
    download_service = AttachmentDownloadService(db)
    attachment = await download_service.get_attachment(attachment_id)
    await download_service.validate_access(attachment, token)
    
    # 图片处理服务
    image_service = ImageProcessService(db, tenant_id=attachment.tenant_id)
    
    # 检查图片处理功能是否启用
    if not await image_service.is_enabled():
        # 未启用，直接重定向到原始文件
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
    
    # 如果无需处理，重定向到原始访问 URL
    if params.is_empty():
        url = await download_service.get_redirect_url(attachment, expires=3600, preview=True)
        return RedirectResponse(url=url)
    
    # 通过服务层获取处理后的图片
    result = await image_service.get_processed_image_response(attachment, params)
    
    # 如果返回 URL，重定向（云存储原生处理）
    if isinstance(result, str):
        return RedirectResponse(url=result)
    
    # 返回处理后的图片数据（本地处理）
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
