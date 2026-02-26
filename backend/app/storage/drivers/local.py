"""
本地存储驱动实现
"""

from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, BinaryIO, Optional

import anyio

from app.exceptions import StorageError, StorageNotFoundError
from app.storage.base import (
    FileInfo,
    StorageConfig,
    StorageDriver,
    StorageVisibility,
    UploadResult,
)

if TYPE_CHECKING:
    from app.utils.image import ImageProcessParams


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
        content = json.dumps(metadata, ensure_ascii=False)

        def _write() -> None:
            meta_path.write_text(content, encoding="utf-8")

        await anyio.to_thread.run_sync(_write)

    async def _load_metadata(self, path: str) -> Optional[dict]:
        """
        读取元数据侧写文件
        """
        meta_path = self._meta_path(path)
        if not meta_path.exists():
            return None

        def _read() -> str:
            return meta_path.read_text(encoding="utf-8")

        content = await anyio.to_thread.run_sync(_read)
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

    # ========== 图片处理方法 ==========

    def _get_cache_root(self) -> Path:
        """
        获取图片缓存根目录
        """
        cache_path = self.config.options.get("image_cache_path")
        if cache_path:
            return Path(cache_path)
        return self.root / ".cache" / "images"

    def _get_cache_path(self, path: str, params: "ImageProcessParams") -> Path:
        """
        获取缓存文件路径
        """
        # 生成缓存键: {path_hash}_{params_hash}.{format}
        path_hash = hashlib.md5(path.encode()).hexdigest()[:8]
        params_hash = params.to_cache_key()
        
        # 确定输出格式
        output_format = params.format
        if not output_format:
            # 从原始路径推断格式
            ext = Path(path).suffix.lower().lstrip(".")
            output_format = ext if ext in {"jpg", "jpeg", "png", "webp", "gif"} else "jpg"
        
        cache_filename = f"{path_hash}_{params_hash}.{output_format}"
        return self._get_cache_root() / cache_filename

    async def get_image_url(
        self,
        path: str,
        params: "ImageProcessParams",
        expires: int = 3600,
        visibility: StorageVisibility | None = None,
    ) -> str:
        """
        获取处理后的图片 URL
        
        本地存储：处理图片并缓存，返回缓存文件的访问 URL
        """
        # 如果不需要处理，直接返回原始 URL
        if params.is_empty():
            return await self.get_url(path, expires=expires, visibility=visibility)
        
        # 检查缓存
        cache_path = self._get_cache_path(path, params)
        if not cache_path.exists():
            # 处理并缓存
            await self._process_and_cache(path, params, cache_path)
        
        # 返回缓存文件的访问 URL
        cache_relative = cache_path.relative_to(self.root)
        return await self.get_url(
            str(cache_relative),
            expires=expires,
            visibility=visibility,
        )

    async def get_processed_image(
        self,
        path: str,
        params: "ImageProcessParams",
    ) -> tuple[bytes, str] | None:
        """
        获取处理后的图片数据
        
        直接返回处理后的字节数据，用于流式响应
        """
        from app.utils.image import ImageProcessor
        
        # 如果不需要处理，返回 None
        if params.is_empty():
            return None
        
        # 检查缓存
        cache_path = self._get_cache_path(path, params)
        if cache_path.exists():
            # 从缓存读取
            def _read_cache() -> tuple[bytes, str]:
                data = cache_path.read_bytes()
                mime, _ = mimetypes.guess_type(str(cache_path))
                return data, mime or "image/jpeg"
            return await anyio.to_thread.run_sync(_read_cache)
        
        # 处理并缓存
        result = await self._process_and_cache(path, params, cache_path)
        return result

    def _count_variants(self, path: str) -> int:
        """
        Count existing cache variants for a given source path
        """
        path_hash = hashlib.md5(path.encode()).hexdigest()[:8]
        cache_root = self._get_cache_root()
        if not cache_root.exists():
            return 0
        return sum(1 for f in cache_root.iterdir() if f.name.startswith(f"{path_hash}_"))

    async def _process_and_cache(
        self,
        path: str,
        params: "ImageProcessParams",
        cache_path: Path,
    ) -> tuple[bytes, str]:
        """
        处理图片并保存到缓存
        """
        from app.utils.image import ImageProcessor

        max_variants = int(self.config.options.get("image_cache_max_variants", 50))
        variant_count = await anyio.to_thread.run_sync(lambda: self._count_variants(path))
        if variant_count >= max_variants:
            self.logger.warning(
                "Image cache variant limit reached for %s (%d/%d), returning original",
                path, variant_count, max_variants,
            )
            source = await self.get(path)
            data = source.read()
            info = await self.get_info(path)
            return data, info.mime_type if info else "image/jpeg"

        # 获取原图
        source = await self.get(path)
        
        # 处理图片
        data, mime_type = await ImageProcessor.process(source, params)
        
        # 保存到缓存
        def _save_cache() -> None:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_bytes(data)
        
        await anyio.to_thread.run_sync(_save_cache)
        
        return data, mime_type

    def supports_native_image_processing(self) -> bool:
        """
        本地存储不支持原生图片处理，需要本地 Pillow 处理
        """
        return False
