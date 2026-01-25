"""
存储后端基础类型与抽象接口
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, BinaryIO, Optional

from app.enums.base import StrEnum

if TYPE_CHECKING:
    from app.utils.image import ImageProcessParams


class StorageVisibility(StrEnum):
    """
    文件可见性枚举
    """
    PUBLIC = ("public", "enum.attachment_visibility.public")
    PRIVATE = ("private", "enum.attachment_visibility.private")


@dataclass
class StorageConfig:
    """
    存储配置对象
    """
    driver: str
    root_path: str
    base_url: Optional[str] = None
    options: dict = field(default_factory=dict)


@dataclass
class UploadResult:
    """
    上传结果对象
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
    文件信息对象
    """
    path: str
    size: int
    mime_type: str
    last_modified: datetime
    visibility: StorageVisibility
    metadata: dict = field(default_factory=dict)


class StorageDriver:
    """
    存储驱动抽象基类
    """
    name: str = "base"
    display_name: str = "Base Storage"
    config_schema: dict | None = None

    def __init__(self, config: StorageConfig):
        """
        初始化驱动
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
        上传文件
        """
        raise NotImplementedError()

    async def get(self, path: str) -> BinaryIO:
        """
        获取文件内容
        """
        raise NotImplementedError()

    async def delete(self, path: str) -> bool:
        """
        删除文件
        """
        raise NotImplementedError()

    async def exists(self, path: str) -> bool:
        """
        判断文件是否存在
        """
        raise NotImplementedError()

    async def get_url(
        self,
        path: str,
        expires: int = 3600,
        visibility: StorageVisibility | None = None,
    ) -> str:
        """
        获取文件访问 URL
        """
        raise NotImplementedError()

    async def get_info(self, path: str) -> Optional[FileInfo]:
        """
        获取文件信息
        """
        raise NotImplementedError()

    async def copy(self, source: str, destination: str) -> bool:
        """
        复制文件
        """
        raise NotImplementedError()

    async def move(self, source: str, destination: str) -> bool:
        """
        移动或重命名文件
        """
        raise NotImplementedError()

    async def get_download_response(self, path: str, filename: str | None = None):
        """
        获取下载响应
        """
        from fastapi.responses import StreamingResponse

        content = await self.get(path)
        info = await self.get_info(path)
        headers = {}
        if filename:
            headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        return StreamingResponse(
            content,
            media_type=info.mime_type if info else "application/octet-stream",
            headers=headers,
        )

    async def get_image_url(
        self,
        path: str,
        params: "ImageProcessParams",
        expires: int = 3600,
        visibility: StorageVisibility | None = None,
    ) -> str:
        """
        获取处理后的图片 URL
        
        各驱动根据服务商规范实现：
        - LocalDriver: 本地处理 + 缓存
        - S3Driver: 返回带参数的 URL
        - OSSDriver: 返回 OSS 图片处理 URL
        
        Args:
            path: 文件路径
            params: 图片处理参数
            expires: URL 有效期（秒）
            visibility: 可见性
        
        Returns:
            处理后的图片 URL
        """
        # 默认实现：返回原始 URL（不处理）
        return await self.get_url(path, expires=expires, visibility=visibility)

    async def get_processed_image(
        self,
        path: str,
        params: "ImageProcessParams",
    ) -> tuple[bytes, str] | None:
        """
        获取处理后的图片数据
        
        仅用于本地存储和无原生图片处理能力的存储驱动
        
        Args:
            path: 文件路径
            params: 图片处理参数
        
        Returns:
            (处理后的字节数据, MIME 类型) 或 None
        """
        # 默认实现：返回 None（表示不支持本地处理）
        return None

    def supports_native_image_processing(self) -> bool:
        """
        是否支持原生图片处理
        
        云存储返回 True（使用云服务处理）
        本地存储返回 False（需要本地 Pillow 处理）
        
        Returns:
            是否支持原生图片处理
        """
        return False


__all__ = [
    "StorageVisibility",
    "StorageConfig",
    "UploadResult",
    "FileInfo",
    "StorageDriver",
]
