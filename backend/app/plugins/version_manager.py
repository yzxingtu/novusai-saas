"""
插件版本管理

提供版本备份、升级、回滚、历史查询功能。
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from app.core.base_model import utc_now
from app.core.logging import get_logger
from app.enums.plugin import PluginStatusEnum, PluginVersionStatusEnum
from app.plugins.exceptions import PluginError, PluginNotFoundError
from app.plugins.loader import PLUGINS_DIR

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

VERSIONS_DIR = PLUGINS_DIR / ".versions"


class VersionManager:
    """插件版本管理器"""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    def archive_version(self, plugin_name: str, version: str) -> Path:
        """
        备份插件当前版本到 .versions/{name}/{version}/

        Returns:
            备份目录路径
        """
        source = PLUGINS_DIR / plugin_name
        if not source.is_dir():
            raise PluginNotFoundError(
                message=f"Plugin directory not found: {source}",
            )

        target = VERSIONS_DIR / plugin_name / version
        if target.exists():
            shutil.rmtree(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, target)
        logger.info("Archived %s v%s to %s", plugin_name, version, target)
        return target

    async def upgrade(
        self,
        plugin_id: int,
        new_source: Path,
    ) -> None:
        """
        升级插件：禁用旧版 → 备份 → 替换 → 迁移 → 启用新版

        失败时自动回滚到旧版本。
        """
        from sqlalchemy import select

        from app.models.system.plugin import Plugin
        from app.models.system.plugin_version import PluginVersion
        from app.plugins.lifecycle import PluginLifecycle
        from app.plugins.loader import PluginLoader

        result = await self._db.execute(
            select(Plugin).where(
                Plugin.id == plugin_id,
                Plugin.is_deleted.is_(False),
            )
        )
        plugin = result.scalar_one_or_none()
        if not plugin:
            raise PluginNotFoundError(message=f"Plugin ID {plugin_id} not found")

        plugin_name = plugin.name
        old_version = plugin.version
        lifecycle = PluginLifecycle(self._db)
        loader = PluginLoader()

        # 解析新版本 manifest
        new_manifest = loader.load_manifest(new_source.name)
        new_version = new_manifest.version

        if new_version == old_version:
            raise PluginError(
                message=f"New version ({new_version}) is the same as current ({old_version})",
            )

        # 1. 禁用旧版
        was_enabled = plugin.status == PluginStatusEnum.ENABLED.value
        if was_enabled:
            await lifecycle.disable(plugin_id)

        # 2. 备份旧版
        self.archive_version(plugin_name, old_version)

        # 3. 替换文件
        target_dir = PLUGINS_DIR / plugin_name
        old_backup = VERSIONS_DIR / plugin_name / old_version

        try:
            shutil.rmtree(target_dir)
            shutil.copytree(new_source, target_dir)

            # 4. 执行迁移（通过 lifecycle 公共接口）
            await lifecycle._run_alembic_upgrade(plugin_name)

            # 5. 更新 DB 记录
            plugin.version = new_version
            plugin.manifest = new_manifest.model_dump()
            plugin.display_name = new_manifest.display_name.get(
                "zh-CN", new_manifest.display_name.get("en", plugin_name)
            )

            # 旧版本归档
            from sqlalchemy import update
            await self._db.execute(
                update(PluginVersion)
                .where(
                    PluginVersion.plugin_id == plugin_id,
                    PluginVersion.status == PluginVersionStatusEnum.ACTIVE.value,
                )
                .values(status=PluginVersionStatusEnum.ARCHIVED.value)
            )

            # 新版本记录
            version_record = PluginVersion(
                plugin_id=plugin_id,
                version=new_version,
                manifest=new_manifest.model_dump(),
                status=PluginVersionStatusEnum.ACTIVE.value,
                installed_at=utc_now(),
            )
            self._db.add(version_record)
            await self._db.flush()

            # 6. 调用 on_upgrade
            try:
                plugin_cls = loader.load_plugin_class(plugin_name)
                from app.plugins.context_factory import create_plugin_context

                ctx = create_plugin_context(
                    plugin_name=plugin_name,
                    manifest=new_manifest,
                    db=self._db,
                    granted_capabilities=plugin.granted_capabilities or [],
                )
                await plugin_cls().on_upgrade(ctx, old_version)
            except Exception as exc:
                logger.warning("on_upgrade failed for %s: %s", plugin_name, exc)

            # 7. 重新启用（如果之前是启用状态）
            if was_enabled:
                await lifecycle.enable(plugin_id)

            logger.info(
                "Plugin %s upgraded: %s → %s", plugin_name, old_version, new_version
            )

        except Exception as exc:
            # 回滚：恢复旧版本文件
            logger.error("Upgrade failed for %s, rolling back: %s", plugin_name, exc)
            if old_backup.exists():
                if target_dir.exists():
                    shutil.rmtree(target_dir)
                shutil.copytree(old_backup, target_dir)
                plugin.version = old_version
                if was_enabled:
                    try:
                        await lifecycle.enable(plugin_id)
                    except Exception:
                        pass
            raise PluginError(
                message=f"Upgrade failed for '{plugin_name}': {exc}",
            )

    async def rollback(self, plugin_id: int, target_version: str) -> None:
        """回滚到指定版本"""
        from sqlalchemy import select

        from app.models.system.plugin import Plugin
        from app.plugins.lifecycle import PluginLifecycle

        result = await self._db.execute(
            select(Plugin).where(
                Plugin.id == plugin_id,
                Plugin.is_deleted.is_(False),
            )
        )
        plugin = result.scalar_one_or_none()
        if not plugin:
            raise PluginNotFoundError(message=f"Plugin ID {plugin_id} not found")

        plugin_name = plugin.name
        backup_dir = VERSIONS_DIR / plugin_name / target_version
        if not backup_dir.is_dir():
            raise PluginNotFoundError(
                message=f"Version {target_version} backup not found for '{plugin_name}'",
            )

        lifecycle = PluginLifecycle(self._db)

        # 禁用当前
        was_enabled = plugin.status == PluginStatusEnum.ENABLED.value
        if was_enabled:
            await lifecycle.disable(plugin_id)

        # 备份当前版本
        self.archive_version(plugin_name, plugin.version)

        # 恢复目标版本
        target_dir = PLUGINS_DIR / plugin_name
        shutil.rmtree(target_dir)
        shutil.copytree(backup_dir, target_dir)

        # 更新 DB
        from app.plugins.loader import PluginLoader

        loader = PluginLoader()
        restored_manifest = loader.load_manifest(plugin_name)

        plugin.version = target_version
        plugin.manifest = restored_manifest.model_dump()
        await self._db.flush()

        # 重新启用
        if was_enabled:
            await lifecycle.enable(plugin_id)

        logger.info("Plugin %s rolled back to v%s", plugin_name, target_version)

    async def list_versions(self, plugin_id: int) -> list[dict]:
        """查询插件版本历史"""
        from sqlalchemy import select

        from app.models.system.plugin_version import PluginVersion

        result = await self._db.execute(
            select(PluginVersion).where(
                PluginVersion.plugin_id == plugin_id,
                PluginVersion.is_deleted.is_(False),
            ).order_by(PluginVersion.created_at.desc())
        )
        versions = result.scalars().all()
        return [
            {
                "id": v.id,
                "version": v.version,
                "status": v.status,
                "changelog": v.changelog,
                "installed_at": v.installed_at.isoformat() if v.installed_at else None,
                "rolled_back_at": v.rolled_back_at.isoformat() if v.rolled_back_at else None,
            }
            for v in versions
        ]
