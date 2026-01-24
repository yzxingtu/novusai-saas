"""
本地存储驱动实现
"""

import hashlib
import json
import mimetypes
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import BinaryIO, Optional

import anyio

from app.exceptions import StorageError, StorageNotFoundError
from app.storage.base import (
    FileInfo,
    StorageConfig,
    StorageDriver,
    StorageVisibility,
    UploadResult,
)


class LocalStorageDriver(StorageDriver):
    """
    本地文件系统存储驱动
    """
    name = "local"
    display_name = "storage.driver.local"
    config_schema = {
        "type": "object",
        "properties": {
            "root_path": {
                "type": "string",
                "title": "config.storage.local.root_path",
                "description": "config.storage.local.root_path_desc",
            },
            "base_url": {
                "type": "string",
                "title": "config.storage.local.base_url",
                "description": "config.storage.local.base_url_desc",
            },
            "permissions": {
                "type": "integer",
                "title": "config.storage.local.permissions",
                "default": 420,
                "description": "config.storage.local.permissions_desc",
            },
        },
        "required": ["root_path"],
    }

    def __init__(self, config: StorageConfig):
        """
        初始化本地存储配置
        """
        super().__init__(config)
        self.root = Path(config.root_path)
        self.root.mkdir(parents=True, exist_ok=True)
        self.base_url = config.base_url.rstrip("/") if config.base_url else None
        self.permissions = config.options.get("permissions", 0o644)

    def _full_path(self, path: str) -> Path:
        """
        生成并校验安全的本地路径
        """
        clean_path = Path(path.lstrip("/"))
        full_path = (self.root / clean_path).resolve()
        if not str(full_path).startswith(str(self.root.resolve())):
            raise StorageError()
        return full_path

    def _meta_path(self, path: str) -> Path:
        """
        元数据侧写文件路径
        """
        return self._full_path(path).with_suffix(".meta.json")

    async def _save_metadata(self, path: str, metadata: dict) -> None:
        """
        保存元数据到侧写文件
        """
        meta_path = self._meta_path(path)
        await anyio.to_thread.run_sync(
            meta_path.write_text,
            json.dumps(metadata, ensure_ascii=False),
            encoding="utf-8",
        )

    async def _load_metadata(self, path: str) -> Optional[dict]:
        """
        读取元数据侧写文件
        """
        meta_path = self._meta_path(path)
        if not meta_path.exists():
            return None
        content = await anyio.to_thread.run_sync(meta_path.read_text, encoding="utf-8")
        return json.loads(content)

    async def put(
        self,
        path: str,
        content: BinaryIO,
        mime_type: str | None = None,
        visibility: StorageVisibility = StorageVisibility.PRIVATE,
        metadata: dict | None = None,
    ) -> UploadResult:
        """
        写入文件并返回上传结果
        """
        full_path = self._full_path(path)
        full_path.parent.mkdir(parents=True, exist_ok=True)

        def _write_file() -> tuple[int, str]:
            """
            同步写入文件并计算哈希与大小
            """
            size = 0
            hasher = hashlib.md5()
            with open(full_path, "wb") as f:
                while True:
                    chunk = content.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)
                    hasher.update(chunk)
                    size += len(chunk)
            os.chmod(full_path, self.permissions)
            return size, hasher.hexdigest()

        size, file_hash = await anyio.to_thread.run_sync(_write_file)

        if not mime_type:
            mime_type, _ = mimetypes.guess_type(path)
            mime_type = mime_type or "application/octet-stream"

        extra_meta = metadata or {}
        await self._save_metadata(
            path,
            {"mime_type": mime_type, "visibility": visibility.value, **extra_meta},
        )

        return UploadResult(
            path=path,
            url=await self.get_url(path, visibility=visibility),
            size=size,
            hash=file_hash,
            mime_type=mime_type,
            driver=self.name,
        )

    async def get(self, path: str) -> BinaryIO:
        """
        打开文件并返回二进制流
        """
        full_path = self._full_path(path)
        if not full_path.exists():
            raise StorageNotFoundError()
        return open(full_path, "rb")

    async def delete(self, path: str) -> bool:
        """
        删除文件与元数据
        """
        full_path = self._full_path(path)
        if not full_path.exists():
            return False

        def _delete() -> None:
            """
            同步删除文件与侧写元数据
            """
            if full_path.exists():
                full_path.unlink()
            meta_path = self._meta_path(path)
            if meta_path.exists():
                meta_path.unlink()

        await anyio.to_thread.run_sync(_delete)
        return True

    async def exists(self, path: str) -> bool:
        """
        判断文件是否存在
        """
        return self._full_path(path).exists()

    async def get_url(
        self,
        path: str,
        expires: int = 3600,
        visibility: StorageVisibility | None = None,
    ) -> str:
        """
        获取文件访问 URL
        """
        if visibility is None:
            info = await self.get_info(path)
            visibility = info.visibility if info else StorageVisibility.PRIVATE
        if visibility == StorageVisibility.PUBLIC and self.base_url:
            return f"{self.base_url}/{path.lstrip('/')}"
        return f"/storage/{path.lstrip('/')}"

    async def get_info(self, path: str) -> Optional[FileInfo]:
        """
        获取文件信息与元数据
        """
        full_path = self._full_path(path)
        if not full_path.exists():
            return None

        def _stat() -> os.stat_result:
            """
            同步获取文件状态
            """
            return full_path.stat()

        stat = await anyio.to_thread.run_sync(_stat)
        mime_type, _ = mimetypes.guess_type(path)
        meta = await self._load_metadata(path)
        visibility = (
            StorageVisibility(meta.get("visibility", "private"))
            if meta
            else StorageVisibility.PRIVATE
        )
        return FileInfo(
            path=path,
            size=stat.st_size,
            mime_type=mime_type or "application/octet-stream",
            last_modified=datetime.fromtimestamp(stat.st_mtime),
            visibility=visibility,
            metadata=meta or {},
        )

    async def copy(self, source: str, destination: str) -> bool:
        """
        复制文件
        """
        src = self._full_path(source)
        dst = self._full_path(destination)
        if not src.exists():
            return False

        def _copy() -> None:
            """
            同步复制文件
            """
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

        await anyio.to_thread.run_sync(_copy)
        return True

    async def move(self, source: str, destination: str) -> bool:
        """
        移动或重命名文件
        """
        src = self._full_path(source)
        dst = self._full_path(destination)
        if not src.exists():
            return False

        def _move() -> None:
            """
            同步移动文件
            """
            dst.parent.mkdir(parents=True, exist_ok=True)
            src.replace(dst)

        await anyio.to_thread.run_sync(_move)
        return True
