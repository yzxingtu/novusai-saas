"""
存储模块入口
"""

from app.storage.base import (
    FileInfo,
    StorageConfig,
    StorageDriver,
    StorageVisibility,
    UploadResult,
)
from app.storage.manager import StorageManager, storage_manager


__all__ = [
    # 基础类型
    "FileInfo",
    "StorageConfig",
    "StorageDriver",
    "StorageVisibility",
    "UploadResult",
    # 管理器
    "StorageManager",
    "storage_manager",
]
