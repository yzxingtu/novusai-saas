"""
NovusDoc 图片/附件上传 API handler

通过 PluginContext.get_storage() 上传到 plugins/novusdoc/ 命名空间。
"""

from __future__ import annotations

import uuid
from pathlib import PurePosixPath

from app.core.logging import get_logger

from .utils import resolve_tenant_id

logger = get_logger("plugin.novusdoc.api")

_ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp"}
_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


async def upload_file(request, db, ctx):
    """POST /upload — 上传图片/附件"""
    tenant_id = resolve_tenant_id(ctx)
    if tenant_id is None:
        return {"error": "tenant_id required", "code": 4010}

    form = await request.form()
    file = form.get("file")
    if not file:
        return {"error": "file is required", "code": 4001}

    filename = getattr(file, "filename", "") or "upload"
    ext = PurePosixPath(filename).suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        return {
            "error": f"unsupported file type: {ext}",
            "code": 4001,
        }

    content = await file.read()
    if len(content) > _MAX_FILE_SIZE:
        return {
            "error": f"file too large (max {_MAX_FILE_SIZE // 1024 // 1024}MB)",
            "code": 4001,
        }

    # 生成唯一文件名
    unique_name = f"{uuid.uuid4().hex}{ext}"
    storage_path = f"t{tenant_id}/docs/{unique_name}"

    try:
        storage = await ctx.get_storage()
        url = await storage.upload(storage_path, content, content_type=file.content_type)
        return {"url": url, "filename": filename, "size": len(content)}
    except Exception as exc:
        logger.error("novusdoc upload failed: %s", exc, exc_info=True)
        return {"error": "upload failed", "code": 5000, "status_code": 500}
