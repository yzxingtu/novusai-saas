"""
存储驱动导出入口

Cloud drivers (OSS/S3/Kodo/COS) have been migrated to plugins.
Only LocalStorageDriver remains as built-in.
"""

from app.storage.drivers.local import LocalStorageDriver

__all__ = ["LocalStorageDriver"]
