"""
文件上传 Service — 整文件 + 分片 + 断点续传
"""

from __future__ import annotations

import os
import re
import uuid

from app.core.base_service import TenantService
from app.core.i18n import _
from app.core.logging import LogManager
from app.exceptions import BusinessException, NotFoundException

logger = LogManager.get_logger("storage")


def _sanitize_filename(name: str) -> str:
    """Sanitize user-provided filename to prevent path traversal."""
    # Strip directory components (handle both / and \ separators)
    name = os.path.basename(name)
    # Remove any remaining path traversal patterns
    name = re.sub(r'\.\.+', '.', name)
    # Remove control characters and null bytes
    name = re.sub(r'[\x00-\x1f]', '', name)
    return name or "untitled"


class UploadService(TenantService):
    def __init__(self, db, tenant_id: int | None):
        # This service composes repositories on demand and does not rely on BaseService.repo.
        self.db = db
        self.tenant_id = tenant_id

    # ── 整文件上传 ─────────────────────────────────────────────

    async def upload_whole(
        self,
        parent_id: int | None,
        filename: str,
        content: bytes,
        mime_type: str,
        created_by: int | None = None,
    ) -> object:
        from app.core.base_model import utc_now
        from app.storage.manager import StorageManager
        from ..models.node import FileNode, NodeTypeEnum
        from ..repositories.quota_repository import QuotaRepository

        filename = _sanitize_filename(filename)

        # 1. 检查配额
        quota_repo = QuotaRepository(self.db, self.tenant_id)
        quota = await quota_repo.get_or_create()
        if not quota.check_capacity(len(content)):
            raise BusinessException(
                message=_("plugin.netdisk.error.quota_exceeded").format(free=f"{quota.free_bytes / 1024**3:.2f}"),
                status_code=429,
            )

        # 2. 写入存储
        tmp_id = str(uuid.uuid4())[:8]
        storage_key = f"netdisk/{self.tenant_id}/{tmp_id}/{filename}"
        storage = StorageManager.get_driver()
        await storage.put(storage_key, content, mime_type=mime_type)

        # 3. 写入 DB 节点
        node = FileNode(
            tenant_id=self.tenant_id,
            parent_id=parent_id,
            name=filename,
            node_type=NodeTypeEnum.FILE.value,
            storage_key=storage_key,
            size_bytes=len(content),
            mime_type=mime_type,
            created_by=created_by,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        self.db.add(node)
        await self.db.flush()

        # 更新 storage_key 加入 node.id
        node.storage_key = f"netdisk/{self.tenant_id}/{node.id}/{filename}"
        try:
            await storage.delete(storage_key)
            await storage.put(node.storage_key, content, mime_type=mime_type)
        except Exception as e:
            logger.warning("netdisk: rename storage key failed: %s", e)
            node.storage_key = storage_key  # fallback

        # 4. 更新配额
        await quota_repo.add_used(len(content))
        await self.db.commit()
        await self.db.refresh(node)
        return node

    # ── 分片上传 ───────────────────────────────────────────────

    async def init_multipart(
        self,
        parent_id: int | None,
        filename: str,
        total_size: int,
    ) -> dict:
        """初始化分片上传，返回 upload_id"""
        from app.storage.manager import StorageManager
        from ..repositories.quota_repository import QuotaRepository

        filename = _sanitize_filename(filename)

        # 先检查配额
        quota_repo = QuotaRepository(self.db, self.tenant_id)
        quota = await quota_repo.get_or_create()
        if not quota.check_capacity(total_size):
            raise BusinessException(
                message=_("plugin.netdisk.error.quota_exceeded").format(free=f"{quota.free_bytes / 1024**3:.2f}"),
                status_code=429,
            )

        upload_id = str(uuid.uuid4())
        storage_key = f"netdisk/{self.tenant_id}/parts/{upload_id}/{filename}"

        storage = StorageManager.get_driver()
        multipart_id = await storage.init_multipart_upload(storage_key)

        # 将分片上传元数据缓存到 Redis（5小时 TTL）
        import json

        from app.core.redis import get_redis
        redis = get_redis()
        meta = {
            "upload_id": upload_id,
            "multipart_id": multipart_id,
            "tenant_id": self.tenant_id,
            "parent_id": parent_id,
            "filename": filename,
            "total_size": total_size,
            "storage_key": storage_key,
            "uploaded_parts": [],
        }
        await redis.setex(f"netdisk:upload:{upload_id}", 18000, json.dumps(meta))

        return {
            "upload_id": upload_id,
            "chunk_size": 5 * 1024 * 1024,  # 5 MB
            "total_size": total_size,
        }

    async def upload_part(self, upload_id: str, part_no: int, data: bytes) -> dict:
        """上传单个分片"""
        import json

        from app.core.redis import get_redis
        from app.storage.manager import StorageManager

        redis = get_redis()
        raw = await redis.get(f"netdisk:upload:{upload_id}")
        if not raw:
            raise NotFoundException(message=_("plugin.netdisk.error.upload_not_found"))

        meta = json.loads(raw)
        if meta["tenant_id"] != self.tenant_id:
            raise BusinessException(message=_("plugin.netdisk.error.upload_not_found"))

        storage = StorageManager.get_driver()
        etag = await storage.upload_part(
            meta["storage_key"], meta["multipart_id"], part_no + 1, data
        )

        if part_no not in meta["uploaded_parts"]:
            meta["uploaded_parts"].append(part_no)
        meta.setdefault("etags", {})[str(part_no)] = etag or ""

        await redis.setex(f"netdisk:upload:{upload_id}", 18000, json.dumps(meta))
        return {"part_no": part_no, "status": "ok"}

    async def complete_multipart(self, upload_id: str, created_by: int | None = None) -> object:
        """合并分片，写入 DB 节点，更新配额"""
        import json

        from app.core.base_model import utc_now
        from app.core.redis import get_redis
        from app.storage.manager import StorageManager
        from ..models.node import FileNode, NodeTypeEnum
        from ..repositories.quota_repository import QuotaRepository

        redis = get_redis()
        raw = await redis.get(f"netdisk:upload:{upload_id}")
        if not raw:
            raise NotFoundException(message=_("plugin.netdisk.error.upload_not_found"))
        meta = json.loads(raw)

        storage = StorageManager.get_driver()
        etags = [(int(k), v) for k, v in (meta.get("etags") or {}).items()]
        etags.sort(key=lambda x: x[0])
        parts = [(pno + 1, etag) for pno, etag in etags]

        final_key = f"netdisk/{self.tenant_id}/{upload_id}/{meta['filename']}"
        await storage.complete_multipart_upload(
            meta["storage_key"], meta["multipart_id"], final_key, parts
        )

        node = FileNode(
            tenant_id=self.tenant_id,
            parent_id=meta.get("parent_id"),
            name=meta["filename"],
            node_type=NodeTypeEnum.FILE.value,
            storage_key=final_key,
            size_bytes=meta["total_size"],
            created_by=created_by,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        self.db.add(node)
        await self.db.flush()

        quota_repo = QuotaRepository(self.db, self.tenant_id)
        await quota_repo.add_used(meta["total_size"])
        await self.db.commit()
        await self.db.refresh(node)

        await redis.delete(f"netdisk:upload:{upload_id}")
        return node

    async def get_upload_status(self, upload_id: str) -> dict:
        """断点续传：查询已上传分片列表"""
        import json

        from app.core.redis import get_redis

        redis = get_redis()
        raw = await redis.get(f"netdisk:upload:{upload_id}")
        if not raw:
            raise NotFoundException(message=_("plugin.netdisk.error.upload_not_found"))
        meta = json.loads(raw)
        if meta["tenant_id"] != self.tenant_id:
            raise NotFoundException(message=_("plugin.netdisk.error.upload_not_found"))

        return {
            "upload_id": upload_id,
            "uploaded_parts": meta.get("uploaded_parts", []),
            "total_size": meta["total_size"],
            "filename": meta["filename"],
        }

    async def get_download_url(self, node_id: int) -> str:
        """生成签名下载 URL（15 分钟有效）"""
        from app.storage.manager import StorageManager
        from ..repositories.node_repository import NodeRepository

        repo = NodeRepository(self.db, self.tenant_id)
        node = await repo.get(node_id)
        if node is None or node.tenant_id != self.tenant_id or not node.storage_key:
            raise NotFoundException(message=_("plugin.netdisk.error.node_not_found"))

        storage = StorageManager.get_driver()
        return await storage.get_url(node.storage_key, expires=900)
