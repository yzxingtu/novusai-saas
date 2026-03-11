"""
Configuration registry / 配置注册中心

Provides registration and query functionality for config groups and items.
Uses singleton pattern to ensure global uniqueness.
提供配置分组和配置项的注册、查询功能
采用单例模式，确保全局唯一
"""

from threading import Lock
from typing import Any

from app.configs.meta import ConfigGroupMeta, ConfigMeta, ConfigOption
from app.core.logging import LogManager
from app.enums.config import ConfigScope

logger = LogManager.get_logger("app")


class ConfigRegistry:
    """
    Configuration registry (singleton) / 配置注册中心（单例）

    Registers and manages all config groups and items metadata.
    用于注册和管理所有配置分组及配置项的元数据

    Usage:
        # Get registry instance / 获取注册中心实例
        registry = ConfigRegistry()

        # Register group / 注册分组
        registry.register_group(platform_basic_group)

        # Query config / 查询配置
        config = registry.get_config("platform_basic", "site_name")

        # Get all platform configs / 获取所有平台配置
        groups = registry.get_groups_by_scope(ConfigScope.ADMIN_ONLY)
    """

    _instance: "ConfigRegistry | None" = None
    _lock: Lock = Lock()

    def __new__(cls) -> "ConfigRegistry":
        """Singleton pattern implementation / 单例模式实现"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """Initialize registry / 初始化注册中心"""
        if self._initialized:
            return

        # Group registry: {group_code: ConfigGroupMeta} / 分组注册表
        self._groups: dict[str, ConfigGroupMeta] = {}

        # Config item index: {group_code: {config_key: ConfigMeta}} / 配置项索引
        self._configs: dict[str, dict[str, ConfigMeta]] = {}

        # Scope index: {scope: [group_code, ...]} / 作用域索引
        self._scope_groups: dict[str, list[str]] = {
            ConfigScope.ADMIN_ONLY.value: [],
            ConfigScope.ALL_TENANTS.value: [],
        }

        self._initialized = True
        logger.debug("ConfigRegistry initialized")

    def register_group(self, group: ConfigGroupMeta) -> None:
        """Register config group / 注册配置分组

        Args:
            group: Config group metadata / 配置分组元数据

        Raises:
            ValueError: Group code already exists / 分组代码已存在
        """
        if group.code in self._groups:
            raise ValueError(f"Config group '{group.code}' already registered")

        # Register group / 注册分组
        self._groups[group.code] = group

        # Register to scope index / 注册到作用域索引
        scope_key = group.scope.value
        if group.code not in self._scope_groups[scope_key]:
            self._scope_groups[scope_key].append(group.code)

        # Register config items / 注册配置项
        self._configs[group.code] = {}
        for config in group.configs:
            self._configs[group.code][config.key] = config

        # Recursively register child groups / 递归注册子分组
        for child in group.children:
            child.parent_code = group.code
            self.register_group(child)

        logger.debug(f"Registered config group: {group.code} with {len(group.configs)} configs")

    def register_groups(self, groups: list[ConfigGroupMeta]) -> None:
        """Batch register config groups / 批量注册配置分组"""
        for group in groups:
            self.register_group(group)

    def unregister_group(self, group_code: str) -> None:
        """Unregister config group / 取消注册配置分组

        Args:
            group_code: Group code / 分组代码
        """
        if group_code not in self._groups:
            return

        group = self._groups[group_code]

        # Recursively unregister child groups / 递归取消子分组
        for child in group.children:
            self.unregister_group(child.code)

        # Remove from scope index / 从作用域索引移除
        scope_key = group.scope.value
        if group_code in self._scope_groups[scope_key]:
            self._scope_groups[scope_key].remove(group_code)

        # Remove config item index / 移除配置项索引
        if group_code in self._configs:
            del self._configs[group_code]

        # Remove group / 移除分组
        del self._groups[group_code]

        logger.debug(f"Unregistered config group: {group_code}")

    def add_option(self, config_key: str, option: ConfigOption) -> bool:
        """Add option to config item / 向配置项添加选项
        向指定配置项动态追加选项（插件启用时注入驱动选项）

        Args:
            config_key: 配置键名（跨分组查找）
            option: 要追加的 ConfigOption

        Returns:
            True=成功追加, False=配置项不存在
        """
        config = self.get_config_by_key(config_key)
        if not config:
            logger.warning(f"add_option: config key '{config_key}' not found")
            return False

        # 避免重复添加
        existing_values = {opt.value for opt in config.options}
        if option.value in existing_values:
            logger.debug(f"add_option: option '{option.value}' already exists in '{config_key}'")
            return True

        config.options.append(option)
        logger.info(f"add_option: added '{option.value}' to config '{config_key}'")
        return True

    def remove_option(self, config_key: str, option_value: Any) -> bool:
        """Remove option from config item (revoke driver option on plugin disable)
        从指定配置项移除选项（插件禁用时撤回驱动选项）

        Args:
            config_key: Config key / 配置键名
            option_value: Option value to remove / 要移除的选项值

        Returns:
            True=removed, False=config or option not found
            True=成功移除, False=配置项不存在或选项不存在
        """
        config = self.get_config_by_key(config_key)
        if not config:
            logger.warning(f"remove_option: config key '{config_key}' not found")
            return False

        original_len = len(config.options)
        config.options = [opt for opt in config.options if opt.value != option_value]

        if len(config.options) < original_len:
            logger.info(f"remove_option: removed '{option_value}' from config '{config_key}'")
            return True

        logger.debug(f"remove_option: option '{option_value}' not found in '{config_key}'")
        return False

    def get_group(self, group_code: str) -> ConfigGroupMeta | None:
        """Get config group / 获取配置分组

        Args:
            group_code: Group code / 分组代码

        Returns:
            Config group metadata, or None if not found / 配置分组元数据，不存在返回 None
        """
        return self._groups.get(group_code)

    def get_config(self, group_code: str, config_key: str) -> ConfigMeta | None:
        """Get config item / 获取配置项

        Args:
            group_code: Group code / 分组代码
            config_key: Config key / 配置键名

        Returns:
            Config item metadata, or None if not found / 配置项元数据，不存在返回 None
        """
        group_configs = self._configs.get(group_code, {})
        return group_configs.get(config_key)

    def get_config_by_key(self, config_key: str) -> ConfigMeta | None:
        """Find config item by key (cross-group) / 根据键名查找配置项（跨分组）

        Args:
            config_key: Config key / 配置键名

        Returns:
            Config item metadata, or None if not found / 配置项元数据，不存在返回 None
        """
        for group_configs in self._configs.values():
            if config_key in group_configs:
                return group_configs[config_key]
        return None

    def get_groups_by_scope(self, scope: ConfigScope) -> list[ConfigGroupMeta]:
        """Get config groups by scope / 根据作用域获取配置分组列表

        Args:
            scope: Scope / 作用域

        Returns:
            Config group list (sorted by sort_order) / 配置分组列表（已按 sort_order 排序）
        """
        group_codes = self._scope_groups.get(scope.value, [])
        groups = [
            self._groups[code]
            for code in group_codes
            if code in self._groups and self._groups[code].parent_code == ""
        ]
        return sorted(groups, key=lambda g: g.sort_order)

    def get_all_groups(self) -> list[ConfigGroupMeta]:
        """Get all top-level config groups / 获取所有顶级配置分组"""
        return [g for g in self._groups.values() if g.parent_code == ""]

    def get_all_configs(self) -> list[ConfigMeta]:
        """Get all config items / 获取所有配置项"""
        configs = []
        for group_configs in self._configs.values():
            configs.extend(group_configs.values())
        return configs

    def get_configs_by_scope(self, scope: ConfigScope) -> list[ConfigMeta]:
        """Get all config items by scope / 根据作用域获取所有配置项"""
        configs = []
        for group in self.get_groups_by_scope(scope):
            configs.extend(group.get_all_configs())
        return configs

    def has_group(self, group_code: str) -> bool:
        """Check if group exists / 检查分组是否存在"""
        return group_code in self._groups

    def has_config(self, group_code: str, config_key: str) -> bool:
        """Check if config item exists / 检查配置项是否存在"""
        return (
            group_code in self._configs
            and config_key in self._configs[group_code]
        )

    def clear(self) -> None:
        """Clear all registrations (for testing only) / 清空所有注册（仅用于测试）"""
        self._groups.clear()
        self._configs.clear()
        self._scope_groups = {
            ConfigScope.ADMIN_ONLY.value: [],
            ConfigScope.ALL_TENANTS.value: [],
        }
        logger.debug("ConfigRegistry cleared")

    def to_dict(self) -> dict[str, Any]:
        """Export as dict (for debugging) / 导出为字典（用于调试）"""
        return {
            "groups": {code: group.to_dict() for code, group in self._groups.items()},
            "scope_groups": self._scope_groups,
        }


# Global registry instance / 全局注册中心实例
config_registry = ConfigRegistry()


def get_config_registry() -> ConfigRegistry:
    """Get config registry instance / 获取配置注册中心实例"""
    return config_registry


__all__ = [
    "ConfigRegistry",
    "config_registry",
    "get_config_registry",
]
