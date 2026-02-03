"""
存储驱动管理器
"""

from typing import Dict, Type

from app.exceptions import StorageConfigError
from app.storage.base import StorageConfig, StorageDriver
from app.storage.drivers.local import LocalStorageDriver
from app.storage.drivers.oss import OssStorageDriver
from app.storage.drivers.s3 import S3StorageDriver


class StorageManager:
    """
    存储驱动注册与获取入口
    """
    _instance: "StorageManager | None" = None

    def __new__(cls) -> "StorageManager":
        """
        单例构造
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._drivers = {}
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """
        初始化默认驱动
        """
        if self._initialized:
            return
        self._drivers: Dict[str, Type[StorageDriver]] = {}
        self.register_driver(LocalStorageDriver)
        self.register_driver(S3StorageDriver)
        self.register_driver(OssStorageDriver)
        self._initialized = True

    def register_driver(self, driver_cls: Type[StorageDriver]) -> None:
        """
        注册驱动
        """
        if not driver_cls.name:
            raise StorageConfigError()
        self._drivers[driver_cls.name] = driver_cls

    def get_driver(self, config: StorageConfig) -> StorageDriver:
        """
        根据配置获取驱动实例
        """
        driver_cls = self._drivers.get(config.driver)
        if not driver_cls:
            raise StorageConfigError()
        return driver_cls(config)


storage_manager = StorageManager()


__all__ = ["StorageManager", "storage_manager"]
