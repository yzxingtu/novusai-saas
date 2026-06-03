"""Configuration sync service / 配置同步服务

Auto-syncs code-defined config items to database on application startup.
Sync strategy: create new / update metadata / preserve user values.
实现应用启动时自动同步代码定义的配置项到数据库
同步策略：新增/更新元数据/保留用户值
"""

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.configs.meta import ConfigGroupMeta, ConfigMeta
from app.configs.registry import ConfigRegistry, config_registry
from app.core.base_model import utc_now
from app.core.logging import LogManager
from app.models.system.config import SystemConfig, SystemConfigGroup, SystemConfigValue

logger = LogManager.get_logger("app")


class ConfigSyncService:
    """
    Configuration sync service / 配置同步服务

    Syncs code-defined config metadata to database.
    将代码中定义的配置元数据同步到数据库

    Sync strategy / 同步策略：
    - Create: config exists in code but not in DB / 新增
    - Update: config exists in both, update metadata (preserve user values) / 更新元数据
    - Deprecate: config exists in DB but not in code, mark invisible / 废弃，标记不可见
    """

    def __init__(
        self,
        db: AsyncSession,
        registry: ConfigRegistry | None = None,
    ):
        """Initialize sync service / 初始化同步服务

        Args:
            db: Database session / 数据库会话
            registry: Config registry, defaults to global instance / 配置注册中心
        """
        self.db = db
        self.registry = registry or config_registry

    async def sync_all(self) -> dict:
        """Sync all configs (groups and items) / 同步所有配置

        Returns:
            Sync result statistics / 同步结果统计
        """
        logger.info("Starting config sync...")

        # Sync groups / 同步分组
        group_stats = await self.sync_groups()

        # Sync config items / 同步配置项
        config_stats = await self.sync_configs()

        # Commit transaction / 提交事务
        await self.db.commit()

        result = {
            "groups": group_stats,
            "configs": config_stats,
        }

        logger.info(f"Config sync completed: {result}")
        return result

    async def sync_groups(self) -> dict:
        """Sync config groups / 同步配置分组

        Returns:
            Sync stats: {created, updated, deprecated} / 同步统计
        """
        stats = {"created": 0, "updated": 0, "deprecated": 0}

        # Get all code-defined groups / 获取所有代码定义的分组
        code_groups = self._collect_all_groups()
        code_group_codes = {g.code for g in code_groups}

        # Get existing groups from DB / 获取数据库中已有的分组
        result = await self.db.execute(
            select(SystemConfigGroup).where(SystemConfigGroup.is_deleted.is_(False))
        )
        db_groups = {g.code: g for g in result.scalars().all()}

        # First pass: create/update groups (skip parent_id) / 第一遍：创建/更新分组
        group_id_map: dict[str, int] = {}

        for group_meta in code_groups:
            if group_meta.code in db_groups:
                # Update existing group / 更新现有分组
                db_group = db_groups[group_meta.code]
                self._update_group_from_meta(db_group, group_meta)
                group_id_map[group_meta.code] = db_group.id
                stats["updated"] += 1
            else:
                # Create new group (skip parent_id for now) / 创建新分组
                db_group = self._create_group_from_meta(group_meta)
                self.db.add(db_group)
                await self.db.flush()  # 获取 ID
                group_id_map[group_meta.code] = db_group.id
                db_groups[group_meta.code] = db_group
                stats["created"] += 1

        # Second pass: update parent_id / 第二遍：更新 parent_id
        for group_meta in code_groups:
            if group_meta.parent_code and group_meta.parent_code in group_id_map:
                db_group = db_groups[group_meta.code]
                db_group.parent_id = group_id_map[group_meta.parent_code]

        # Mark deprecated groups / 标记废弃的分组
        for code, db_group in db_groups.items():
            if code not in code_group_codes:
                db_group.is_active = False
                stats["deprecated"] += 1

        logger.debug(f"Groups sync stats: {stats}")
        return stats

    async def sync_configs(self) -> dict:
        """Sync config items / 同步配置项

        Returns:
            Sync stats: {created, updated, deprecated, migrated_values} / 同步统计
        """
        stats = {"created": 0, "updated": 0, "deprecated": 0, "migrated_values": 0}

        # Get all code-defined config items / 获取所有代码定义的配置项
        code_configs = self.registry.get_all_configs()
        code_config_keys = {(c.group_code, c.key) for c in code_configs}

        # Get group mapping from DB / 获取数据库中的分组映射
        result = await self.db.execute(
            select(SystemConfigGroup).where(SystemConfigGroup.is_deleted.is_(False))
        )
        group_map = {g.code: g.id for g in result.scalars().all()}

        # Get existing config items from DB / 获取数据库中已有的配置项
        result = await self.db.execute(
            select(SystemConfig).where(SystemConfig.is_deleted.is_(False))
        )
        db_configs: dict[tuple[int, str], SystemConfig] = {}
        for config in result.scalars().all():
            db_configs[(config.group_id, config.key)] = config

        # Create reverse mapping group_id -> code / 创建反向映射
        group_id_to_code = {v: k for k, v in group_map.items()}
        canonical_configs_by_key: dict[str, SystemConfig] = {}

        # Create/update config items / 创建/更新配置项
        for config_meta in code_configs:
            group_id = group_map.get(config_meta.group_code)
            if not group_id:
                logger.warning(
                    f"Config '{config_meta.key}' references unknown group '{config_meta.group_code}'"
                )
                continue

            db_key = (group_id, config_meta.key)

            if db_key in db_configs:
                # Update existing config item / 更新现有配置项
                db_config = db_configs[db_key]
                self._update_config_from_meta(db_config, config_meta, group_id)
                stats["updated"] += 1
            else:
                # Create new config item / 创建新配置项
                db_config = self._create_config_from_meta(config_meta, group_id)
                self.db.add(db_config)
                stats["created"] += 1
            canonical_configs_by_key[config_meta.key] = db_config

        if stats["created"]:
            await self.db.flush()

        # Mark deprecated config items / 标记废弃的配置项
        for (group_id, key), db_config in db_configs.items():
            group_code = group_id_to_code.get(group_id, "")
            if (group_code, key) not in code_config_keys:
                canonical_config = canonical_configs_by_key.get(key)
                if canonical_config and canonical_config.id != db_config.id:
                    migrated_values = await self._copy_values_to_canonical_config(
                        source_config_id=db_config.id,
                        target_config_id=canonical_config.id,
                    )
                    stats["migrated_values"] += migrated_values
                db_config.is_visible = False
                stats["deprecated"] += 1

        logger.debug(f"Configs sync stats: {stats}")
        return stats

    async def _copy_values_to_canonical_config(
        self,
        *,
        source_config_id: int,
        target_config_id: int,
    ) -> int:
        """Copy values from a rehomed key when target lacks tenant row / 迁移换组配置值。"""
        result = await self.db.execute(
            select(SystemConfigValue).where(
                SystemConfigValue.config_id == source_config_id,
                SystemConfigValue.is_deleted.is_(False),
            )
        )
        source_values = list(result.scalars().all())
        if not source_values:
            return 0

        tenant_ids = [value.tenant_id for value in source_values]
        result = await self.db.execute(
            select(SystemConfigValue.tenant_id).where(
                SystemConfigValue.config_id == target_config_id,
                SystemConfigValue.tenant_id.in_(tenant_ids),
                SystemConfigValue.is_deleted.is_(False),
            )
        )
        existing_tenant_ids = set(result.scalars().all())

        migrated = 0
        for source_value in source_values:
            if source_value.tenant_id in existing_tenant_ids:
                continue
            self.db.add(
                SystemConfigValue(
                    config_id=target_config_id,
                    tenant_id=source_value.tenant_id,
                    value=source_value.value,
                )
            )
            migrated += 1
        return migrated

    def _collect_all_groups(self) -> list[ConfigGroupMeta]:
        """Collect all groups (including nested child groups) / 收集所有分组（包括嵌套的子分组）"""
        groups = []

        def collect_recursive(group: ConfigGroupMeta):
            groups.append(group)
            for child in group.children:
                collect_recursive(child)

        for group in self.registry.get_all_groups():
            collect_recursive(group)

        return groups

    def _create_group_from_meta(self, meta: ConfigGroupMeta) -> SystemConfigGroup:
        """Create group model from metadata / 从元数据创建分组模型"""
        return SystemConfigGroup(
            code=meta.code,
            name_key=meta.name_key,
            description_key=meta.description_key or None,
            scope=meta.scope.value,
            icon=meta.icon or None,
            sort_order=meta.sort_order,
            is_active=meta.is_active,
            # parent_id set in second pass / parent_id 在第二遍设置
        )

    def _update_group_from_meta(
        self,
        db_group: SystemConfigGroup,
        meta: ConfigGroupMeta,
    ) -> None:
        """Update group model from metadata / 从元数据更新分组模型"""
        db_group.name_key = meta.name_key
        db_group.description_key = meta.description_key or None
        db_group.scope = meta.scope.value
        db_group.icon = meta.icon or None
        db_group.sort_order = meta.sort_order
        db_group.is_active = meta.is_active
        db_group.updated_at = utc_now()

    def _create_config_from_meta(
        self,
        meta: ConfigMeta,
        group_id: int,
    ) -> SystemConfig:
        """Create config item model from metadata / 从元数据创建配置项模型"""
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
        """Update config item model from metadata (preserve user values) / 从元数据更新配置项模型（保留用户值）"""
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
        db_config.updated_at = utc_now()
        # Note: do not update user-set values in values table / 注意：不更新用户已设置的值

    def _serialize_value(self, value) -> str | None:
        """Serialize value to JSON string / 序列化值为 JSON 字符串"""
        if value is None:
            return None
        return json.dumps(value, ensure_ascii=False)

    def _serialize_rules(self, rules: list) -> str | None:
        """Serialize validation rules / 序列化验证规则"""
        if not rules:
            return None
        return json.dumps(
            [rule.to_dict() for rule in rules],
            ensure_ascii=False,
        )

    def _serialize_options(self, options: list) -> str | None:
        """Serialize options list / 序列化选项列表"""
        if not options:
            return None
        return json.dumps(
            [opt.to_dict() for opt in options],
            ensure_ascii=False,
        )


async def sync_configs_on_startup(db: AsyncSession) -> dict:
    """Sync configs on application startup / 应用启动时同步配置

    Args:
        db: Database session / 数据库会话

    Returns:
        Sync result statistics / 同步结果统计
    """
    service = ConfigSyncService(db)
    return await service.sync_all()


__all__ = [
    "ConfigSyncService",
    "sync_configs_on_startup",
]
