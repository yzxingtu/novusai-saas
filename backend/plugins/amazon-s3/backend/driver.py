"""
Amazon S3 Compatible Storage Driver

Migrated from built-in app.storage.drivers.s3 with identical interface.
Supports AWS S3, MinIO, Cloudflare R2, Backblaze B2, etc.
Optional image processing via Cloudflare Image Resizing or imgproxy.
"""

from __future__ import annotations

import hashlib
import mimetypes
import tempfile
from datetime import datetime, timezone
from typing import TYPE_CHECKING, BinaryIO

import anyio

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
    import boto3
    from botocore.exceptions import ClientError
except ModuleNotFoundError:
    boto3 = None  # type: ignore[assignment]
    ClientError = Exception  # type: ignore[assignment,misc]


def _require_boto3():
    """Ensure optional boto3 SDK is available before runtime use."""
    if boto3 is None:
        raise StorageConfigError(
            message=(
                "boto3 SDK is not installed. "
                "Install dependency: pip install boto3>=1.35"
            ),
        )
    return boto3


class S3StorageDriver(StorageDriver):
    """
    S3 compatible object storage driver (plugin edition)
    """
    name = "s3"
    display_name = "storage.driver.s3"
    config_schema = {
        "type": "object",
        "properties": {
            "root_path": {
                "type": "string",
                "title": "plugin.amazon-s3.config.bucket",
            },
            "base_url": {
                "type": "string",
                "title": "plugin.amazon-s3.config.base_url",
            },
            "access_key_id": {
                "type": "string",
                "title": "plugin.amazon-s3.config.access_key_id",
                "x-encrypted": True,
            },
            "secret_access_key": {
                "type": "string",
                "title": "plugin.amazon-s3.config.secret_access_key",
                "x-encrypted": True,
            },
            "region": {
                "type": "string",
                "title": "plugin.amazon-s3.config.region",
            },
            "endpoint_url": {
                "type": "string",
                "title": "plugin.amazon-s3.config.endpoint_url",
            },
            "prefix": {
                "type": "string",
                "title": "plugin.amazon-s3.config.prefix",
            },
            "image_process_provider": {
                "type": "string",
                "title": "plugin.amazon-s3.config.image_process_provider",
                "enum": ["", "cloudflare", "imgproxy"],
                "default": "",
            },
            "image_process_url": {
                "type": "string",
                "title": "plugin.amazon-s3.config.image_process_url",
                "default": "",
            },
        },
        "required": ["root_path"],
    }

    def __init__(self, config: StorageConfig):
        super().__init__(config)
        options = config.options or {}
        self.bucket = options.get("bucket") or config.root_path
        if not self.bucket:
            raise StorageConfigError(
                message="S3 missing required config: bucket/root_path",
            )
        self.base_url = config.base_url.rstrip("/") if config.base_url else None
        self.prefix = options.get("prefix", "").strip("/")
        _require_boto3()
        self.client = boto3.client(
            "s3",
            aws_access_key_id=options.get("access_key_id"),
            aws_secret_access_key=options.get("secret_access_key"),
            region_name=options.get("region"),
            endpoint_url=options.get("endpoint_url") or None,
        )

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

    def _build_extra_args(
        self,
        path: str,
        mime_type: str | None,
        visibility: StorageVisibility,
        metadata: dict | None,
    ) -> dict:
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
        key = self._key(path)

        def _get() -> BinaryIO:
            try:
                response = self.client.get_object(Bucket=self.bucket, Key=key)
            except ClientError as exc:
                if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey"}:
                    raise StorageNotFoundError() from exc
                raise StorageError(message=str(exc)) from exc
            return response["Body"]

        return await anyio.to_thread.run_sync(_get)

    async def delete(self, path: str) -> bool:
        key = self._key(path)

        def _delete() -> bool:
            try:
                self.client.delete_object(Bucket=self.bucket, Key=key)
            except ClientError as exc:
                raise StorageError(message=str(exc)) from exc
            return True

        result = await anyio.to_thread.run_sync(_delete)
        self.logger.debug("delete %s", path)
        return result

    async def exists(self, path: str) -> bool:
        key = self._key(path)

        def _exists() -> bool:
            try:
                self.client.head_object(Bucket=self.bucket, Key=key)
                return True
            except ClientError as exc:
                if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey"}:
                    return False
                raise StorageError(message=str(exc)) from exc

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
            return self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=expires,
            )

        return await anyio.to_thread.run_sync(_presign)

    async def get_info(self, path: str) -> FileInfo | None:
        key = self._key(path)

        def _head() -> FileInfo | None:
            try:
                response = self.client.head_object(Bucket=self.bucket, Key=key)
            except ClientError as exc:
                if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey"}:
                    return None
                raise StorageError(message=str(exc)) from exc
            metadata = response.get("Metadata", {}) or {}
            visibility_value = metadata.get("visibility", "private")
            return FileInfo(
                path=path,
                size=response.get("ContentLength", 0),
                mime_type=response.get("ContentType") or "application/octet-stream",
                last_modified=response.get("LastModified") or datetime.now(timezone.utc),
                visibility=StorageVisibility(visibility_value),
                metadata=metadata,
            )

        return await anyio.to_thread.run_sync(_head)

    async def copy(self, source: str, destination: str) -> bool:
        src_key = self._key(source)
        dst_key = self._key(destination)

        def _copy() -> bool:
            try:
                self.client.copy_object(
                    Bucket=self.bucket,
                    CopySource={"Bucket": self.bucket, "Key": src_key},
                    Key=dst_key,
                )
            except ClientError as exc:
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

    def _get_image_process_provider(self) -> str | None:
        return self.config.options.get("image_process_provider")

    def _get_image_process_url(self) -> str | None:
        return self.config.options.get("image_process_url")

    def _build_cloudflare_params(self, params: ImageProcessParams) -> str:
        parts: list[str] = []
        if params.width:
            parts.append(f"width={params.width}")
        if params.height:
            parts.append(f"height={params.height}")
        if params.quality:
            parts.append(f"quality={params.quality}")
        if params.format:
            parts.append(f"format={params.format}")
        fit_map = {
            "fit": "contain",
            "fill": "cover",
            "crop": "crop",
            "pad": "pad",
        }
        if params.mode:
            parts.append(f"fit={fit_map.get(params.mode, 'contain')}")
        return ",".join(parts)

    def _build_imgproxy_params(self, params: ImageProcessParams, source_url: str) -> str:
        parts: list[str] = []
        if params.width or params.height:
            mode_map = {
                "fit": "fit",
                "fill": "fill",
                "crop": "crop",
            }
            resize_mode = mode_map.get(params.mode, "fit")
            w = params.width or 0
            h = params.height or 0
            parts.append(f"rs:{resize_mode}:{w}:{h}")
        if params.quality:
            parts.append(f"q:{params.quality}")
        if params.format:
            parts.append(f"f:{params.format}")
        processing = "/".join(parts) if parts else ""
        return f"/{processing}/plain/{source_url}" if processing else f"/plain/{source_url}"

    async def get_image_url(
        self,
        path: str,
        params: ImageProcessParams,
        expires: int = 3600,
        visibility: StorageVisibility | None = None,
    ) -> str:
        if params.is_empty():
            return await self.get_url(path, expires=expires, visibility=visibility)
        provider = self._get_image_process_provider()
        process_url = self._get_image_process_url()
        if provider == "cloudflare" and process_url:
            key = self._key(path)
            cf_params = self._build_cloudflare_params(params)
            return f"{process_url.rstrip('/')}/cdn-cgi/image/{cf_params}/{key}"
        if provider == "imgproxy" and process_url:
            source_url = await self.get_url(path, expires=expires, visibility=visibility)
            imgproxy_path = self._build_imgproxy_params(params, source_url)
            return f"{process_url.rstrip('/')}{imgproxy_path}"
        return await self.get_url(path, expires=expires, visibility=visibility)

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
        provider = self._get_image_process_provider()
        process_url = self._get_image_process_url()
        return bool(provider) and bool(process_url)
