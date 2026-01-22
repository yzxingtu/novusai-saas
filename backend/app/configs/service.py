"""
配置读写服务

提供配置的 CRUD 操作，支持平台配置和租户配置
"""

import json
import logging
from typing import Any

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.configs.meta import ConfigGroupMeta, ConfigMeta
from app.configs.registry import ConfigRegistry, config_registry
from app.enums.config import ConfigScope
from app.models.system.config import (
    SystemConfig,
    SystemConfigGroup,
    SystemConfigValue,
)

logger = logging.getLogger(__name__)

# 平台级配置使用 tenant_id = 0
PLATFORM_TENANT_ID = 0


class ConfigService:
    """
    配置读写服务
    
    提供配置值的读取和写入功能
    
    Usage:
        service = ConfigService(db)
        
        # 获取平台配置
        value = await service.get_platform_config("site_name")
        
        # 设置平台配置
        await service.set_platform_config("site_name", "My SaaS")
        
        # 获取租户配置（会回退到平台默认值）
        value = await service.get_tenant_config(tenant_id, "theme_color")
    """
    
    def __init__(
        self,
        db: AsyncSession,
        registry: ConfigRegistry | None = None,
    ):
        """
        初始化服务
        
        Args:
            db: 数据库会话
            registry: 配置注册中心，默认使用全局实例
        """
        self.db = db
        self.registry = registry or config_registry
    
    # ==========================================
    # 平台配置操作
    # ==========================================
    
    async def get_platform_config(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        """
        获取平台配置值
        
        Args:
            key: 配置键名
            default: 默认值（如果配置不存在）
            
        Returns:
            配置值（已反序列化）
        """
        return await self._get_config_value(
            key=key,
            tenant_id=PLATFORM_TENANT_ID,
            scope=ConfigScope.PLATFORM,
            default=default,
        )
    
    async def set_platform_config(
        self,
        key: str,
        value: Any,
    ) -> None:
        """
        设置平台配置值
        
        Args:
            key: 配置键名
            value: 配置值
        """
        await self._set_config_value(
            key=key,
            tenant_id=PLATFORM_TENANT_ID,
            value=value,
        )
    
    async def get_platform_configs_by_group(
        self,
        group_code: str,
    ) -> dict[str, Any]:
        """
        获取平台配置分组下的所有配置值
        
        Args:
            group_code: 分组代码
            
        Returns:
            {config_key: value, ...}
        """
        return await self._get_configs_by_group(
            group_code=group_code,
            tenant_id=PLATFORM_TENANT_ID,
        )
    
    # ==========================================
    # 租户配置操作
    # ==========================================
    
    async def get_tenant_config(
        self,
        tenant_id: int,
        key: str,
        default: Any = None,
    ) -> Any:
        """
        获取租户配置值
        
        如果租户未设置该配置，会依次回退：
        1. 租户设置的值
        2. 平台设置的默认值（对于 tenant 作用域的配置）
        3. 代码定义的默认值
        4. 传入的 default 参数
        
        Args:
            tenant_id: 租户 ID
            key: 配置键名
            default: 默认值
            
        Returns:
            配置值（已反序列化）
        """
        # 先尝试获取租户设置的值
        value = await self._get_config_value(
            key=key,
            tenant_id=tenant_id,
            scope=ConfigScope.TENANT,
            default=None,
            skip_default=True,
        )
        
        if value is not None:
            return value
        
        # 回退到配置元数据的默认值
        config_meta = self.registry.get_config_by_key(key)
        if config_meta and config_meta.default_value is not None:
            return config_meta.default_value
        
        return default
    
    async def set_tenant_config(
        self,
        tenant_id: int,
        key: str,
        value: Any,
    ) -> None:
        """
        设置租户配置值
        
        Args:
            tenant_id: 租户 ID
            key: 配置键名
            value: 配置值
        """
        await self._set_config_value(
            key=key,
            tenant_id=tenant_id,
            value=value,
        )
    
    async def get_tenant_configs_by_group(
        self,
        tenant_id: int,
        group_code: str,
    ) -> dict[str, Any]:
        """
        获取租户配置分组下的所有配置值
        
        Args:
            tenant_id: 租户 ID
            group_code: 分组代码
            
        Returns:
            {config_key: value, ...}
        """
        return await self._get_configs_by_group(
            group_code=group_code,
            tenant_id=tenant_id,
        )
    
    async def ensure_tenant_configs(self, tenant_id: int) -> int:
        """
        确保租户配置已初始化
        
        为租户创建所有 tenant 作用域配置的默认值记录
        
        Args:
            tenant_id: 租户 ID
            
        Returns:
            创建的配置值数量
        """
        created_count = 0
        
        # 获取所有租户作用域的配置
        tenant_configs = self.registry.get_configs_by_scope(ConfigScope.TENANT)
        
        for config_meta in tenant_configs:
            # 检查是否已有值
            config_id = await self._get_config_id(config_meta.key)
            if not config_id:
                continue
            
            existing = await self.db.execute(
                select(SystemConfigValue).where(
                    and_(
                        SystemConfigValue.config_id == config_id,
                        SystemConfigValue.tenant_id == tenant_id,
                        SystemConfigValue.is_deleted == False,
                    )
                )
            )
            
            if existing.scalar_one_or_none():
                continue
            
            # 创建默认值记录
            default_value = self._serialize_value(config_meta.default_value)
            value_record = SystemConfigValue(
                config_id=config_id,
                tenant_id=tenant_id,
                value=default_value,
            )
            self.db.add(value_record)
            created_count += 1
        
        if created_count > 0:
            await self.db.flush()
            logger.info(f"Created {created_count} config values for tenant {tenant_id}")
        
        return created_count
    
    # ==========================================
    # 批量获取（含元数据）
    # ==========================================
    
    async def get_configs_with_meta(
        self,
        scope: ConfigScope,
        tenant_id: int | None = None,
        group_code: str | None = None,
    ) -> list[dict]:
        """
        获取配置列表（含元数据）
        
        Args:
            scope: 作用域
            tenant_id: 租户 ID（租户作用域时必填）
            group_code: 分组代码（可选，为空则返回所有）
            
        Returns:
            配置列表，每项包含：
            - key: 配置键
            - name_key: 名称 i18n 键
            - description_key: 描述 i18n 键
            - value_type: 值类型
            - value: 当前值
            - default_value: 默认值
            - options: 选项列表
            - is_required: 是否必填
            - is_encrypted: 是否加密
            - group_code: 分组代码
        """
        actual_tenant_id = PLATFORM_TENANT_ID if scope == ConfigScope.PLATFORM else tenant_id
        
        # 获取分组
        if group_code:
            groups = [self.registry.get_group(group_code)]
            groups = [g for g in groups if g]
        else:
            groups = self.registry.get_groups_by_scope(scope)
        
        result = []
        
        for group in groups:
            configs = group.configs
            for config_meta in configs:
                if not config_meta.is_visible:
                    continue
                
                # 获取当前值
                value = await self._get_config_value(
                    key=config_meta.key,
                    tenant_id=actual_tenant_id,
                    scope=scope,
                    default=config_meta.default_value,
                )
                
                result.append({
                    "key": config_meta.key,
                    "name_key": config_meta.name_key,
                    "description_key": config_meta.description_key,
                    "value_type": config_meta.value_type.value,
                    "value": value,
                    "default_value": config_meta.default_value,
                    "options": [opt.to_dict() for opt in config_meta.options],
                    "validation_rules": [rule.to_dict() for rule in config_meta.validation_rules],
                    "is_required": config_meta.is_required,
                    "is_encrypted": config_meta.is_encrypted,
                    "group_code": config_meta.group_code,
                    "sort_order": config_meta.sort_order,
                })
        
        return sorted(result, key=lambda x: (x["group_code"], x["sort_order"]))
    
    async def get_groups_with_configs(
        self,
        scope: ConfigScope,
        tenant_id: int | None = None,
    ) -> list[dict]:
        """
        获取分组列表（含配置项）
        
        Args:
            scope: 作用域
            tenant_id: 租户 ID（租户作用域时必填）
            
        Returns:
            分组列表，每项包含分组信息和配置项列表
        """
        actual_tenant_id = PLATFORM_TENANT_ID if scope == ConfigScope.PLATFORM else tenant_id
        groups = self.registry.get_groups_by_scope(scope)
        
        result = []
        
        for group in groups:
            if not group.is_active:
                continue
            
            configs = []
            for config_meta in group.configs:
                if not config_meta.is_visible:
                    continue
                
                value = await self._get_config_value(
                    key=config_meta.key,
                    tenant_id=actual_tenant_id,
                    scope=scope,
                    default=config_meta.default_value,
                )
                
                configs.append({
                    "key": config_meta.key,
                    "name_key": config_meta.name_key,
                    "description_key": config_meta.description_key,
                    "value_type": config_meta.value_type.value,
                    "value": value,
                    "default_value": config_meta.default_value,
                    "options": [opt.to_dict() for opt in config_meta.options],
                    "validation_rules": [rule.to_dict() for rule in config_meta.validation_rules],
                    "is_required": config_meta.is_required,
                    "is_encrypted": config_meta.is_encrypted,
                    "sort_order": config_meta.sort_order,
                })
            
            result.append({
                "code": group.code,
                "name_key": group.name_key,
                "description_key": group.description_key,
                "icon": group.icon,
                "sort_order": group.sort_order,
                "configs": sorted(configs, key=lambda x: x["sort_order"]),
            })
        
        return sorted(result, key=lambda x: x["sort_order"])
    
    # ==========================================
    # 内部方法
    # ==========================================
    
    async def _get_config_value(
        self,
        key: str,
        tenant_id: int,
        scope: ConfigScope,
        default: Any = None,
        skip_default: bool = False,
    ) -> Any:
        """获取配置值"""
        # 获取配置项 ID
        config_id = await self._get_config_id(key)
        if not config_id:
            return default if not skip_default else None
        
        # 查询配置值
        result = await self.db.execute(
            select(SystemConfigValue).where(
                and_(
                    SystemConfigValue.config_id == config_id,
                    SystemConfigValue.tenant_id == tenant_id,
                    SystemConfigValue.is_deleted == False,
                )
            )
        )
        value_record = result.scalar_one_or_none()
        
        if value_record and value_record.value is not None:
            return self._deserialize_value(value_record.value)
        
        if skip_default:
            return None
        
        # 返回默认值
        return default
    
    async def _set_config_value(
        self,
        key: str,
        tenant_id: int,
        value: Any,
    ) -> None:
        """设置配置值"""
        # 获取配置项 ID
        config_id = await self._get_config_id(key)
        if not config_id:
            raise ValueError(f"Config '{key}' not found")
        
        # 查询现有记录
        result = await self.db.execute(
            select(SystemConfigValue).where(
                and_(
                    SystemConfigValue.config_id == config_id,
                    SystemConfigValue.tenant_id == tenant_id,
                    SystemConfigValue.is_deleted == False,
                )
            )
        )
        value_record = result.scalar_one_or_none()
        
        serialized_value = self._serialize_value(value)
        
        if value_record:
            # 更新现有记录
            value_record.value = serialized_value
        else:
            # 创建新记录
            value_record = SystemConfigValue(
                config_id=config_id,
                tenant_id=tenant_id,
                value=serialized_value,
            )
            self.db.add(value_record)
        
        await self.db.flush()
    
    async def _get_configs_by_group(
        self,
        group_code: str,
        tenant_id: int,
    ) -> dict[str, Any]:
        """获取分组下的所有配置值"""
        group = self.registry.get_group(group_code)
        if not group:
            return {}
        
        result = {}
        for config_meta in group.configs:
            value = await self._get_config_value(
                key=config_meta.key,
                tenant_id=tenant_id,
                scope=config_meta.scope,
                default=config_meta.default_value,
            )
            result[config_meta.key] = value
        
        return result
    
    async def _get_config_id(self, key: str) -> int | None:
        """根据 key 获取配置项 ID"""
        result = await self.db.execute(
            select(SystemConfig.id).where(
                and_(
                    SystemConfig.key == key,
                    SystemConfig.is_deleted == False,
                )
            )
        )
        return result.scalar_one_or_none()
    
    def _serialize_value(self, value: Any) -> str | None:
        """序列化值为 JSON 字符串"""
        if value is None:
            return None
        return json.dumps(value, ensure_ascii=False)
    
    def _deserialize_value(self, value: str) -> Any:
        """反序列化 JSON 字符串为值"""
        if value is None:
            return None
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value


# 便捷函数
async def get_config_service(db: AsyncSession) -> ConfigService:
    """获取配置服务实例"""
    return ConfigService(db)


__all__ = [
    "ConfigService",
    "get_config_service",
    "PLATFORM_TENANT_ID",
]
