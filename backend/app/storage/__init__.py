"""
存储模块入口
"""

from pathlib import Path

from app.storage.base import (
    FileInfo,
    StorageConfig,
    StorageDriver,
    StorageVisibility,
    UploadResult,
)
from app.storage.manager import StorageManager, storage_manager

# 本地存储硬编码路径（相对于项目根目录）
_PROJECT_ROOT = Path(__file__).parent.parent.parent
LOCAL_STORAGE_ROOT = _PROJECT_ROOT / "storage" / "uploads"
LOCAL_IMAGE_CACHE_ROOT = _PROJECT_ROOT / "storage" / "cache" / "images"


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
    # 本地存储路径常量
    "LOCAL_STORAGE_ROOT",
    "LOCAL_IMAGE_CACHE_ROOT",
]
