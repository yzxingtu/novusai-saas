"""
企业端上传/下载 API

Handler 签名：(request, db, ctx)
- 整文件上传：multipart/form-data 通过 request.form() + request.files()
- 分片上传：init → part × N → complete
"""

from __future__ import annotations

from ._schemas import node_schema as _node_schema


async def upload_whole(request, db, ctx):
    """POST multipart/form-data 整文件上传"""
    form      = await request.form()
    file_obj  = form.get("file")
    parent_id_str = form.get("parent_id")
    parent_id = int(parent_id_str) if parent_id_str else None

    content   = await file_obj.read()
    mime_type = file_obj.content_type or "application/octet-stream"
    filename  = file_obj.filename or "untitled"

    from ..services.upload_service import UploadService
    svc  = UploadService(db, ctx.get_current_tenant_id())
    node = await svc.upload_whole(
        parent_id=parent_id,
        filename=filename,
        content=content,
        mime_type=mime_type,
    )
    return {"node": _node_schema(node)}


async def upload_init(request, db, ctx):
    """POST JSON 初始化分片上传，返回 upload_id"""
    body = await request.json()
    from ..services.upload_service import UploadService
    svc    = UploadService(db, ctx.get_current_tenant_id())
    result = await svc.init_multipart(
        parent_id=body.get("parent_id"),
        filename=body["filename"],
        total_size=int(body["size"]),
    )
    return result


async def upload_part(request, db, ctx):
    """POST multipart 上传单个分片"""
    upload_id = request.query_params["upload_id"]
    part_no   = int(request.query_params["part_no"])
    form      = await request.form()
    file_obj  = form.get("file")
    data      = await file_obj.read()

    from ..services.upload_service import UploadService
    svc    = UploadService(db, ctx.get_current_tenant_id())
    result = await svc.upload_part(upload_id, part_no, data)
    return result


async def upload_complete(request, db, ctx):
    """POST JSON 合并分片，创建节点"""
    body = await request.json()
    from ..services.upload_service import UploadService
    svc  = UploadService(db, ctx.get_current_tenant_id())
    node = await svc.complete_multipart(body["upload_id"])
    return {"node": _node_schema(node)}


async def upload_status(request, db, ctx):
    """GET 断点续传查询—已上传分片列表"""
    upload_id = request.path_params["upload_id"]
    from ..services.upload_service import UploadService
    svc    = UploadService(db, ctx.get_current_tenant_id())
    result = await svc.get_upload_status(upload_id)
    return result


async def download_node(request, db, ctx):
    """GET 返回签名下载 URL（15 分钟有效）"""
    node_id = int(request.path_params["node_id"])
    from ..services.upload_service import UploadService
    svc = UploadService(db, ctx.get_current_tenant_id())
    url = await svc.get_download_url(node_id)
    return {"url": url}


async def get_thumbnail(request, db, ctx):
    """GET 图片缩略图（200x200 JPEG，直接返回二进制）"""
    import io

    from fastapi import HTTPException
    from fastapi.responses import Response
    from PIL import Image, UnidentifiedImageError

    from app.storage.manager import StorageManager
    from ..repositories.node_repository import NodeRepository

    node_id   = int(request.path_params["node_id"])
    tenant_id = ctx.get_current_tenant_id()

    # 通过 Repository 查询（避免 Controller 直接操作 DB）
    repo = NodeRepository(db, tenant_id)
    node = await repo.get(node_id)
    if node is None or node.tenant_id != tenant_id \
            or not (node.mime_type or "").startswith("image/") \
            or not node.storage_key or node.is_deleted:
        raise HTTPException(status_code=404)

    storage = StorageManager.get_driver()
    raw     = await storage.get(node.storage_key)

    # PIL Decompression Bomb 防护（限制解压尺寸最大 50MP）
    Image.MAX_IMAGE_PIXELS = 50_000_000
    try:
        img = Image.open(io.BytesIO(raw))
        img.thumbnail((200, 200), Image.LANCZOS)
    except (UnidentifiedImageError, Image.DecompressionBombError):
        raise HTTPException(status_code=415, detail="Unsupported or oversized image")

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return Response(content=buf.getvalue(), media_type="image/jpeg")


