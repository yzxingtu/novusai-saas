"""
存储驱动管理器
"""

from typing import Dict, Type

from app.core.logging import LogManager
from app.exceptions import StorageConfigError
from app.storage.base import StorageConfig, StorageDriver
from app.storage.drivers.local import LocalStorageDriver

logger = LogManager.get_logger("storage")


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
        self._initialized = True

    def register_driver(self, driver_cls: Type[StorageDriver]) -> None:
        """
        注册驱动
        """
        if not driver_cls.name:
            raise StorageConfigError()
        self._drivers[driver_cls.name] = driver_cls
        display = getattr(driver_cls, "display_name", driver_cls.name)
        logger.info("Storage driver registered: %s (%s)", driver_cls.name, display)

    def unregister_driver(self, driver_name: str) -> None:
        """
        注销驱动（插件禁用时调用）
        """
        removed = self._drivers.pop(driver_name, None)
        if removed:
            logger.info("Storage driver unregistered: %s", driver_name)
        else:
            logger.warning("Storage driver unregister skipped (not found): %s", driver_name)

    def get_driver(self, config: StorageConfig) -> StorageDriver:
        """
        根据配置获取驱动实例
        """
        driver_cls = self._drivers.get(config.driver)
        if not driver_cls:
            raise StorageConfigError()
        return driver_cls(config)

    def get_available_drivers(self) -> list[str]:
        """
        获取所有已注册的驱动名称列表（供前端存储配置下拉使用）
        """
        return list(self._drivers.keys())

    def has_driver(self, driver_name: str) -> bool:
        """
        判断指定驱动是否已注册
        """
        return driver_name in self._drivers

    def get_driver_class(self, driver_name: str) -> Type[StorageDriver] | None:
        """
        获取驱动类（供连接测试等场景使用）
        """
        return self._drivers.get(driver_name)

    def get_driver_info_list(self) -> list[dict]:
        """
        获取所有已注册驱动的详细信息（含 display_name + config_schema + is_available）
        """
        result = []
        for name, cls in self._drivers.items():
            result.append({
                "name": name,
                "display_name": getattr(cls, "display_name", name),
                "config_schema": getattr(cls, "config_schema", None),
                "is_builtin": name == "local",
                "is_available": True,
            })
        return result

    def get_all_driver_info_list(
        self,
        known_plugin_drivers: list[dict] | None = None,
    ) -> list[dict]:
        """
        获取所有驱动的详细信息，包含未注册（插件未启用）的驱动

        Args:
            known_plugin_drivers: 从 DB 插件表获取的已知存储驱动列表，
                每项含 name/display_name/plugin_name/plugin_status

        Returns:
            包含 is_available 字段的驱动列表
        """
        registered = self.get_driver_info_list()
        registered_names = {d["name"] for d in registered}

        if known_plugin_drivers:
            # 为已注册的插件驱动补充 plugin_name/plugin_status
            plugin_map = {pd["name"]: pd for pd in known_plugin_drivers}
            for d in registered:
                if d["name"] in plugin_map:
                    d["plugin_name"] = plugin_map[d["name"]].get("plugin_name")
                    d["plugin_status"] = plugin_map[d["name"]].get("plugin_status")

            # 补充未注册（插件未启用）的驱动
            for pd in known_plugin_drivers:
                if pd["name"] not in registered_names:
                    registered.append({
                        "name": pd["name"],
                        "display_name": pd.get("display_name", pd["name"]),
                        "config_schema": None,
                        "is_builtin": False,
                        "is_available": False,
                        "plugin_name": pd.get("plugin_name"),
                        "plugin_status": pd.get("plugin_status"),
                    })

        return registered


storage_manager = StorageManager()


__all__ = ["StorageManager", "storage_manager"]
