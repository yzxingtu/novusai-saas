"""
Plugin version management. / 插件版本管理。

Provides version backup, upgrade, rollback, and history query functionality.
/ 提供版本备份、升级、回滚、历史查询功能。
"""

from __future__ import annotations

import contextlib
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from app.core.base_model import utc_now
from app.core.logging import get_logger
from app.enums.plugin import PluginStatusEnum, PluginVersionStatusEnum
from app.plugins.exceptions import PluginError, PluginNotFoundError, PluginSecurityError
from app.plugins.loader import PLUGINS_DIR

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

VERSIONS_DIR = PLUGINS_DIR / ".versions"


class VersionManager:
    """Plugin version manager / 插件版本管理器"""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    def archive_version(self, plugin_name: str, version: str) -> Path:
        """
        Archive current plugin version to .versions/{name}/{version}/
        / 备份插件当前版本

        Returns:
            Backup directory path / 备份目录路径
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
        logger.info("Archived {} v{} to {}", plugin_name, version, target)
        return target

    async def upgrade(
        self,
        plugin_id: int,
        new_source: Path,
    ) -> None:
        """Upgrade plugin (full flow locked, avoid concurrent race conditions).
        / 升级插件（全流程加锁）"""
        from app.plugins.lifecycle import _plugin_lock

        async with _plugin_lock(plugin_id):
            await self._upgrade_unlocked(plugin_id, new_source)

    async def _upgrade_unlocked(
        self,
        plugin_id: int,
        new_source: Path,
    ) -> None:
        """
        Upgrade plugin: disable old → backup → replace → migrate → enable new.
        / 升级插件：禁用旧版 → 备份 → 替换 → 迁移 → 启用新版

        Auto-rollback to old version on failure.
        / 失败时自动回滚。
        """
        from sqlalchemy import select

        from app.models.system.plugin import Plugin
        from app.models.system.plugin_version import PluginVersion
        from app.plugins.lifecycle import PluginLifecycle
        from app.plugins.loader import PluginLoader
        from app.plugins.module_loader import unload_plugin_modules

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

        # Parse new version manifest / 解析新版本 manifest
        new_manifest = loader.load_manifest_from_path(new_source)
        new_version = new_manifest.version

        if new_manifest.name != plugin_name:
            raise PluginError(
                message=(
                    f"Upgrade package mismatch: expected plugin '{plugin_name}', "
                    f"but got '{new_manifest.name}'"
                ),
            )

        # Pre-upgrade security scan (high risk fail-close) / 升级前安全扫描
        from app.plugins.security_scan import scan_plugin_directory

        scan_result = scan_plugin_directory(new_source)
        if scan_result.has_warnings:
            top_warnings = "; ".join(scan_result.warnings[:5])
            raise PluginSecurityError(
                message=(
                    f"Plugin '{plugin_name}' upgrade blocked by security scan: "
                    f"{top_warnings}"
                ),
            )

        if new_version == old_version:
            raise PluginError(
                message=f"New version ({new_version}) is the same as current ({old_version})",
            )

        # 1. Disable old version (call _disable_impl since outer upgrade() already holds lock)
        # / 禁用旧版
        was_enabled = plugin.status == PluginStatusEnum.ENABLED.value
        if was_enabled:
            await lifecycle._disable_impl(plugin_id)

        # 2. Backup old version / 备份旧版
        self.archive_version(plugin_name, old_version)

        # 3. Replace files / 替换文件
        target_dir = PLUGINS_DIR / plugin_name
        old_backup = VERSIONS_DIR / plugin_name / old_version

        try:
            shutil.rmtree(target_dir)
            shutil.copytree(new_source, target_dir)

            # Clear module cache, ensure subsequent on_upgrade/enable uses new code
            # / 清理模块缓存
            unload_plugin_modules(plugin_name)

            # 4. Install new version Python deps (npm installed during re-enable)
            # pip must be installed before migration since migration scripts may import new deps
            # / 安装新版 Python 依赖
            if new_manifest.dependencies.python:
                await lifecycle._install_python_deps(plugin_name, new_manifest.dependencies.python)

            # 5. Run migration (via lifecycle public interface) / 执行迁移
            await lifecycle.run_alembic_upgrade(plugin_name)

            # 6. Update DB record / 更新 DB 记录
            plugin.version = new_version
            plugin.manifest = new_manifest.model_dump()
            from app.plugins.preview import resolve_i18n
            plugin.display_name = resolve_i18n(new_manifest.display_name)
            new_py_deps = getattr(getattr(new_manifest, "dependencies", None), "python", None) or []
            plugin.installed_packages = new_py_deps

            # Archive old version / 旧版本归档
            from sqlalchemy import update
            await self._db.execute(
                update(PluginVersion)
                .where(
                    PluginVersion.plugin_id == plugin_id,
                    PluginVersion.status == PluginVersionStatusEnum.ACTIVE.value,
                )
                .values(status=PluginVersionStatusEnum.ARCHIVED.value)
            )

            # New version record / 新版本记录
            version_record = PluginVersion(
                plugin_id=plugin_id,
                version=new_version,
                manifest=new_manifest.model_dump(),
                status=PluginVersionStatusEnum.ACTIVE.value,
                installed_at=utc_now(),
            )
            self._db.add(version_record)
            await self._db.flush()

            # 7. Call on_upgrade / 调用 on_upgrade
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
                logger.warning("on_upgrade failed for {}: {}", plugin_name, exc)

            # 8. Re-enable (if previously enabled, call _enable_impl to avoid nested locks)
            # / 重新启用
            if was_enabled:
                await lifecycle._enable_impl(plugin_id)

            logger.info(
                "Plugin {} upgraded: {} → {}", plugin_name, old_version, new_version
            )

        except Exception as exc:
            # Rollback: restore old version files / 回滚
            logger.error("Upgrade failed for {}, rolling back: {}", plugin_name, exc)
            if old_backup.exists():
                if target_dir.exists():
                    shutil.rmtree(target_dir)
                shutil.copytree(old_backup, target_dir)
                unload_plugin_modules(plugin_name)
                plugin.version = old_version
                if was_enabled:
                    with contextlib.suppress(Exception):
                        await lifecycle._enable_impl(plugin_id)
            raise PluginError(
                message=f"Upgrade failed for '{plugin_name}': {exc}",
            )

    async def rollback(self, plugin_id: int, target_version: str) -> None:
        """Rollback to specified version (full flow locked, avoid concurrent race conditions).
        / 回滚到指定版本（全流程加锁）"""
        from app.plugins.lifecycle import _plugin_lock

        async with _plugin_lock(plugin_id):
            await self._rollback_unlocked(plugin_id, target_version)

    async def _rollback_unlocked(self, plugin_id: int, target_version: str) -> None:
        """Rollback to specified version. / 回滚到指定版本。"""
        from sqlalchemy import select

        from app.models.system.plugin import Plugin
        from app.plugins.lifecycle import PluginLifecycle
        from app.plugins.module_loader import unload_plugin_modules

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

        # Disable current (call _disable_impl since outer rollback() already holds lock)
        # / 禁用当前
        was_enabled = plugin.status == PluginStatusEnum.ENABLED.value
        if was_enabled:
            await lifecycle._disable_impl(plugin_id)

        # Backup current version / 备份当前版本
        self.archive_version(plugin_name, plugin.version)

        # Rollback alembic migration (must be done before file replacement, using current version's migration scripts)
        # If downgrade is not done first, current version's extra migration stamps will be purged by
        # _purge_orphaned_alembic_stamps, causing upgrade to rebuild existing tables and error out.
        # / 回滚 alembic 迁移（必须在文件替换前）
        try:
            await lifecycle.run_alembic_downgrade(plugin_name)
        except Exception as exc:
            logger.warning(
                "Rollback {}: alembic downgrade failed (continuing with file restore): {}",
                plugin_name, exc,
            )

        # Restore target version / 恢复目标版本
        target_dir = PLUGINS_DIR / plugin_name
        shutil.rmtree(target_dir)
        shutil.copytree(backup_dir, target_dir)
        unload_plugin_modules(plugin_name)

        # Update DB / 更新 DB
        from app.plugins.loader import PluginLoader

        loader = PluginLoader()
        restored_manifest = loader.load_manifest(plugin_name)

        plugin.version = target_version
        plugin.manifest = restored_manifest.model_dump()
        restored_py_deps = getattr(getattr(restored_manifest, "dependencies", None), "python", None) or []
        plugin.installed_packages = restored_py_deps
        await self._db.flush()

        # Re-enable (call _enable_impl to avoid nested locks) / 重新启用
        if was_enabled:
            await lifecycle._enable_impl(plugin_id)

        logger.info("Plugin {} rolled back to v{}", plugin_name, target_version)

    async def list_versions(self, plugin_id: int) -> list[dict]:
        """Query plugin version history / 查询插件版本历史"""
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
