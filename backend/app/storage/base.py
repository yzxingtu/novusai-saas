from dataclasses import dataclass, field
from datetime import datetime
from typing import BinaryIO, Optional

from app.enums.base import StrEnum


class StorageVisibility(StrEnum):
    PUBLIC = ("public", "enum.attachment_visibility.public")
    PRIVATE = ("private", "enum.attachment_visibility.private")


@dataclass
class StorageConfig:
    driver: str
    root_path: str
    base_url: Optional[str] = None
    options: dict = field(default_factory=dict)


@dataclass
class UploadResult:
    path: str
    url: str
    size: int
    hash: str
    mime_type: str
    driver: str


@dataclass
class FileInfo:
    path: str
    size: int
    mime_type: str
    last_modified: datetime
    visibility: StorageVisibility
    metadata: dict = field(default_factory=dict)


class StorageDriver:
    name: str = "base"
    display_name: str = "Base Storage"
    config_schema: dict | None = None

    def __init__(self, config: StorageConfig):
        self.config = config

    async def put(
        self,
        path: str,
        content: BinaryIO,
        mime_type: str | None = None,
        visibility: StorageVisibility = StorageVisibility.PRIVATE,
        metadata: dict | None = None,
    ) -> UploadResult:
        raise NotImplementedError()

    async def get(self, path: str) -> BinaryIO:
        raise NotImplementedError()

    async def delete(self, path: str) -> bool:
        raise NotImplementedError()

    async def exists(self, path: str) -> bool:
        raise NotImplementedError()

    async def get_url(
        self,
        path: str,
        expires: int = 3600,
        visibility: StorageVisibility | None = None,
    ) -> str:
        raise NotImplementedError()

    async def get_info(self, path: str) -> Optional[FileInfo]:
        raise NotImplementedError()

    async def copy(self, source: str, destination: str) -> bool:
        raise NotImplementedError()

    async def move(self, source: str, destination: str) -> bool:
        raise NotImplementedError()

    async def get_download_response(self, path: str, filename: str | None = None):
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


__all__ = [
    "StorageVisibility",
    "StorageConfig",
    "UploadResult",
    "FileInfo",
    "StorageDriver",
]
