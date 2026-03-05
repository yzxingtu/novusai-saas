"""
Tencent Cloud COS Storage Driver

Plugin-based driver using cos-python-sdk-v5.
Supports imageMogr2 native image processing.
"""

from __future__ import annotations

import hashlib
import mimetypes
import tempfile
from datetime import datetime, timezone
from typing import TYPE_CHECKING, BinaryIO

import anyio

from app.core.i18n import _
from app.exceptions import StorageConfigError, StorageError, StorageNotFoundError
from app.storage.base import (
    FileInfo,
    StorageConfig,
    StorageDriver,
    StorageVisibility,
    UploadResult,
)

if TYPE_CHECKING:
    from app.utils.image import ImageProcessParams

try:
    from qcloud_cos import CosConfig, CosS3Client
    from qcloud_cos.cos_exception import CosServiceError
except ModuleNotFoundError:
    CosConfig = None
    CosS3Client = None

    class CosServiceError(Exception):
        """Fallback error type when COS SDK is unavailable."""


def _require_cos_sdk() -> tuple[type, type]:
    """Ensure optional COS SDK is available before runtime use."""
    if CosConfig is None or CosS3Client is None:
        raise StorageConfigError(
            message=(
                _(
                    "Tencent COS SDK is not installed. "
                    "Install dependency: pip install cos-python-sdk-v5"
                )
            ),
        )
    return CosConfig, CosS3Client


