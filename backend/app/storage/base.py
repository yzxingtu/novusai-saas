"""
存储后端基础类型与抽象接口 / Storage backend base types and abstract interface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, BinaryIO
from urllib.parse import quote

from app.core.logging import StorageLoggerMixin
from app.enums.base import StrEnum

if TYPE_CHECKING:
    from app.utils.image import ImageProcessParams


class StorageVisibility(StrEnum):
    """
    File Visibility Enum / 文件可见性枚举
    """
    PUBLIC = ("public", "enum.attachment_visibility.public")
    PRIVATE = ("private", "enum.attachment_visibility.private")


@dataclass
class StorageConfig:
    """
    Storage Config Object / 存储配置对象
    """
    driver: str
    root_path: str
    base_url: str | None = None
    options: dict = field(default_factory=dict)


@dataclass
class UploadResult:
    """
    Upload Result Object / 上传结果对象
    """
    path: str
    url: str
    size: int
    hash: str
    mime_type: str
    driver: str


@dataclass
class FileInfo:
    """
    File Info Object / 文件信息对象
    """
    path: str
    size: int
    mime_type: str
    last_modified: datetime
    visibility: StorageVisibility
    metadata: dict = field(default_factory=dict)


def build_content_disposition(
    filename: str,
    disposition: str = "attachment",
) -> str:
    """
    Build RFC 5987-compatible Content-Disposition header.
    构建兼容 RFC 5987 的 Content-Disposition 响应头。
    """
    safe_filename = filename.replace("\\", "_").replace('"', "_").strip() or "file"
    try:
        safe_filename.encode("latin-1")
        return f'{disposition}; filename="{safe_filename}"'
    except UnicodeEncodeError:
        suffix = Path(safe_filename).suffix
        fallback = f"file{suffix}" if suffix else "file"
        encoded = quote(safe_filename, safe="")
        return (
            f'{disposition}; filename="{fallback}"; '
            f"filename*=UTF-8''{encoded}"
        )


class StorageDriver(StorageLoggerMixin):
    """
    Storage Driver Abstract Base Class / 存储驱动抽象基类

    Provides self.logger via StorageLoggerMixin, logs to logs/storage.log.
    通过 StorageLoggerMixin 提供 self.logger 属性，日志记录到 logs/storage.log。
    """
    name: str = "base"
    display_name: str = "Base Storage"
    config_schema: dict | None = None

    def __init__(self, config: StorageConfig):
        """
        Initialize driver / 初始化驱动
        """
        self.config = config

    async def put(
        self,
        path: str,
        content: BinaryIO,
        mime_type: str | None = None,
        visibility: StorageVisibility = StorageVisibility.PRIVATE,
        metadata: dict | None = None,
    ) -> UploadResult:
        """
        Upload file / 上传文件
        """
        raise NotImplementedError()

    async def get(self, path: str) -> BinaryIO:
        """
        Get file content / 获取文件内容
        """
        raise NotImplementedError()

    async def delete(self, path: str) -> bool:
        """
        Delete file / 删除文件
        """
        raise NotImplementedError()

    async def exists(self, path: str) -> bool:
        """
        Check if file exists / 判断文件是否存在
        """
        raise NotImplementedError()

    async def get_url(
        self,
        path: str,
        expires: int = 3600,
        visibility: StorageVisibility | None = None,
    ) -> str:
        """
        Get file access URL / 获取文件访问 URL
        """
        raise NotImplementedError()

    async def get_info(self, path: str) -> FileInfo | None:
        """
        Get file info / 获取文件信息
        """
        raise NotImplementedError()

    async def copy(self, source: str, destination: str) -> bool:
        """
        Copy file / 复制文件
        """
        raise NotImplementedError()

    async def move(self, source: str, destination: str) -> bool:
        """
        Move or rename file / 移动或重命名文件
        """
        raise NotImplementedError()

    async def get_download_response(self, path: str, filename: str | None = None):
        """
        Get download response / 获取下载响应
        """
        from fastapi.responses import StreamingResponse

        content = await self.get(path)
        info = await self.get_info(path)
        headers = {}
        if filename:
            headers["Content-Disposition"] = build_content_disposition(filename)
        return StreamingResponse(
            content,
            media_type=info.mime_type if info else "application/octet-stream",
            headers=headers,
        )

    async def get_image_url(
        self,
        path: str,
        params: ImageProcessParams,
        expires: int = 3600,
        visibility: StorageVisibility | None = None,
    ) -> str:
        """
        Get processed image URL / 获取处理后的图片 URL

        Each driver implements per provider spec / 各驱动根据服务商规范实现：
        - LocalDriver: Local processing + cache / 本地处理 + 缓存
        - S3Driver: Return URL with params / 返回带参数的 URL
        - OSSDriver: Return OSS image processing URL / 返回 OSS 图片处理 URL

        Args:
            path: File path / 文件路径
            params: Image processing params / 图片处理参数
            expires: URL expiry (seconds) / URL 有效期（秒）
            visibility: Visibility / 可见性

        Returns:
            Processed image URL / 处理后的图片 URL
        """
        _ = params
        # Default impl: return original URL (no processing) / 默认实现：返回原始 URL（不处理）
        return await self.get_url(path, expires=expires, visibility=visibility)

    async def get_processed_image(
        self,
        path: str,
        params: ImageProcessParams,
    ) -> tuple[bytes, str] | None:
        """
        Get processed image data / 获取处理后的图片数据

        Only for local storage and drivers without native image processing / 仅用于本地存储和无原生图片处理能力的存储驱动

        Args:
            path: File path / 文件路径
            params: Image processing params / 图片处理参数

        Returns:
            (processed bytes, MIME type) or None / (处理后的字节数据, MIME 类型) 或 None
        """
        _ = (path, params)
        # Default impl: return None (not supported locally) / 默认实现：返回 None（表示不支持本地处理）
        return None

    def supports_native_image_processing(
        self,
        visibility: StorageVisibility | None = None,
    ) -> bool:
        """
        Whether native image processing is supported / 是否支持原生图片处理

        Cloud storage returns True (uses cloud service processing) / 云存储返回 True（使用云服务处理）
        Local storage returns False (requires local Pillow processing) / 本地存储返回 False（需要本地 Pillow 处理）

        Returns:
            Whether native image processing is supported / 是否支持原生图片处理
        """
        _ = visibility
        return False

    def get_base_url(self) -> str:
        """
        Get storage base access URL (with prefix) / 获取存储的基础访问 URL（含 prefix）

        Joins config.base_url with driver prefix, ensuring the base_url
        stored in attachment records can be concatenated with path for a full URL / 将 config.base_url 与驱动的 prefix 拼接，确保存入
        附件记录的 base_url 可直接与 path 拼出完整 URL

        Returns:
            Base URL without trailing slash / 基础 URL，不带尾部斜杠
        """
        base_url = (self.config.base_url or "").rstrip("/")
        prefix = getattr(self, "prefix", "").strip("/")
        if prefix and base_url:
            return f"{base_url}/{prefix}"
        return base_url


__all__ = [
    "StorageVisibility",
    "StorageConfig",
    "UploadResult",
    "FileInfo",
    "StorageDriver",
]
