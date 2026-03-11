"""
Storage Driver Export Entry Point
存储驱动导出入口

Cloud drivers (OSS/S3/Kodo/COS) have been migrated to plugins.
Only LocalStorageDriver remains as built-in.
云存储驱动（OSS/S3/Kodo/COS）已迁移至插件。
仅 LocalStorageDriver 作为内置驱动保留。
"""

from app.storage.drivers.local import LocalStorageDriver

__all__ = ["LocalStorageDriver"]