class CosStorageDriver(StorageDriver):
    """
    Tencent Cloud COS object storage driver
    """
    name = "tencent-cos"
    display_name = "storage.driver.tencent_cos"
    config_schema = {
        "type": "object",
        "properties": {
            "root_path": {
                "type": "string",
                "title": "plugin.tencent-cos.config.bucket",
            },
            "base_url": {
                "type": "string",
                "title": "plugin.tencent-cos.config.base_url",
            },
            "secret_id": {
                "type": "string",
                "title": "plugin.tencent-cos.config.secret_id",
                "x-encrypted": True,
            },
            "secret_key": {
                "type": "string",
                "title": "plugin.tencent-cos.config.secret_key",
                "x-encrypted": True,
            },
            "region": {
                "type": "string",
                "title": "plugin.tencent-cos.config.region",
            },
            "prefix": {
                "type": "string",
                "title": "plugin.tencent-cos.config.prefix",
            },
        },
        "required": ["root_path", "secret_id", "secret_key", "region"],
    }

    MAX_PROCESS_SIZE = 32 * 1024 * 1024  # 32MB

    def __init__(self, config: StorageConfig):
        super().__init__(config)
        cos_config_cls, cos_client_cls = _require_cos_sdk()
        options = config.options or {}
        self.bucket_name = options.get("bucket") or config.root_path
        region = options.get("region")
        missing = []
        if not self.bucket_name:
            missing.append("bucket/root_path")
        if not region:
            missing.append("region")
        if missing:
            raise StorageConfigError(
                message=f"Tencent COS missing required config: {', '.join(missing)}",
            )
        self.region = region
        self.base_url = config.base_url.rstrip("/") if config.base_url else None
        self.prefix = options.get("prefix", "").strip("/")
        cos_config = cos_config_cls(
            Region=region,
            SecretId=options.get("secret_id"),
            SecretKey=options.get("secret_key"),
            Scheme="https",
        )
        self.client = cos_client_cls(cos_config)

    def _key(self, path: str) -> str:
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
        key = self._key(path)

        def _upload() -> tuple[int, str]:
            size = 0
            hasher = hashlib.sha256()
            with tempfile.TemporaryFile() as tmp:
                while True:
                    chunk = content.read(8192)
                    if not chunk:
                        break
                    tmp.write(chunk)
                    hasher.update(chunk)
                    size += len(chunk)
                tmp.seek(0)
                extra_args: dict = {}
                final_mime = mime_type or mimetypes.guess_type(path)[0]
                if final_mime:
                    extra_args["ContentType"] = final_mime
                if visibility == StorageVisibility.PUBLIC:
                    extra_args["ACL"] = "public-read"
                user_meta = metadata.copy() if metadata else {}
                user_meta["visibility"] = visibility.value
                if user_meta:
                    extra_args["Metadata"] = {
                        f"x-cos-meta-{k}": str(v) for k, v in user_meta.items()
                    }
                self.client.put_object(
                    Bucket=self.bucket_name,
                    Body=tmp,
                    Key=key,
                    **extra_args,
                )
            return size, hasher.hexdigest()

        size, file_hash = await anyio.to_thread.run_sync(_upload)
        self.logger.debug("put %s (%d bytes)", path, size)
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
        key = self._key(path)

        def _get() -> BinaryIO:
            try:
                response = self.client.get_object(
                    Bucket=self.bucket_name,
                    Key=key,
                )
                return response["Body"].get_raw_stream()
            except CosServiceError as exc:
                if exc.get_error_code() == "NoSuchKey":
                    raise StorageNotFoundError() from exc
                raise StorageError(message=str(exc)) from exc

        return await anyio.to_thread.run_sync(_get)

    async def delete(self, path: str) -> bool:
        key = self._key(path)

        def _delete() -> bool:
            try:
                self.client.delete_object(
                    Bucket=self.bucket_name,
                    Key=key,
                )
            except CosServiceError as exc:
                raise StorageError(message=str(exc)) from exc
            return True

        result = await anyio.to_thread.run_sync(_delete)
        self.logger.debug("delete %s", path)
        return result

    async def exists(self, path: str) -> bool:
        key = self._key(path)

        def _exists() -> bool:
            try:
                self.client.head_object(
                    Bucket=self.bucket_name,
                    Key=key,
                )
                return True
            except CosServiceError:
                return False

        return await anyio.to_thread.run_sync(_exists)

    async def get_url(
        self,
        path: str,
        expires: int = 3600,
        visibility: StorageVisibility | None = None,
    ) -> str:
        key = self._key(path)
        if visibility is None:
            info = await self.get_info(path)
            visibility = info.visibility if info else StorageVisibility.PRIVATE
        if visibility == StorageVisibility.PUBLIC and self.base_url:
            return f"{self.base_url}/{key}"

        def _presign() -> str:
            return self.client.get_presigned_url(
                Method="GET",
                Bucket=self.bucket_name,
                Key=key,
                Expired=expires,
            )

        return await anyio.to_thread.run_sync(_presign)

    async def get_info(self, path: str) -> FileInfo | None:
        key = self._key(path)

        def _head() -> FileInfo | None:
            try:
                response = self.client.head_object(
                    Bucket=self.bucket_name,
                    Key=key,
                )
            except CosServiceError:
                return None
            metadata = {}
            for k, v in response.items():
                lk = k.lower()
                if lk.startswith("x-cos-meta-"):
                    metadata[lk[len("x-cos-meta-"):]] = v
            visibility_value = metadata.get("visibility", "private")
            return FileInfo(
                path=path,
                size=int(response.get("Content-Length", 0)),
                mime_type=response.get("Content-Type", "application/octet-stream"),
                last_modified=datetime.now(timezone.utc),
                visibility=StorageVisibility(visibility_value),
                metadata=metadata,
            )

        return await anyio.to_thread.run_sync(_head)

    async def copy(self, source: str, destination: str) -> bool:
        src_key = self._key(source)
        dst_key = self._key(destination)

        def _copy() -> bool:
            try:
                self.client.copy(
                    Bucket=self.bucket_name,
                    Key=dst_key,
                    CopySource={
                        "Bucket": self.bucket_name,
                        "Key": src_key,
                        "Region": self.region,
                    },
                )
            except CosServiceError as exc:
                raise StorageError(message=str(exc)) from exc
            return True

        result = await anyio.to_thread.run_sync(_copy)
        self.logger.debug("copy %s -> %s", source, destination)
        return result

    async def move(self, source: str, destination: str) -> bool:
        copied = await self.copy(source, destination)
        if not copied:
            return False
        return await self.delete(source)

    # ========== Image Processing ==========

    def _build_cos_process_params(self, params: ImageProcessParams) -> str:
        """Build COS imageMogr2 URL suffix"""
        parts: list[str] = ["imageMogr2"]
        if params.width or params.height:
            w = params.width or ""
            h = params.height or ""
            mode = params.mode or "fit"
            if mode == "fill":
                parts.append(f"thumbnail/{w}x{h}")
                parts.append(f"crop/{w}x{h}/gravity/center")
            elif mode == "crop":
                parts.append(f"cut/{w}x{h}")
            elif mode == "pad":
                parts.append(f"thumbnail/{w}x{h}/pad/1")
            else:
                parts.append(f"thumbnail/{w}x{h}")
        if params.quality and params.quality < 100:
            parts.append(f"quality/{params.quality}")
        if params.format:
            parts.append(f"format/{params.format}")
        return "/".join(parts)

    async def get_image_url(
        self,
        path: str,
        params: ImageProcessParams,
        expires: int = 3600,
        visibility: StorageVisibility | None = None,
    ) -> str:
        if params.is_empty():
            return await self.get_url(path, expires=expires, visibility=visibility)

        info = await self.get_info(path)
        if info and info.size > self.MAX_PROCESS_SIZE:
            return await self.get_url(path, expires=expires, visibility=visibility)

        key = self._key(path)
        process_str = self._build_cos_process_params(params)
        if visibility is None:
            visibility = info.visibility if info else StorageVisibility.PRIVATE
        if visibility == StorageVisibility.PUBLIC and self.base_url:
            return f"{self.base_url}/{key}?{process_str}"

        def _presign() -> str:
            url = self.client.get_presigned_url(
                Method="GET",
                Bucket=self.bucket_name,
                Key=key,
                Expired=expires,
            )
            separator = "&" if "?" in url else "?"
            return f"{url}{separator}{process_str}"

        return await anyio.to_thread.run_sync(_presign)

    async def get_processed_image(
        self,
        path: str,
        params: ImageProcessParams,
    ) -> tuple[bytes, str] | None:
        if params.is_empty():
            return None
        from app.utils.image import ImageProcessor
        source = await self.get(path)
        return await ImageProcessor.process(source, params)

    def supports_native_image_processing(self) -> bool:
        return True
