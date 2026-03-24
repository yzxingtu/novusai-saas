"""Qiniu Kodo Storage Driver / 说明

New plugin-based driver using qiniu SDK.
Supports imageView2 native image processing."""

from __future__ import annotations

import hashlib
import io
import mimetypes
import tempfile
from datetime import datetime, timezone
from typing import TYPE_CHECKING, BinaryIO

import anyio
import httpx

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
    import qiniu
except ModuleNotFoundError:
    qiniu = None


def _require_qiniu_sdk():
    """Ensure optional qiniu SDK is available before runtime use. / 说明"""
    if qiniu is None:
        raise StorageConfigError(
            message=(
                _(
                    "Qiniu Kodo SDK is not installed. "
                    "Install dependency: pip install qiniu"
                )
            ),
        )
    return qiniu


class KodoStorageDriver(StorageDriver):
    """Qiniu Kodo object storage driver / 说明"""
    name = "qiniu-kodo"
    display_name = "storage.driver.qiniu_kodo"
    config_schema = {
        "type": "object",
        "properties": {
            "root_path": {
                "type": "string",
                "title": "plugin.qiniu-kodo.config.bucket",
            },
            "base_url": {
                "type": "string",
                "title": "plugin.qiniu-kodo.config.base_url",
            },
            "access_key": {
                "type": "string",
                "title": "plugin.qiniu-kodo.config.access_key",
                "x-encrypted": True,
            },
            "secret_key": {
                "type": "string",
                "title": "plugin.qiniu-kodo.config.secret_key",
                "x-encrypted": True,
            },
            "prefix": {
                "type": "string",
                "title": "plugin.qiniu-kodo.config.prefix",
            },
            "is_private": {
                "type": "boolean",
                "title": "plugin.qiniu-kodo.config.is_private",
                "default": False,
            },
        },
        "required": ["root_path", "access_key", "secret_key"],
    }

    MAX_PROCESS_SIZE = 20 * 1024 * 1024  # 20MB / 图像处理上限约 20MB

    def __init__(self, config: StorageConfig):
        super().__init__(config)
        sdk = _require_qiniu_sdk()
        options = config.options or {}
        self.bucket_name = options.get("bucket") or config.root_path
        ak = options.get("access_key")
        sk = options.get("secret_key")
        missing = []
        if not self.bucket_name:
            missing.append("bucket/root_path")
        if not ak:
            missing.append("access_key")
        if not sk:
            missing.append("secret_key")
        if missing:
            raise StorageConfigError(
                message=f"Qiniu Kodo missing required config: {', '.join(missing)}",
            )
        self._sdk = sdk
        self.auth = self._sdk.Auth(ak, sk)
        self.base_url = config.base_url.rstrip("/") if config.base_url else None
        self.prefix = options.get("prefix", "").strip("/")
        self.is_private = bool(options.get("is_private", False))
        self.bucket_manager = self._sdk.BucketManager(self.auth)

    def _key(self, path: str) -> str:
        clean = path.lstrip("/")
        return f"{self.prefix}/{clean}" if self.prefix else clean

    def _validate_visibility(self, visibility: StorageVisibility) -> None:
        if self.is_private and visibility != StorageVisibility.PRIVATE:
            raise StorageConfigError(
                message=(
                    "Qiniu Kodo private buckets only support private attachments. "
                    "Use a public bucket or change attachment visibility."
                ),
            )
        if not self.is_private and visibility != StorageVisibility.PUBLIC:
            raise StorageConfigError(
                message=(
                    "Qiniu Kodo public buckets only support public attachments. "
                    "Use a private bucket or change attachment visibility."
                ),
            )

    async def put(
        self,
        path: str,
        content: BinaryIO,
        mime_type: str | None = None,
        visibility: StorageVisibility = StorageVisibility.PRIVATE,
        metadata: dict | None = None,
    ) -> UploadResult:
        self._validate_visibility(visibility)
        key = self._key(path)
        final_mime_type = mime_type or mimetypes.guess_type(path)[0] or "application/octet-stream"

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
                file_hash = hasher.hexdigest()
                token = self.auth.upload_token(self.bucket_name, key, 3600)
                upload_params = {
                    f"x:{k}": str(v) for k, v in (metadata or {}).items()
                }
                upload_params["x:visibility"] = visibility.value
                ret, info = self._sdk.put_stream(
                    token,
                    key,
                    tmp,
                    size,
                    params=upload_params,
                    mime_type=final_mime_type,
                )
            if info.status_code != 200:
                raise StorageError(
                    message=f"Qiniu upload failed: {info.error} (status={info.status_code})",
                )
            return size, file_hash

        size, file_hash = await anyio.to_thread.run_sync(_upload)
        self.logger.debug("put %s (%d bytes)", path, size)
        return UploadResult(
            path=path,
            url=await self.get_url(path, visibility=visibility),
            size=size,
            hash=file_hash,
            mime_type=final_mime_type,
            driver=self.name,
        )

    async def get(self, path: str) -> BinaryIO:
        url = await self.get_url(path)

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                if response.status_code == 404:
                    raise StorageNotFoundError()
                response.raise_for_status()
                return io.BytesIO(response.content)
        except (StorageNotFoundError, StorageError):
            raise
        except httpx.HTTPStatusError as exc:
            raise StorageError(message=str(exc)) from exc
        except httpx.RequestError as exc:
            raise StorageError(message=str(exc)) from exc

    async def delete(self, path: str) -> bool:
        key = self._key(path)

        def _delete() -> bool:
            ret, info = self.bucket_manager.delete(self.bucket_name, key)
            if info.status_code == 612:
                return False
            if info.status_code != 200:
                raise StorageError(
                    message=f"Qiniu delete failed: status={info.status_code}",
                )
            return True

        result = await anyio.to_thread.run_sync(_delete)
        self.logger.debug("delete %s", path)
        return result

    async def exists(self, path: str) -> bool:
        key = self._key(path)

        def _exists() -> bool:
            ret, info = self.bucket_manager.stat(self.bucket_name, key)
            return info.status_code == 200

        return await anyio.to_thread.run_sync(_exists)

    async def get_url(
        self,
        path: str,
        expires: int = 3600,
        visibility: StorageVisibility | None = None,
    ) -> str:
        key = self._key(path)
        if not self.base_url:
            raise StorageConfigError(
                message="Qiniu Kodo base_url is required for URL generation",
            )
        base = f"{self.base_url}/{key}"
        if self.is_private or (visibility and visibility == StorageVisibility.PRIVATE):
            return self.auth.private_download_url(base, expires=expires)
        return base

    def get_base_url(self) -> str:
        if self.is_private:
            return ""
        return super().get_base_url()

    async def get_info(self, path: str) -> FileInfo | None:
        key = self._key(path)

        def _stat() -> FileInfo | None:
            ret, info = self.bucket_manager.stat(self.bucket_name, key)
            if info.status_code != 200:
                return None
            size = ret.get("fsize", 0)
            mime = ret.get("mimeType", "application/octet-stream")
            put_time = ret.get("putTime", 0)
            last_modified = datetime.fromtimestamp(put_time / 10000000, tz=timezone.utc) if put_time else datetime.now(timezone.utc)
            return FileInfo(
                path=path,
                size=size,
                mime_type=mime,
                last_modified=last_modified,
                visibility=StorageVisibility.PRIVATE if self.is_private else StorageVisibility.PUBLIC,
                metadata={},
            )

        return await anyio.to_thread.run_sync(_stat)

    async def copy(self, source: str, destination: str) -> bool:
        src_key = self._key(source)
        dst_key = self._key(destination)

        def _copy() -> bool:
            ret, info = self.bucket_manager.copy(
                self.bucket_name, src_key,
                self.bucket_name, dst_key,
            )
            return info.status_code == 200

        result = await anyio.to_thread.run_sync(_copy)
        self.logger.debug("copy %s -> %s", source, destination)
        return result

    async def move(self, source: str, destination: str) -> bool:
        src_key = self._key(source)
        dst_key = self._key(destination)

        def _move() -> bool:
            ret, info = self.bucket_manager.move(
                self.bucket_name, src_key,
                self.bucket_name, dst_key,
            )
            return info.status_code == 200

        return await anyio.to_thread.run_sync(_move)

    # ========== Image Processing / 图片处理 ==========

    def _build_kodo_process_params(self, params: ImageProcessParams) -> str:
        """Build Kodo image processing URL suffix. / 说明

        Uses imageView2 for fit/fill/pad; imageMogr2 for crop (center crop)."""
        w = params.width or ""
        h = params.height or ""

        if params.mode == "crop":
            parts: list[str] = ["imageMogr2"]
            if w or h:
                parts.append(f"crop/{w}x{h}/gravity/Center")
            if params.quality and params.quality < 100:
                parts.append(f"quality/{params.quality}")
            if params.format:
                parts.append(f"format/{params.format}")
            return "/".join(parts)

        mode_map = {"fit": 2, "fill": 1, "pad": 2}
        mode = mode_map.get(params.mode, 2)
        parts = [f"imageView2/{mode}"]
        if params.width:
            parts.append(f"w/{params.width}")
        if params.height:
            parts.append(f"h/{params.height}")
        if params.quality and params.quality < 100:
            parts.append(f"q/{params.quality}")
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
        if not self.base_url:
            raise StorageConfigError(
                message="Qiniu Kodo base_url is required for image processing",
            )
        process_str = self._build_kodo_process_params(params)
        base = f"{self.base_url}/{key}?{process_str}"
        if self.is_private or (visibility and visibility == StorageVisibility.PRIVATE):
            return self.auth.private_download_url(base, expires=expires)
        return base

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

    def supports_native_image_processing(
        self,
        visibility: StorageVisibility | None = None,
    ) -> bool:
        _ = visibility
        return True
