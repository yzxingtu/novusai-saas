"""
阿里云 OSS 存储驱动实现
"""

import hashlib
import mimetypes
import tempfile
from datetime import datetime
from typing import BinaryIO, Optional

import anyio
import oss2

from app.exceptions import StorageConfigError, StorageError, StorageNotFoundError
from app.storage.base import (
    FileInfo,
    StorageConfig,
    StorageDriver,
    StorageVisibility,
    UploadResult,
)


class OssStorageDriver(StorageDriver):
    """
    阿里云 OSS 存储驱动
    """
    name = "aliyun-oss"
    display_name = "storage.driver.aliyun_oss"
    config_schema = {
        "type": "object",
        "properties": {
            "root_path": {
                "type": "string",
                "title": "config.storage.oss.bucket",
                "description": "config.storage.oss.bucket_desc",
            },
            "base_url": {
                "type": "string",
                "title": "config.storage.oss.base_url",
                "description": "config.storage.oss.base_url_desc",
            },
            "access_key_id": {
                "type": "string",
                "title": "config.storage.oss.access_key_id",
            },
            "access_key_secret": {
                "type": "string",
                "title": "config.storage.oss.access_key_secret",
            },
            "endpoint": {
                "type": "string",
                "title": "config.storage.oss.endpoint",
            },
            "prefix": {
                "type": "string",
                "title": "config.storage.oss.prefix",
            },
        },
        "required": ["root_path"],
    }

    def __init__(self, config: StorageConfig):
        """
        初始化 OSS 客户端
        """
        super().__init__(config)
        options = config.options or {}
        self.bucket_name = options.get("bucket") or config.root_path
        self.endpoint = options.get("endpoint")
        if not self.bucket_name or not self.endpoint:
            raise StorageConfigError()
        self.base_url = config.base_url.rstrip("/") if config.base_url else None
        self.prefix = options.get("prefix", "").strip("/")
        auth = oss2.Auth(
            options.get("access_key_id"),
            options.get("access_key_secret"),
        )
        self.bucket = oss2.Bucket(auth, self.endpoint, self.bucket_name)

    def _key(self, path: str) -> str:
        """
        生成 OSS 对象 Key
        """
        clean = path.lstrip("/")
        return f"{self.prefix}/{clean}" if self.prefix else clean

    def _build_headers(
        self,
        path: str,
        mime_type: str | None,
        visibility: StorageVisibility,
        metadata: dict | None,
    ) -> dict:
        """
        组装上传头信息
        """
        headers: dict = {}
        final_mime_type = mime_type or mimetypes.guess_type(path)[0]
        if final_mime_type:
            headers["Content-Type"] = final_mime_type
        if visibility == StorageVisibility.PUBLIC:
            headers["x-oss-object-acl"] = "public-read"
        if metadata:
            for key, value in metadata.items():
                headers[f"x-oss-meta-{key}"] = str(value)
        headers["x-oss-meta-visibility"] = visibility.value
        return headers

    async def put(
        self,
        path: str,
        content: BinaryIO,
        mime_type: str | None = None,
        visibility: StorageVisibility = StorageVisibility.PRIVATE,
        metadata: dict | None = None,
    ) -> UploadResult:
        """
        上传文件并返回结果
        """
        key = self._key(path)

        def _upload() -> tuple[int, str]:
            """
            同步上传并计算哈希与大小
            """
            size = 0
            hasher = hashlib.md5()
            with tempfile.TemporaryFile() as tmp:
                while True:
                    chunk = content.read(8192)
                    if not chunk:
                        break
                    tmp.write(chunk)
                    hasher.update(chunk)
                    size += len(chunk)
                tmp.seek(0)
                self.bucket.put_object(
                    key,
                    tmp,
                    headers=self._build_headers(path, mime_type, visibility, metadata),
                )
            return size, hasher.hexdigest()

        size, file_hash = await anyio.to_thread.run_sync(_upload)
        final_mime_type = mime_type or mimetypes.guess_type(path)[0]
        return UploadResult(
            path=path,
            url=await self.get_url(path, visibility=visibility),
            size=size,
            hash=file_hash,
            mime_type=final_mime_type or "application/octet-stream",
            driver=self.name,
        )

    async def get(self, path: str) -> BinaryIO:
        """
        获取对象内容
        """
        key = self._key(path)

        def _get() -> BinaryIO:
            """
            同步获取对象
            """
            try:
                result = self.bucket.get_object(key)
            except oss2.exceptions.NoSuchKey as exc:
                raise StorageNotFoundError() from exc
            except oss2.exceptions.OssError as exc:
                raise StorageError() from exc
            return result

        return await anyio.to_thread.run_sync(_get)

    async def delete(self, path: str) -> bool:
        """
        删除对象
        """
        key = self._key(path)

        def _delete() -> bool:
            """
            同步删除对象
            """
            try:
                self.bucket.delete_object(key)
            except oss2.exceptions.OssError as exc:
                raise StorageError() from exc
            return True

        return await anyio.to_thread.run_sync(_delete)

    async def exists(self, path: str) -> bool:
        """
        判断对象是否存在
        """
        key = self._key(path)

        def _exists() -> bool:
            """
            同步检查对象是否存在
            """
            try:
                return self.bucket.object_exists(key)
            except oss2.exceptions.OssError as exc:
                raise StorageError() from exc

        return await anyio.to_thread.run_sync(_exists)

    async def get_url(
        self,
        path: str,
        expires: int = 3600,
        visibility: StorageVisibility | None = None,
    ) -> str:
        """
        获取访问 URL
        """
        key = self._key(path)
        if visibility is None:
            info = await self.get_info(path)
            visibility = info.visibility if info else StorageVisibility.PRIVATE
        if visibility == StorageVisibility.PUBLIC and self.base_url:
            return f"{self.base_url}/{key}"

        def _sign() -> str:
            """
            生成签名 URL
            """
            return self.bucket.sign_url("GET", key, expires)

        return await anyio.to_thread.run_sync(_sign)

    async def get_info(self, path: str) -> Optional[FileInfo]:
        """
        获取对象元信息
        """
        key = self._key(path)

        def _head() -> Optional[FileInfo]:
            """
            同步获取对象头信息
            """
            try:
                meta = self.bucket.get_object_meta(key)
            except oss2.exceptions.NoSuchKey:
                return None
            except oss2.exceptions.OssError as exc:
                raise StorageError() from exc
            headers = meta.headers or {}
            metadata = {
                k[len("x-oss-meta-") :]: v
                for k, v in headers.items()
                if k.lower().startswith("x-oss-meta-")
            }
            visibility_value = metadata.get("visibility", "private")
            return FileInfo(
                path=path,
                size=getattr(meta, "content_length", 0),
                mime_type=getattr(meta, "content_type", None)
                or "application/octet-stream",
                last_modified=getattr(meta, "last_modified", None) or datetime.utcnow(),
                visibility=StorageVisibility(visibility_value),
                metadata=metadata,
            )

        return await anyio.to_thread.run_sync(_head)

    async def copy(self, source: str, destination: str) -> bool:
        """
        复制对象
        """
        src_key = self._key(source)
        dst_key = self._key(destination)

        def _copy() -> bool:
            """
            同步复制对象
            """
            try:
                self.bucket.copy_object(self.bucket_name, src_key, dst_key)
            except oss2.exceptions.OssError as exc:
                raise StorageError() from exc
            return True

        return await anyio.to_thread.run_sync(_copy)

    async def move(self, source: str, destination: str) -> bool:
        """
        移动或重命名对象
        """
        copied = await self.copy(source, destination)
        if not copied:
            return False
        return await self.delete(source)
