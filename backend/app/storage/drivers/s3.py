"""
S3 兼容存储驱动实现
"""

import hashlib
import mimetypes
import tempfile
from datetime import datetime
from typing import BinaryIO, Optional

import anyio
import boto3
from botocore.exceptions import ClientError

from app.exceptions import StorageConfigError, StorageError, StorageNotFoundError
from app.storage.base import (
    FileInfo,
    StorageConfig,
    StorageDriver,
    StorageVisibility,
    UploadResult,
)


class S3StorageDriver(StorageDriver):
    """
    S3 兼容对象存储驱动
    """
    name = "s3"
    display_name = "storage.driver.s3"
    config_schema = {
        "type": "object",
        "properties": {
            "root_path": {
                "type": "string",
                "title": "config.storage.s3.bucket",
                "description": "config.storage.s3.bucket_desc",
            },
            "base_url": {
                "type": "string",
                "title": "config.storage.s3.base_url",
                "description": "config.storage.s3.base_url_desc",
            },
            "access_key_id": {
                "type": "string",
                "title": "config.storage.s3.access_key_id",
            },
            "secret_access_key": {
                "type": "string",
                "title": "config.storage.s3.secret_access_key",
            },
            "region": {
                "type": "string",
                "title": "config.storage.s3.region",
            },
            "endpoint_url": {
                "type": "string",
                "title": "config.storage.s3.endpoint_url",
            },
            "prefix": {
                "type": "string",
                "title": "config.storage.s3.prefix",
            },
        },
        "required": ["root_path"],
    }

    def __init__(self, config: StorageConfig):
        """
        初始化 S3 客户端
        """
        super().__init__(config)
        options = config.options or {}
        self.bucket = options.get("bucket") or config.root_path
        if not self.bucket:
            raise StorageConfigError()
        self.base_url = config.base_url.rstrip("/") if config.base_url else None
        self.prefix = options.get("prefix", "").strip("/")
        self.client = boto3.client(
            "s3",
            aws_access_key_id=options.get("access_key_id"),
            aws_secret_access_key=options.get("secret_access_key"),
            region_name=options.get("region"),
            endpoint_url=options.get("endpoint_url"),
        )

    def _key(self, path: str) -> str:
        """
        生成对象存储的 Key
        """
        clean = path.lstrip("/")
        return f"{self.prefix}/{clean}" if self.prefix else clean

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
                self.client.upload_fileobj(
                    tmp,
                    self.bucket,
                    key,
                    ExtraArgs=self._build_extra_args(
                        path, mime_type, visibility, metadata
                    ),
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

    def _build_extra_args(
        self,
        path: str,
        mime_type: str | None,
        visibility: StorageVisibility,
        metadata: dict | None,
    ) -> dict:
        """
        组装上传附加参数
        """
        final_mime_type = mime_type or mimetypes.guess_type(path)[0]
        extra_args: dict = {}
        if final_mime_type:
            extra_args["ContentType"] = final_mime_type
        meta = metadata.copy() if metadata else {}
        meta["visibility"] = visibility.value
        if meta:
            extra_args["Metadata"] = {str(k): str(v) for k, v in meta.items()}
        if visibility == StorageVisibility.PUBLIC:
            extra_args["ACL"] = "public-read"
        return extra_args

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
                response = self.client.get_object(Bucket=self.bucket, Key=key)
            except ClientError as exc:
                if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey"}:
                    raise StorageNotFoundError() from exc
                raise StorageError() from exc
            return response["Body"]

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
                self.client.delete_object(Bucket=self.bucket, Key=key)
            except ClientError as exc:
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
                self.client.head_object(Bucket=self.bucket, Key=key)
                return True
            except ClientError as exc:
                if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey"}:
                    return False
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

        def _presign() -> str:
            """
            生成预签名 URL
            """
            return self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=expires,
            )

        return await anyio.to_thread.run_sync(_presign)

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
                response = self.client.head_object(Bucket=self.bucket, Key=key)
            except ClientError as exc:
                if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey"}:
                    return None
                raise StorageError() from exc
            metadata = response.get("Metadata", {}) or {}
            visibility_value = metadata.get("visibility", "private")
            return FileInfo(
                path=path,
                size=response.get("ContentLength", 0),
                mime_type=response.get("ContentType") or "application/octet-stream",
                last_modified=response.get("LastModified") or datetime.utcnow(),
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
                self.client.copy_object(
                    Bucket=self.bucket,
                    CopySource={"Bucket": self.bucket, "Key": src_key},
                    Key=dst_key,
                )
            except ClientError as exc:
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
