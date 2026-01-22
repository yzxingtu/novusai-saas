"""
配置注册中心

提供配置分组和配置项的注册、查询功能
采用单例模式，确保全局唯一
"""

import logging
from threading import Lock
from typing import Any

from app.configs.meta import ConfigGroupMeta, ConfigMeta
from app.enums.config import ConfigScope

logger = logging.getLogger(__name__)


class ConfigRegistry:
    """
    配置注册中心（单例）
    
    用于注册和管理所有配置分组及配置项的元数据
    
    Usage:
        # 获取注册中心实例
        registry = ConfigRegistry()
        
        # 注册分组
        registry.register_group(platform_basic_group)
        
        # 查询配置
        config = registry.get_config("platform_basic", "site_name")
        
        # 获取所有平台配置
        groups = registry.get_groups_by_scope(ConfigScope.PLATFORM)
    """
    
    _instance: "ConfigRegistry | None" = None
    _lock: Lock = Lock()
    
    def __new__(cls) -> "ConfigRegistry":
        """单例模式实现"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self) -> None:
        """初始化注册中心"""
        if self._initialized:
            return
        
        # 分组注册表: {group_code: ConfigGroupMeta}
        self._groups: dict[str, ConfigGroupMeta] = {}
        
        # 配置项索引: {group_code: {config_key: ConfigMeta}}
        self._configs: dict[str, dict[str, ConfigMeta]] = {}
        
        # 作用域索引: {scope: [group_code, ...]}
        self._scope_groups: dict[str, list[str]] = {
            ConfigScope.PLATFORM.value: [],
            ConfigScope.TENANT.value: [],
        }
        
        self._initialized = True
        logger.debug("ConfigRegistry initialized")
    
    def register_group(self, group: ConfigGroupMeta) -> None:
        """
        注册配置分组
        
        Args:
            group: 配置分组元数据
            
        Raises:
            ValueError: 分组代码已存在
        """
        if group.code in self._groups:
            raise ValueError(f"Config group '{group.code}' already registered")
        
        # 注册分组
        self._groups[group.code] = group
        
        # 注册到作用域索引
        scope_key = group.scope.value
        if group.code not in self._scope_groups[scope_key]:
            self._scope_groups[scope_key].append(group.code)
        
        # 注册配置项
        self._configs[group.code] = {}
        for config in group.configs:
            self._configs[group.code][config.key] = config
        
        # 递归注册子分组
        for child in group.children:
            child.parent_code = group.code
            self.register_group(child)
        
        logger.debug(f"Registered config group: {group.code} with {len(group.configs)} configs")
    
    def register_groups(self, groups: list[ConfigGroupMeta]) -> None:
        """批量注册配置分组"""
        for group in groups:
            self.register_group(group)
    
    def unregister_group(self, group_code: str) -> None:
        """
        取消注册配置分组
        
        Args:
            group_code: 分组代码
        """
        if group_code not in self._groups:
            return
        
        group = self._groups[group_code]
        
        # 递归取消子分组
        for child in group.children:
            self.unregister_group(child.code)
        
        # 从作用域索引移除
        scope_key = group.scope.value
        if group_code in self._scope_groups[scope_key]:
            self._scope_groups[scope_key].remove(group_code)
        
        # 移除配置项索引
        if group_code in self._configs:
            del self._configs[group_code]
        
        # 移除分组
        del self._groups[group_code]
        
        logger.debug(f"Unregistered config group: {group_code}")
    
    def get_group(self, group_code: str) -> ConfigGroupMeta | None:
        """
        获取配置分组
        
        Args:
            group_code: 分组代码
            
        Returns:
            配置分组元数据，不存在返回 None
        """
        return self._groups.get(group_code)
    
    def get_config(self, group_code: str, config_key: str) -> ConfigMeta | None:
        """
        获取配置项
        
        Args:
            group_code: 分组代码
            config_key: 配置键名
            
        Returns:
            配置项元数据，不存在返回 None
        """
        group_configs = self._configs.get(group_code, {})
        return group_configs.get(config_key)
    
    def get_config_by_key(self, config_key: str) -> ConfigMeta | None:
        """
        根据键名查找配置项（跨分组）
        
        Args:
            config_key: 配置键名
            
        Returns:
            配置项元数据，不存在返回 None
        """
        for group_configs in self._configs.values():
            if config_key in group_configs:
                return group_configs[config_key]
        return None
    
    def get_groups_by_scope(self, scope: ConfigScope) -> list[ConfigGroupMeta]:
        """
        根据作用域获取配置分组列表
        
        Args:
            scope: 作用域
            
        Returns:
            配置分组列表（已按 sort_order 排序）
        """
        group_codes = self._scope_groups.get(scope.value, [])
        groups = [
            self._groups[code] 
            for code in group_codes 
            if code in self._groups and self._groups[code].parent_code == ""
        ]
        return sorted(groups, key=lambda g: g.sort_order)
    
    def get_all_groups(self) -> list[ConfigGroupMeta]:
        """获取所有顶级配置分组"""
        return [g for g in self._groups.values() if g.parent_code == ""]
    
    def get_all_configs(self) -> list[ConfigMeta]:
        """获取所有配置项"""
        configs = []
        for group_configs in self._configs.values():
            configs.extend(group_configs.values())
        return configs
    
    def get_configs_by_scope(self, scope: ConfigScope) -> list[ConfigMeta]:
        """根据作用域获取所有配置项"""
        configs = []
        for group in self.get_groups_by_scope(scope):
            configs.extend(group.get_all_configs())
        return configs
    
    def has_group(self, group_code: str) -> bool:
        """检查分组是否存在"""
        return group_code in self._groups
    
    def has_config(self, group_code: str, config_key: str) -> bool:
        """检查配置项是否存在"""
        return (
            group_code in self._configs 
            and config_key in self._configs[group_code]
        )
    
    def clear(self) -> None:
        """清空所有注册（仅用于测试）"""
        self._groups.clear()
        self._configs.clear()
        self._scope_groups = {
            ConfigScope.PLATFORM.value: [],
            ConfigScope.TENANT.value: [],
        }
        logger.debug("ConfigRegistry cleared")
    
    def to_dict(self) -> dict[str, Any]:
        """导出为字典（用于调试）"""
        return {
            "groups": {code: group.to_dict() for code, group in self._groups.items()},
            "scope_groups": self._scope_groups,
        }


# 全局注册中心实例
config_registry = ConfigRegistry()


def get_config_registry() -> ConfigRegistry:
    """获取配置注册中心实例"""
    return config_registry


__all__ = [
    "ConfigRegistry",
    "config_registry",
    "get_config_registry",
]
