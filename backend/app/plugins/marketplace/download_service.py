"""
插件下载与安装服务

职责：
1. 从 GitHub/Gitee Release 下载插件包
2. 一键安装流程（下载 → 解压 → 校验 → 安装 → 启用 → 回写市场字段）
3. 一键更新流程（下载新版 → 升级 → 重新启用）
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.i18n import _
from app.core.logging import LogManager
from app.exceptions import BusinessException, ConflictException, NotFoundException
from app.plugins.github_client import (
    async_download,
    async_get,
    build_release_api_url,
    get_mirror,
    get_repo_for_mirror,
    parse_release_download_url,
)
from app.plugins.marketplace.registry_service import PluginRegistryService

if TYPE_CHECKING:
    from app.models.system.plugin import Plugin

logger = LogManager.get_logger("app")

# 安全：允许的下载 MIME 类型
_ALLOWED_CONTENT_TYPES = (
    "application/zip",
    "application/x-zip-compressed",
    "application/octet-stream",
)


class PluginDownloadService:
    """
    插件下载与安装服务

    调用链：
    1. install_from_registry(slug) → 下载 → 解压 → PluginManager.install() → enable
    2. update_from_registry(slug) → 下载 → PluginManager.upgrade() → 更新元数据
    """

    # ========================================
    # 一键安装
    # ========================================

    async def install_from_registry(
        self,
        db: AsyncSession,
        slug: str,
        version: str | None = None,
        admin_id: int | None = None,
    ) -> Plugin:
        """
        从插件市场一键安装插件

        流程：
        1. 从 registry 获取插件元数据
        2. 检查本地是否已安装
        3. 检查平台版本兼容性
        4. 从 Release 下载插件包
        5. 解压到 plugins 目录
        6. 调用 PluginManager.install()
        7. 自动启用
        8. 回写市场字段（install_source/marketplace_slug/category/tags 等）
        9. 清理临时文件

        Args:
            db: 数据库会话
            slug: 插件市场 slug
            version: 指定版本（默认最新）
            admin_id: 操作管理员 ID

        Returns:
            安装后的 Plugin 模型

        Raises:
            NotFoundException: slug 不存在
            ConflictException: 已安装
            BusinessException: 下载/安装失败
        """
        from app.plugins.manager import get_plugin_manager
        from app.repositories.system.plugin_repository import PluginRepository

        registry_svc = PluginRegistryService()

        # 1. 获取插件元数据
        plugin_entry = await registry_svc.get_plugin_by_slug(slug, db)
        if not plugin_entry:
            raise NotFoundException(_("marketplace.plugin_not_found"))

        # 2. 检查是否已安装
        repo = PluginRepository(db)
        existing = await repo.get_by_name(plugin_entry.name)
        if existing:
            raise ConflictException(_("marketplace.plugin_already_installed"))

        # 3. 检查平台版本兼容性
        if plugin_entry.min_platform_version:
            from app.plugins.dependencies import check_platform_version_or_raise
            try:
                check_platform_version_or_raise(plugin_entry.min_platform_version)
            except Exception as exc:
                raise BusinessException(
                    _("marketplace.platform_version_incompatible")
                ) from exc

        # 4. 下载插件包
        target_version = version or plugin_entry.version
        tmp_dir = tempfile.mkdtemp(prefix="novusai_marketplace_")

        try:
            nap_path = await self._download_release(
                plugin_entry, target_version, tmp_dir,
            )

            # 5. 解压到 plugins 目录
            from app.plugins.packaging import PackageError, extract_package

            extract_dir = Path(tmp_dir) / "extracted"
            try:
                manifest = extract_package(nap_path, extract_dir)
            except PackageError as exc:
                raise BusinessException(
                    _("marketplace.package_invalid") + f": {exc}"
                ) from exc

            plugin_name = manifest.get("name", "")
            raw_entry_point = manifest.get("entry_point", "")
            module_name = plugin_name.replace("-", "_")

            plugins_base = Path(__file__).resolve().parent.parent.parent / "plugins"
            permanent_dir = plugins_base / module_name

            if permanent_dir.exists():
                raise ConflictException(
                    _("marketplace.plugin_directory_exists")
                )

            shutil.copytree(extract_dir, permanent_dir)

            # 6. 安装
            entry_point = f"app.plugins.{module_name}.{raw_entry_point}"
            manager = get_plugin_manager()

            # 安装 Python 依赖
            try:
                manager.install_plugin_requirements(plugin_name)
            except Exception:
                shutil.rmtree(permanent_dir, ignore_errors=True)
                raise

            try:
                plugin = await manager.install(
                    db,
                    entry_point=entry_point,
                    is_system=False,
                    admin_id=admin_id,
                )
            except Exception:
                shutil.rmtree(permanent_dir, ignore_errors=True)
                raise

            # 7. 自动启用
            try:
                plugin = await manager.enable_platform(
                    db, plugin.id, admin_id=admin_id,
                )
            except Exception as exc:
                logger.warning(
                    "Marketplace plugin installed but auto-enable failed: %s — %s",
                    plugin_name, str(exc),
                )

            # 8. 回写市场字段
            await self._update_marketplace_fields(
                db, plugin.id, plugin_entry, slug,
            )

            logger.info(
                "Marketplace plugin installed: %s v%s (slug=%s, mirror=%s)",
                plugin_name, target_version, slug, get_mirror(),
            )
            return plugin

        finally:
            # 9. 清理临时文件
            shutil.rmtree(tmp_dir, ignore_errors=True)

    # ========================================
    # 一键更新
    # ========================================

    async def update_from_registry(
        self,
        db: AsyncSession,
        slug: str,
        admin_id: int | None = None,
    ) -> Plugin:
        """
        从插件市场一键更新插件

        流程：
        1. 从 registry 获取最新版本
        2. 与本地版本对比
        3. 下载新版插件包
        4. 解压 → 覆盖 → PluginManager.upgrade()
        5. 更新市场元数据

        Args:
            db: 数据库会话
            slug: 插件市场 slug
            admin_id: 操作管理员 ID

        Returns:
            更新后的 Plugin 模型

        Raises:
            NotFoundException: 插件不存在
            BusinessException: 已是最新版/升级失败
        """
        from app.plugins.manager import get_plugin_manager
        from app.repositories.system.plugin_repository import PluginRepository

        registry_svc = PluginRegistryService()

        # 1. 获取 registry 元数据
        plugin_entry = await registry_svc.get_plugin_by_slug(slug, db)
        if not plugin_entry:
            raise NotFoundException(_("marketplace.plugin_not_found"))

        # 2. 查找本地已安装插件
        repo = PluginRepository(db)
        existing = await repo.get_by_name(plugin_entry.name)
        if not existing:
            raise NotFoundException(_("marketplace.plugin_not_installed"))

        # 3. 版本对比
        if not PluginRegistryService._is_newer_version(
            plugin_entry.version, existing.version,
        ):
            raise BusinessException(_("marketplace.already_latest_version"))

        # 4. 下载新版
        tmp_dir = tempfile.mkdtemp(prefix="novusai_marketplace_update_")

        try:
            nap_path = await self._download_release(
                plugin_entry, plugin_entry.version, tmp_dir,
            )

            # 解压
            from app.plugins.packaging import PackageError, extract_package

            extract_dir = Path(tmp_dir) / "extracted"
            try:
                manifest = extract_package(nap_path, extract_dir)
            except PackageError as exc:
                raise BusinessException(
                    _("marketplace.package_invalid") + f": {exc}"
                ) from exc

            plugin_name = manifest.get("name", "")
            raw_entry_point = manifest.get("entry_point", "")
            module_name = plugin_name.replace("-", "_")

            plugins_base = Path(__file__).resolve().parent.parent.parent / "plugins"
            permanent_dir = plugins_base / module_name

            # 备份旧版 → 覆盖新版
            backup_dir = permanent_dir.with_suffix(".bak")
            if backup_dir.exists():
                shutil.rmtree(backup_dir, ignore_errors=True)

            if permanent_dir.exists():
                shutil.move(str(permanent_dir), str(backup_dir))

            try:
                shutil.copytree(extract_dir, permanent_dir)
            except Exception:
                shutil.rmtree(permanent_dir, ignore_errors=True)
                if backup_dir.exists():
                    shutil.move(str(backup_dir), str(permanent_dir))
                raise

            # 安装 Python 依赖
            manager = get_plugin_manager()
            try:
                manager.install_plugin_requirements(plugin_name)
            except Exception:
                shutil.rmtree(permanent_dir, ignore_errors=True)
                if backup_dir.exists():
                    shutil.move(str(backup_dir), str(permanent_dir))
                raise

            # 升级
            entry_point = f"app.plugins.{module_name}.{raw_entry_point}"
            try:
                plugin = await manager.upgrade(
                    db,
                    plugin_id=existing.id,
                    new_entry_point=entry_point,
                )
                # 升级成功，删除备份
                shutil.rmtree(backup_dir, ignore_errors=True)
            except Exception:
                shutil.rmtree(permanent_dir, ignore_errors=True)
                if backup_dir.exists():
                    shutil.move(str(backup_dir), str(permanent_dir))
                raise

            # 5. 更新市场元数据
            await self._update_marketplace_fields(
                db, plugin.id, plugin_entry, slug,
            )

            logger.info(
                "Marketplace plugin updated: %s %s → %s (slug=%s)",
                plugin_name, existing.version, plugin_entry.version, slug,
            )
            return plugin

        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    # ========================================
    # 内部方法
    # ========================================

    async def _download_release(
        self,
        plugin_entry: Any,
        version: str,
        tmp_dir: str,
    ) -> Path:
        """
        从 GitHub/Gitee Release 下载插件包

        Args:
            plugin_entry: MarketplacePluginResponse
            version: 目标版本
            tmp_dir: 临时目录

        Returns:
            下载的 .zip/.nap 文件路径
        """
        # 获取当前镜像的 repo
        repos = {}
        if plugin_entry.repo:
            if plugin_entry.repo.github:
                repos["github"] = plugin_entry.repo.github
            if plugin_entry.repo.gitee:
                repos["gitee"] = plugin_entry.repo.gitee

        if not repos:
            raise BusinessException(_("marketplace.no_repository_configured"))

        repo = get_repo_for_mirror(repos)
        tag = f"v{version}" if not version.startswith("v") else version

        # 获取 Release 信息
        release_url = build_release_api_url(repo, tag)
        try:
            release_data = await async_get(release_url)
        except Exception as exc:
            raise BusinessException(
                _("marketplace.release_not_found") + f": {tag}"
            ) from exc

        if not isinstance(release_data, dict):
            raise BusinessException(_("marketplace.release_not_found"))

        # 提取 asset 下载 URL
        download_url = parse_release_download_url(release_data)
        if not download_url:
            raise BusinessException(
                _("marketplace.no_downloadable_asset")
            )

        # 下载
        dest_path = Path(tmp_dir) / f"{plugin_entry.slug}-{version}.zip"
        try:
            await async_download(
                download_url,
                dest_path,
                expected_content_types=_ALLOWED_CONTENT_TYPES,
            )
        except ValueError as exc:
            raise BusinessException(str(exc)) from exc
        except Exception as exc:
            raise BusinessException(
                _("marketplace.download_failed") + f": {exc}"
            ) from exc

        return dest_path

    @staticmethod
    async def _update_marketplace_fields(
        db: AsyncSession,
        plugin_id: int,
        plugin_entry: Any,
        slug: str,
    ) -> None:
        """回写市场相关字段到 Plugin 记录"""
        from app.repositories.system.plugin_repository import PluginRepository

        repo = PluginRepository(db)
        update_data: dict[str, Any] = {
            "install_source": "marketplace",
            "marketplace_slug": slug,
        }

        if plugin_entry.category:
            update_data["category"] = plugin_entry.category
        if plugin_entry.tags:
            update_data["tags"] = plugin_entry.tags
        if plugin_entry.icon:
            update_data["icon"] = plugin_entry.icon
        if plugin_entry.license:
            update_data["license"] = plugin_entry.license
        if plugin_entry.screenshots:
            update_data["screenshots"] = plugin_entry.screenshots

        # 构建 source_url（当前镜像的仓库地址）
        repos = {}
        if plugin_entry.repo:
            if plugin_entry.repo.github:
                repos["github"] = plugin_entry.repo.github
            if plugin_entry.repo.gitee:
                repos["gitee"] = plugin_entry.repo.gitee
        if repos:
            from app.plugins.github_client import build_repo_url
            try:
                r = get_repo_for_mirror(repos)
                update_data["source_url"] = build_repo_url(r)
            except ValueError:
                pass

        try:
            await repo.update(plugin_id, update_data)
        except Exception as exc:
            logger.warning(
                "Failed to update marketplace fields for plugin %d: %s",
                plugin_id, str(exc),
            )
