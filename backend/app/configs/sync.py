"""
配置同步服务

实现应用启动时自动同步代码定义的配置项到数据库
同步策略：新增/更新元数据/保留用户值
"""

import json
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.configs.meta import ConfigGroupMeta, ConfigMeta
from app.configs.registry import ConfigRegistry, config_registry
from app.models.system.config import SystemConfig, SystemConfigGroup

logger = logging.getLogger(__name__)


class ConfigSyncService:
    """
    配置同步服务
    
    将代码中定义的配置元数据同步到数据库
    
    同步策略：
    - 新增：代码中有但数据库中没有的配置，创建新记录
    - 更新：代码中有且数据库中也有的配置，更新元数据（不覆盖用户设置的值）
    - 废弃：数据库中有但代码中没有的配置，标记为不可见（保留数据）
    """
    
    def __init__(
        self,
        db: AsyncSession,
        registry: ConfigRegistry | None = None,
    ):
        """
        初始化同步服务
        
        Args:
            db: 数据库会话
            registry: 配置注册中心，默认使用全局实例
        """
        self.db = db
        self.registry = registry or config_registry
    
    async def sync_all(self) -> dict:
        """
        同步所有配置（分组和配置项）
        
        Returns:
            同步结果统计
        """
        logger.info("Starting config sync...")
        
        # 同步分组
        group_stats = await self.sync_groups()
        
        # 同步配置项
        config_stats = await self.sync_configs()
        
        # 提交事务
        await self.db.commit()
        
        result = {
            "groups": group_stats,
            "configs": config_stats,
        }
        
        logger.info(f"Config sync completed: {result}")
        return result
    
    async def sync_groups(self) -> dict:
        """
        同步配置分组
        
        Returns:
            同步统计：{created: int, updated: int, deprecated: int}
        """
        stats = {"created": 0, "updated": 0, "deprecated": 0}
        
        # 获取所有代码定义的分组
        code_groups = self._collect_all_groups()
        code_group_codes = {g.code for g in code_groups}
        
        # 获取数据库中已有的分组
        result = await self.db.execute(
            select(SystemConfigGroup).where(SystemConfigGroup.is_deleted == False)
        )
        db_groups = {g.code: g for g in result.scalars().all()}
        
        # 第一遍：创建/更新分组（不处理 parent_id）
        group_id_map: dict[str, int] = {}
        
        for group_meta in code_groups:
            if group_meta.code in db_groups:
                # 更新现有分组
                db_group = db_groups[group_meta.code]
                self._update_group_from_meta(db_group, group_meta)
                group_id_map[group_meta.code] = db_group.id
                stats["updated"] += 1
            else:
                # 创建新分组（先不设置 parent_id）
                db_group = self._create_group_from_meta(group_meta)
                self.db.add(db_group)
                await self.db.flush()  # 获取 ID
                group_id_map[group_meta.code] = db_group.id
                db_groups[group_meta.code] = db_group
                stats["created"] += 1
        
        # 第二遍：更新 parent_id
        for group_meta in code_groups:
            if group_meta.parent_code and group_meta.parent_code in group_id_map:
                db_group = db_groups[group_meta.code]
                db_group.parent_id = group_id_map[group_meta.parent_code]
        
        # 标记废弃的分组
        for code, db_group in db_groups.items():
            if code not in code_group_codes:
                db_group.is_active = False
                stats["deprecated"] += 1
        
        logger.debug(f"Groups sync stats: {stats}")
        return stats
    
    async def sync_configs(self) -> dict:
        """
        同步配置项
        
        Returns:
            同步统计：{created: int, updated: int, deprecated: int}
        """
        stats = {"created": 0, "updated": 0, "deprecated": 0}
        
        # 获取所有代码定义的配置项
        code_configs = self.registry.get_all_configs()
        code_config_keys = {(c.group_code, c.key) for c in code_configs}
        
        # 获取数据库中的分组映射
        result = await self.db.execute(
            select(SystemConfigGroup).where(SystemConfigGroup.is_deleted == False)
        )
        group_map = {g.code: g.id for g in result.scalars().all()}
        
        # 获取数据库中已有的配置项
        result = await self.db.execute(
            select(SystemConfig).where(SystemConfig.is_deleted == False)
        )
        db_configs: dict[tuple[int, str], SystemConfig] = {}
        for config in result.scalars().all():
            db_configs[(config.group_id, config.key)] = config
        
        # 创建 group_id -> code 的反向映射
        group_id_to_code = {v: k for k, v in group_map.items()}
        
        # 创建/更新配置项
        for config_meta in code_configs:
            group_id = group_map.get(config_meta.group_code)
            if not group_id:
                logger.warning(
                    f"Config '{config_meta.key}' references unknown group '{config_meta.group_code}'"
                )
                continue
            
            db_key = (group_id, config_meta.key)
            
            if db_key in db_configs:
                # 更新现有配置项
                db_config = db_configs[db_key]
                self._update_config_from_meta(db_config, config_meta, group_id)
                stats["updated"] += 1
            else:
                # 创建新配置项
                db_config = self._create_config_from_meta(config_meta, group_id)
                self.db.add(db_config)
                stats["created"] += 1
        
        # 标记废弃的配置项
        for (group_id, key), db_config in db_configs.items():
            group_code = group_id_to_code.get(group_id, "")
            if (group_code, key) not in code_config_keys:
                db_config.is_visible = False
                stats["deprecated"] += 1
        
        logger.debug(f"Configs sync stats: {stats}")
        return stats
    
    def _collect_all_groups(self) -> list[ConfigGroupMeta]:
        """收集所有分组（包括嵌套的子分组）"""
        groups = []
        
        def collect_recursive(group: ConfigGroupMeta):
            groups.append(group)
            for child in group.children:
                collect_recursive(child)
        
        for group in self.registry.get_all_groups():
            collect_recursive(group)
        
        return groups
    
    def _create_group_from_meta(self, meta: ConfigGroupMeta) -> SystemConfigGroup:
        """从元数据创建分组模型"""
        return SystemConfigGroup(
            code=meta.code,
            name_key=meta.name_key,
            description_key=meta.description_key or None,
            scope=meta.scope.value,
            icon=meta.icon or None,
            sort_order=meta.sort_order,
            is_active=meta.is_active,
            # parent_id 在第二遍设置
        )
    
    def _update_group_from_meta(
        self,
        db_group: SystemConfigGroup,
        meta: ConfigGroupMeta,
    ) -> None:
        """从元数据更新分组模型"""
        db_group.name_key = meta.name_key
        db_group.description_key = meta.description_key or None
        db_group.scope = meta.scope.value
        db_group.icon = meta.icon or None
        db_group.sort_order = meta.sort_order
        db_group.is_active = meta.is_active
        db_group.updated_at = datetime.utcnow()
    
    def _create_config_from_meta(
        self,
        meta: ConfigMeta,
        group_id: int,
    ) -> SystemConfig:
        """从元数据创建配置项模型"""
        return SystemConfig(
            key=meta.key,
            group_id=group_id,
            name_key=meta.name_key,
            description_key=meta.description_key or None,
            scope=meta.scope.value,
            value_type=meta.value_type.value,
            default_value=self._serialize_value(meta.default_value),
            validation_rules=self._serialize_rules(meta.validation_rules),
            options=self._serialize_options(meta.options),
            is_required=meta.is_required,
            is_visible=meta.is_visible,
            is_encrypted=meta.is_encrypted,
            sort_order=meta.sort_order,
        )
    
    def _update_config_from_meta(
        self,
        db_config: SystemConfig,
        meta: ConfigMeta,
        group_id: int,
    ) -> None:
        """从元数据更新配置项模型（保留用户设置的值）"""
        db_config.group_id = group_id
        db_config.name_key = meta.name_key
        db_config.description_key = meta.description_key or None
        db_config.scope = meta.scope.value
        db_config.value_type = meta.value_type.value
        db_config.default_value = self._serialize_value(meta.default_value)
        db_config.validation_rules = self._serialize_rules(meta.validation_rules)
        db_config.options = self._serialize_options(meta.options)
        db_config.is_required = meta.is_required
        db_config.is_visible = meta.is_visible
        db_config.is_encrypted = meta.is_encrypted
        db_config.sort_order = meta.sort_order
        db_config.updated_at = datetime.utcnow()
        # 注意：不更新 values 表中用户已设置的值
    
    def _serialize_value(self, value) -> str | None:
        """序列化值为 JSON 字符串"""
        if value is None:
            return None
        return json.dumps(value, ensure_ascii=False)
    
    def _serialize_rules(self, rules: list) -> str | None:
        """序列化验证规则"""
        if not rules:
            return None
        return json.dumps(
            [rule.to_dict() for rule in rules],
            ensure_ascii=False,
        )
    
    def _serialize_options(self, options: list) -> str | None:
        """序列化选项列表"""
        if not options:
            return None
        return json.dumps(
            [opt.to_dict() for opt in options],
            ensure_ascii=False,
        )


async def sync_configs_on_startup(db: AsyncSession) -> dict:
    """
    应用启动时同步配置
    
    Args:
        db: 数据库会话
        
    Returns:
        同步结果统计
    """
    service = ConfigSyncService(db)
    return await service.sync_all()


__all__ = [
    "ConfigSyncService",
    "sync_configs_on_startup",
]
