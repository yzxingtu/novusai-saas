"""
Alibaba Cloud OSS Storage Driver (V2 SDK)

Uses alibabacloud-oss-v2 SDK with typed Request objects.
Registered as plugin storage_driver extension via plugin.yaml.
"""

from __future__ import annotations

import hashlib
import io
import mimetypes
import tempfile
from datetime import datetime, timedelta, timezone
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
    import alibabacloud_oss_v2 as oss
except ModuleNotFoundError as exc:  # pragma: no cover - exercised via runtime config
    oss = None  # type: ignore[assignment]
    _OSS_IMPORT_ERROR = exc
else:
    _OSS_IMPORT_ERROR = None


class OssStorageDriver(StorageDriver):
    """
    Alibaba Cloud OSS storage driver (V2 SDK edition)
    """
    name = "aliyun-oss"
    display_name = "storage.driver.aliyun_oss"
    config_schema = {
        "type": "object",
        "properties": {
            "root_path": {
                "type": "string",
                "title": "plugin.aliyun-oss.config.bucket",
            },
            "base_url": {
                "type": "string",
                "title": "plugin.aliyun-oss.config.base_url",
            },
            "access_key_id": {
                "type": "string",
                "title": "plugin.aliyun-oss.config.access_key_id",
                "x-encrypted": True,
            },
            "access_key_secret": {
                "type": "string",
                "title": "plugin.aliyun-oss.config.access_key_secret",
                "x-encrypted": True,
            },
            "endpoint": {
                "type": "string",
                "title": "plugin.aliyun-oss.config.endpoint",
            },
            "region": {
                "type": "string",
                "title": "plugin.aliyun-oss.config.region",
            },
            "prefix": {
                "type": "string",
                "title": "plugin.aliyun-oss.config.prefix",
            },
        },
        "required": ["root_path", "access_key_id", "access_key_secret"],
    }

    MAX_PROCESS_SIZE = 20 * 1024 * 1024  # 20MB

    def __init__(self, config: StorageConfig):
        super().__init__(config)
        if oss is None:
            raise StorageConfigError(
                message=(
                    "Aliyun OSS SDK is not installed. "
                    "Install 'alibabacloud-oss-v2' to enable this driver."
                ),
            ) from _OSS_IMPORT_ERROR
        options = config.options or {}
        self.bucket_name = options.get("bucket") or config.root_path
        endpoint = options.get("endpoint")
        region = options.get("region", "")
        ak = options.get("access_key_id")
        sk = options.get("access_key_secret")
        missing = []
        if not self.bucket_name:
            missing.append("bucket/root_path")
        if not ak:
            missing.append("access_key_id")
        if not sk:
            missing.append("access_key_secret")
        if missing:
            raise StorageConfigError(
                message=f"Aliyun OSS missing required config: {', '.join(missing)}",
            )
        if not endpoint and not region:
            raise StorageConfigError(
                message="Aliyun OSS requires either 'endpoint' or 'region'",
            )
        self.base_url = config.base_url.rstrip("/") if config.base_url else None
        self.prefix = options.get("prefix", "").strip("/")

        credentials_provider = oss.credentials.StaticCredentialsProvider(
            access_key_id=ak,
            access_key_secret=sk,
        )
        cfg = oss.config.load_default()
        cfg.credentials_provider = credentials_provider
        if region:
            cfg.region = region
        if endpoint:
            cfg.endpoint = endpoint
        self.client = oss.Client(cfg)

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
        final_mime_type = mime_type or mimetypes.guess_type(path)[0]

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

                meta_dict: dict[str, str] = {}
                if metadata:
                    meta_dict.update({k: str(v) for k, v in metadata.items()})
                meta_dict["visibility"] = visibility.value

                acl = "public-read" if visibility == StorageVisibility.PUBLIC else None

                self.client.put_object(oss.PutObjectRequest(
                    bucket=self.bucket_name,
                    key=key,
                    body=tmp,
                    content_type=final_mime_type,
                    acl=acl,
                    metadata=meta_dict,
                ))
            return size, hasher.hexdigest()

        size, file_hash = await anyio.to_thread.run_sync(_upload)
        self.logger.debug("put %s (%d bytes)", path, size)
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
                result = self.client.get_object(oss.GetObjectRequest(
                    bucket=self.bucket_name,
                    key=key,
                ))
                data = result.body.content
                return io.BytesIO(data)
            except oss.exceptions.OperationError as exc:
                se = exc.unwrap()
                if hasattr(se, "code") and se.code == "NoSuchKey":
                    raise StorageNotFoundError() from exc
                raise StorageError(message=str(exc)) from exc

        return await anyio.to_thread.run_sync(_get)

    async def delete(self, path: str) -> bool:
        key = self._key(path)

        def _delete() -> bool:
            try:
                self.client.delete_object(oss.DeleteObjectRequest(
                    bucket=self.bucket_name,
                    key=key,
                ))
            except oss.exceptions.OperationError as exc:
                raise StorageError(message=str(exc)) from exc
            return True

        result = await anyio.to_thread.run_sync(_delete)
        self.logger.debug("delete %s", path)
        return result

    async def exists(self, path: str) -> bool:
        key = self._key(path)

        def _exists() -> bool:
            try:
                return self.client.is_object_exist(
                    bucket=self.bucket_name,
                    key=key,
                )
            except oss.exceptions.OperationError as exc:
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

        def _sign() -> str:
            pre = self.client.presign(
                oss.GetObjectRequest(
                    bucket=self.bucket_name,
                    key=key,
                ),
                expires=timedelta(seconds=expires),
            )
            return pre.url

        return await anyio.to_thread.run_sync(_sign)

    async def get_info(self, path: str) -> FileInfo | None:
        key = self._key(path)

        def _head() -> FileInfo | None:
            try:
                result = self.client.head_object(oss.HeadObjectRequest(
                    bucket=self.bucket_name,
                    key=key,
                ))
            except oss.exceptions.OperationError:
                return None

            user_meta: dict[str, str] = {}
            if hasattr(result, "metadata") and result.metadata:
                user_meta = dict(result.metadata)
            visibility_value = user_meta.get("visibility", "private")

            last_mod = result.last_modified or datetime.now(timezone.utc)

            return FileInfo(
                path=path,
                size=result.content_length or 0,
                mime_type=result.content_type or "application/octet-stream",
                last_modified=last_mod,
                visibility=StorageVisibility(visibility_value),
                metadata=user_meta,
            )

        return await anyio.to_thread.run_sync(_head)

    async def copy(self, source: str, destination: str) -> bool:
        src_key = self._key(source)
        dst_key = self._key(destination)

        def _copy() -> bool:
            try:
                self.client.copy_object(oss.CopyObjectRequest(
                    bucket=self.bucket_name,
                    key=dst_key,
                    source_bucket=self.bucket_name,
                    source_key=src_key,
                ))
            except oss.exceptions.OperationError as exc:
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

    # ========== Image Processing / 图片处理 ==========

    def _build_oss_process_params(self, params: ImageProcessParams) -> str:
        operations: list[str] = []
        resize_parts: list[str] = []
        if params.width:
            resize_parts.append(f"w_{params.width}")
        if params.height:
            resize_parts.append(f"h_{params.height}")
        if resize_parts:
            mode_map = {
                "fit": "m_lfit",
                "fill": "m_fill",
                "crop": "m_fill",
                "pad": "m_pad",
            }
            mode = mode_map.get(params.mode, "m_lfit")
            resize_parts.append(mode)
            operations.append("resize," + ",".join(resize_parts))
        if params.quality and params.quality < 100:
            operations.append(f"quality,q_{params.quality}")
        if params.format:
            fmt = params.format
            if fmt == "jpeg":
                fmt = "jpg"
            operations.append(f"format,{fmt}")
        if not operations:
            return ""
        return "image/" + "/".join(operations)

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
        process_params = self._build_oss_process_params(params)
        if visibility is None:
            visibility = info.visibility if info else StorageVisibility.PRIVATE
        if visibility == StorageVisibility.PUBLIC and self.base_url:
            return f"{self.base_url}/{key}?x-oss-process={process_params}"

        def _sign() -> str:
            pre = self.client.presign(
                oss.GetObjectRequest(
                    bucket=self.bucket_name,
                    key=key,
                    process=process_params,
                ),
                expires=timedelta(seconds=expires),
            )
            return pre.url

        return await anyio.to_thread.run_sync(_sign)

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
