"""
插件生命周期管理

install / enable / disable / uninstall 四个核心操作。
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from app.core.base_model import utc_now
from app.core.logging import get_logger
from app.enums.plugin import (
    PluginInstallSourceEnum,
    PluginStatusEnum,
    PluginTierEnum,
)
from app.plugins.exceptions import (
    PluginDependencyError,
    PluginError,
    PluginInstallError,
)
from app.plugins.loader import PLUGINS_DIR, PluginLoader
from app.plugins.preview import resolve_i18n

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.system.plugin import Plugin

logger = get_logger(__name__)


class PluginLifecycle:
    """插件生命周期管理器"""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._loader = PluginLoader()

    # ================================================================
    # install
    # ================================================================

    async def install(
        self,
        source_path: Path,
        config: dict | None = None,
    ) -> Plugin:
        """
        安装插件（10 步流程）

        Args:
            source_path: 插件源目录（已解压）
            config: 初始配置（可选）
        """
        from sqlalchemy import select

        from app.models.system.plugin import Plugin as PluginModel
        from app.models.system.plugin_version import PluginVersion
        from app.plugins.context_factory import create_plugin_context
        from app.plugins.crypto import encrypt_plugin_config

        # 1. 复制到 plugins 目录（如果 source 已在 plugins/ 中则跳过）
        manifest = self._loader.load_manifest(source_path.name)
        plugin_name = manifest.name
        target_dir = PLUGINS_DIR / plugin_name

        # 如果 source_path 就是 target_dir（上传端点已复制好），跳过复制
        source_resolved = source_path.resolve()
        target_resolved = target_dir.resolve()
        already_in_place = source_resolved == target_resolved

        if not already_in_place:
            if target_dir.exists():
                existing = await self._db.execute(
                    select(PluginModel).where(
                        PluginModel.name == plugin_name,
                        PluginModel.is_deleted.is_(False),
                    )
                )
                if existing.scalar_one_or_none():
                    raise PluginInstallError(
                        message=f"Plugin '{plugin_name}' is already installed",
                    )
                logger.warning(
                    "Stale plugin directory found for %s (no DB record), cleaning up",
                    plugin_name,
                )
                shutil.rmtree(target_dir, ignore_errors=True)
            shutil.copytree(source_path, target_dir)
            logger.info("Copied plugin to %s", target_dir)
        else:
            # 文件已就位，仅检查是否已安装
            existing = await self._db.execute(
                select(PluginModel).where(
                    PluginModel.name == plugin_name,
                    PluginModel.is_deleted.is_(False),
                )
            )
            if existing.scalar_one_or_none():
                raise PluginInstallError(
                    message=f"Plugin '{plugin_name}' is already installed",
                )

        completed_steps: list[str] = ["copy"]

        try:
            # 2. 解析 manifest（已在上面完成）
            # 3. 校验兼容性 + 插件依赖检查
            from app.enums.plugin import PluginStatusEnum

            if manifest.dependencies.plugins:
                missing: list[str] = []
                for dep_name in manifest.dependencies.plugins:
                    dep_result = await self._db.execute(
                        select(PluginModel.status).where(
                            PluginModel.name == dep_name,
                            PluginModel.is_deleted.is_(False),
                        )
                    )
                    dep_row = dep_result.scalar_one_or_none()
                    if not dep_row:
                        missing.append(f"{dep_name} (not installed)")
                    elif dep_row != PluginStatusEnum.ENABLED.value:
                        missing.append(f"{dep_name} (not enabled)")
                if missing:
                    raise PluginInstallError(
                        message=f"Missing plugin dependencies: {', '.join(missing)}",
                    )
                logger.info("Plugin dependency check passed for %s", plugin_name)

            # 4. 安装 Python 依赖
            installed_packages: list[str] = []
            if manifest.dependencies.python:
                installed_packages = await self._install_python_deps(
                    plugin_name, manifest.dependencies.python
                )
                completed_steps.append("pip")

            # 5. 执行 Alembic 迁移
            migrations_dir = target_dir / "backend" / "migrations" / "versions"
            if migrations_dir.is_dir():
                await self._run_alembic_upgrade(plugin_name)
                completed_steps.append("alembic")

            # 6. 注册 AI features → SystemAgentAssignment
            if manifest.ai_requirements and manifest.ai_requirements.features:
                from app.models.system.agent_assignment import SystemAgentAssignment
                for feature in manifest.ai_requirements.features:
                    feature_code = f"plugin.{plugin_name}.{feature.feature_code}"
                    feature_name = feature.display_name.get(
                        "zh-CN", feature.display_name.get("en", feature.feature_code)
                    )
                    feature_desc = feature.description.get(
                        "zh-CN", feature.description.get("en", "")
                    )
                    # 检查是否已存在
                    existing = await self._db.execute(
                        select(SystemAgentAssignment.id).where(
                            SystemAgentAssignment.feature_code == feature_code,
                            SystemAgentAssignment.is_deleted.is_(False),
                        )
                    )
                    if not existing.scalar_one_or_none():
                        self._db.add(SystemAgentAssignment(
                            feature_code=feature_code,
                            feature_name=feature_name,
                            description=feature_desc,
                            agent_id=None,
                            tenant_id=None,
                            is_active=True,
                        ))
                await self._db.flush()
                completed_steps.append("ai_features")
                logger.info(
                    "Registered %d AI features for plugin %s",
                    len(manifest.ai_requirements.features), plugin_name,
                )

            # 7. 合并 i18n 翻译（预留，当前仅记录）
            locales = self._loader.load_locales(plugin_name)
            if locales:
                logger.info(
                    "Plugin %s has %d locale(s): %s",
                    plugin_name, len(locales), list(locales.keys()),
                )
                completed_steps.append("i18n")

            # 8. 实例化插件类并调用 on_install
            try:
                plugin_cls = self._loader.load_plugin_class(plugin_name)
                plugin_instance = plugin_cls()
                ctx = create_plugin_context(
                    plugin_name=plugin_name,
                    manifest=manifest,
                    db=self._db,
                    granted_capabilities=manifest.capabilities,
                )
                await plugin_instance.on_install(ctx)
                completed_steps.append("on_install")
            except Exception as exc:
                logger.warning(
                    "Plugin %s on_install failed (non-fatal): %s",
                    plugin_name, exc,
                )

            # 9. 写入 plugins 表
            initial_config = config or {}
            config_schema = manifest.config_schema
            if config_schema and initial_config:
                initial_config = encrypt_plugin_config(initial_config, config_schema)

            plugin = PluginModel(
                name=plugin_name,
                display_name=resolve_i18n(manifest.display_name),
                version=manifest.version,
                description=resolve_i18n(manifest.description) if manifest.description else None,
                author=manifest.author or None,
                icon=manifest.icon or None,
                icon_color=manifest.icon_color or None,
                homepage=manifest.homepage or None,
                repository_url=manifest.repository_url or None,
                license_text=manifest.license or None,
                tags=manifest.tags,
                scope=manifest.scope,
                status=PluginStatusEnum.INSTALLED.value,
                tier=PluginTierEnum.COMMUNITY.value,
                install_source=PluginInstallSourceEnum.LOCAL.value,
                manifest=manifest.model_dump(),
                config=initial_config,
                ai_requirements=manifest.ai_requirements.model_dump() if manifest.ai_requirements else None,
                pricing_type=manifest.pricing.type,
                pricing_info=manifest.pricing.model_dump() if manifest.pricing.type != "free" else None,
                error_count=0,
                installed_packages=installed_packages,
                granted_capabilities=manifest.capabilities,
                installed_at=utc_now(),
            )
            self._db.add(plugin)
            await self._db.flush()
            completed_steps.append("db")

            # 10. 备份版本
            version_record = PluginVersion(
                plugin_id=plugin.id,
                version=manifest.version,
                manifest=manifest.model_dump(),
                status="active",
                installed_at=utc_now(),
            )
            self._db.add(version_record)
            await self._db.flush()

            logger.info(
                "Plugin %s v%s installed successfully",
                plugin_name, manifest.version,
            )
            return plugin

        except Exception as exc:
            logger.error(
                "Plugin %s install failed at step %s: %s",
                plugin_name, completed_steps[-1] if completed_steps else "init", exc,
            )
            await self._rollback_install(plugin_name, completed_steps)
            if isinstance(exc, (PluginError, PluginInstallError, PluginDependencyError)):
                raise
            raise PluginInstallError(
                message=f"Failed to install plugin '{plugin_name}': {exc}",
            )

    # ================================================================
    # enable
    # ================================================================

    async def enable(self, plugin_id: int) -> None:
        """启用插件"""
        from sqlalchemy import select

        from app.enums.plugin import PluginStatusEnum
        from app.models.system.plugin import Plugin as PluginModel
        from app.plugins.context_factory import create_plugin_context
        from app.plugins.registry import ExtensionRegistry

        plugin = await self._db.execute(
            select(PluginModel).where(
                PluginModel.id == plugin_id,
                PluginModel.is_deleted.is_(False),
            )
        )
        plugin = plugin.scalar_one_or_none()
        if not plugin:
            from app.plugins.exceptions import PluginNotFoundError
            raise PluginNotFoundError(message=f"Plugin ID {plugin_id} not found")

        if plugin.status == PluginStatusEnum.ENABLED.value:
            return  # 已启用

        plugin_name = plugin.name
        manifest = self._loader.load_manifest(plugin_name)

        # DEBUG 模式：同步磁盘 plugin.yaml 的关键字段到 DB（scope/manifest 等）
        from app.core.config import settings
        if settings.DEBUG:
            from app.plugins.preview import resolve_i18n
            plugin.scope = manifest.scope
            plugin.manifest = manifest.model_dump()
            plugin.display_name = resolve_i18n(manifest.display_name)
            plugin.description = resolve_i18n(manifest.description) if manifest.description else plugin.description
            plugin.icon = manifest.icon or plugin.icon
            plugin.icon_color = manifest.icon_color or plugin.icon_color
            plugin.tags = manifest.tags
            await self._db.flush()

        # 检查依赖插件是否都已启用
        if manifest.dependencies.plugins:
            not_enabled: list[str] = []
            for dep_name in manifest.dependencies.plugins:
                dep_result = await self._db.execute(
                    select(PluginModel.status).where(
                        PluginModel.name == dep_name,
                        PluginModel.is_deleted.is_(False),
                    )
                )
                dep_status = dep_result.scalar_one_or_none()
                if dep_status != PluginStatusEnum.ENABLED.value:
                    not_enabled.append(dep_name)
            if not_enabled:
                raise PluginDependencyError(
                    message=f"Cannot enable '{plugin_name}': dependency plugins not enabled: {', '.join(not_enabled)}. Enable them first.",
                )

        registry = ExtensionRegistry.get_instance()

        # 注册所有扩展点
        ext = manifest.extensions

        # Skills（resolver + executor）
        for skill_ext in ext.skills:
            resolver_func = self._load_handler(plugin_name, skill_ext.entry_point + ".resolve") if skill_ext.entry_point else None
            executor_cls = self._load_plugin_executor(plugin_name, skill_ext.type)
            if resolver_func:
                registry.register_skill(
                    plugin_name, skill_ext.type, resolver_func, executor_cls,
                )

        # Adapters
        for adapter_ext in ext.adapters:
            adapter_cls = self._load_handler(plugin_name, adapter_ext.entry_point)
            if adapter_cls:
                registry.register_adapter(plugin_name, adapter_ext.provider_code, adapter_cls)

        # Storage Drivers
        for storage_ext in ext.storage_drivers:
            driver_cls = self._load_handler(plugin_name, storage_ext.entry_point)
            if driver_cls:
                registry.register_storage_driver(plugin_name, driver_cls)

        # Hooks
        for hook in ext.hooks:
            handler = self._load_handler(plugin_name, hook.handler)
            if handler:
                registry.register_hook(plugin_name, hook.point, handler, hook.priority)

        # Events
        for event in ext.events:
            handler = self._load_handler(plugin_name, event.handler)
            if handler:
                registry.register_event(plugin_name, event.event, handler)

        # Webhooks
        for webhook in ext.webhooks:
            handler = self._load_handler(plugin_name, webhook.handler)
            if handler:
                registry.register_webhook(
                    plugin_name, webhook.path, handler,
                    webhook.method, webhook.auth.model_dump(),
                )

        # Tasks
        for task_ext in ext.tasks:
            handler = self._load_handler(plugin_name, task_ext.handler)
            if handler:
                registry.register_task(
                    plugin_name, task_ext.name, handler,
                    task_ext.schedule_type,
                    task_ext.cron_expression,
                    task_ext.interval_seconds,
                    task_ext.queue,
                )

        # Notifications
        for notif_ext in ext.notifications:
            registry.register_notification(
                plugin_name, notif_ext.code,
                notif_ext.title, notif_ext.channels, notif_ext.category,
            )

        # Permissions
        for perm_ext in ext.permissions:
            registry.register_permission(
                plugin_name, perm_ext.code,
                perm_ext.name, perm_ext.scope, perm_ext.actions,
            )

        # 自动创建 SkillPackage + Skill 记录（供 Agent 绑定）
        if ext.skills:
            await self._ensure_plugin_skill_records(
                plugin_name, manifest, ext.skills, active=True,
            )

        # 调用 on_enable
        try:
            plugin_cls = self._loader.load_plugin_class(plugin_name)
            ctx = create_plugin_context(
                plugin_name=plugin_name,
                manifest=manifest,
                db=self._db,
                granted_capabilities=plugin.granted_capabilities or [],
            )
            await plugin_cls().on_enable(ctx)
        except Exception as exc:
            logger.warning("Plugin %s on_enable failed: %s", plugin_name, exc)

        # 更新状态
        plugin.status = PluginStatusEnum.ENABLED.value
        plugin.enabled_at = utc_now()
        plugin.error_message = None
        plugin.error_count = 0
        await self._db.flush()

        logger.info("Plugin %s enabled", plugin_name)

    # ================================================================
    # disable
    # ================================================================

    async def disable(self, plugin_id: int) -> None:
        """禁用插件"""
        from sqlalchemy import select

        from app.enums.plugin import PluginStatusEnum
        from app.models.system.plugin import Plugin as PluginModel
        from app.plugins.context_factory import create_plugin_context
        from app.plugins.registry import ExtensionRegistry

        plugin = await self._db.execute(
            select(PluginModel).where(
                PluginModel.id == plugin_id,
                PluginModel.is_deleted.is_(False),
            )
        )
        plugin = plugin.scalar_one_or_none()
        if not plugin:
            from app.plugins.exceptions import PluginNotFoundError
            raise PluginNotFoundError(message=f"Plugin ID {plugin_id} not found")

        if plugin.status == PluginStatusEnum.DISABLED.value:
            return

        plugin_name = plugin.name

        # 检查是否有其他插件依赖此插件
        dependents = await self._get_dependents(plugin_name)
        if dependents:
            raise PluginDependencyError(
                message=f"Cannot disable '{plugin_name}': plugins [{', '.join(dependents)}] depend on it. Disable them first.",
            )

        # 反注册所有扩展点
        ExtensionRegistry.get_instance().unregister_all(plugin_name)

        # 停用插件技能记录
        await self._deactivate_plugin_skill_records(plugin_name)

        # 调用 on_disable
        try:
            manifest = self._loader.load_manifest(plugin_name)
            plugin_cls = self._loader.load_plugin_class(plugin_name)
            ctx = create_plugin_context(
                plugin_name=plugin_name,
                manifest=manifest,
                db=self._db,
                granted_capabilities=plugin.granted_capabilities or [],
            )
            await plugin_cls().on_disable(ctx)
        except Exception as exc:
            logger.warning("Plugin %s on_disable failed: %s", plugin_name, exc)

        # 更新状态
        plugin.status = PluginStatusEnum.DISABLED.value
        plugin.enabled_at = None
        await self._db.flush()

        logger.info("Plugin %s disabled", plugin_name)

    # ================================================================
    # uninstall
    # ================================================================

    async def uninstall(
        self, plugin_id: int, confirm_data_delete: bool = False
    ) -> None:
        """卸载插件（14 步清理）"""
        from sqlalchemy import delete, select

        from app.models.system.plugin import Plugin as PluginModel
        from app.models.system.plugin_license import PluginLicense
        from app.models.system.plugin_tenant_assignment import PluginTenantAssignment
        from app.models.system.plugin_version import PluginVersion
        from app.plugins.context_factory import create_plugin_context
        from app.plugins.registry import ExtensionRegistry

        plugin = await self._db.execute(
            select(PluginModel).where(
                PluginModel.id == plugin_id,
                PluginModel.is_deleted.is_(False),
            )
        )
        plugin = plugin.scalar_one_or_none()
        if not plugin:
            from app.plugins.exceptions import PluginNotFoundError
            raise PluginNotFoundError(message=f"Plugin ID {plugin_id} not found")

        plugin_name = plugin.name

        # 1. 检查依赖（其他插件依赖此插件）
        dependents = await self._get_dependents(plugin_name)
        if dependents:
            raise PluginDependencyError(
                message=f"Cannot uninstall '{plugin_name}': plugins [{', '.join(dependents)}] depend on it. Uninstall them first.",
            )

        # 2. 禁用（如果启用中）
        if plugin.status == PluginStatusEnum.ENABLED.value:
            await self.disable(plugin_id)

        # 3. 调用 on_uninstall
        try:
            manifest = self._loader.load_manifest(plugin_name)
            plugin_cls = self._loader.load_plugin_class(plugin_name)
            ctx = create_plugin_context(
                plugin_name=plugin_name,
                manifest=manifest,
                db=self._db,
                granted_capabilities=plugin.granted_capabilities or [],
            )
            await plugin_cls().on_uninstall(ctx)
        except Exception as exc:
            logger.warning("Plugin %s on_uninstall failed: %s", plugin_name, exc)

        # 4. 反注册所有扩展点
        ExtensionRegistry.get_instance().unregister_all(plugin_name)

        # 5. 删除插件创建的 SkillPackage + Skill 记录
        await self._delete_plugin_skill_records(plugin_name)

        # 6-8. 移除 AI features / i18n / 通知模板 / 权限
        try:
            from app.models.system.agent_assignment import SystemAgentAssignment
            await self._db.execute(
                delete(SystemAgentAssignment).where(
                    SystemAgentAssignment.feature_code.like(f"plugin.{plugin_name}.%")
                )
            )
        except Exception as exc:
            logger.warning("Failed to cleanup AI features for %s: %s", plugin_name, exc)

        # 9. Alembic 回退
        if confirm_data_delete:
            try:
                await self._run_alembic_downgrade(plugin_name)
            except Exception as exc:
                logger.warning(
                    "Plugin %s alembic downgrade failed: %s", plugin_name, exc
                )

        # 10. 卸载独占 Python 依赖
        if plugin.installed_packages:
            await self._uninstall_python_deps(plugin_name, plugin.installed_packages)

        # 11-13. 删除关联记录
        await self._db.execute(
            delete(PluginVersion).where(PluginVersion.plugin_id == plugin_id)
        )
        await self._db.execute(
            delete(PluginTenantAssignment).where(
                PluginTenantAssignment.plugin_id == plugin_id
            )
        )
        await self._db.execute(
            delete(PluginLicense).where(PluginLicense.plugin_id == plugin_id)
        )

        # 14. 删除 plugins 记录 + 物理文件
        await self._db.execute(
            delete(PluginModel).where(PluginModel.id == plugin_id)
        )
        await self._db.flush()

        plugin_dir = PLUGINS_DIR / plugin_name
        if plugin_dir.exists():
            shutil.rmtree(plugin_dir, ignore_errors=True)

        # 清理 sys.modules 中的插件模块缓存
        from app.plugins.module_loader import unload_plugin_modules
        unload_plugin_modules(plugin_name)

        logger.info("Plugin %s uninstalled completely", plugin_name)

    # ================================================================
    # 依赖检查
    # ================================================================

    async def _get_dependents(self, plugin_name: str) -> list[str]:
        """
        查找依赖指定插件的所有已安装插件。

        扫描所有已安装插件的 manifest.dependencies.plugins，
        返回声明了对 plugin_name 依赖的插件名列表。
        """
        from sqlalchemy import select

        from app.models.system.plugin import Plugin as PluginModel

        result = await self._db.execute(
            select(PluginModel.name, PluginModel.manifest).where(
                PluginModel.name != plugin_name,
                PluginModel.is_deleted.is_(False),
            )
        )
        dependents: list[str] = []
        for row in result.all():
            name, manifest_data = row[0], row[1]
            if not manifest_data or not isinstance(manifest_data, dict):
                continue
            deps = manifest_data.get("dependencies", {})
            if isinstance(deps, dict):
                plugin_deps = deps.get("plugins", [])
                if isinstance(plugin_deps, list) and plugin_name in plugin_deps:
                    dependents.append(name)
        return dependents

    async def get_dependents(self, plugin_id: int) -> list[str]:
        """获取依赖指定插件的插件列表（API 用）"""
        from sqlalchemy import select

        from app.models.system.plugin import Plugin as PluginModel

        result = await self._db.execute(
            select(PluginModel.name).where(
                PluginModel.id == plugin_id,
                PluginModel.is_deleted.is_(False),
            )
        )
        name = result.scalar_one_or_none()
        if not name:
            return []
        return await self._get_dependents(name)

    async def get_dependencies(self, plugin_id: int) -> list[str]:
        """获取指定插件的依赖插件列表（API 用）"""
        from sqlalchemy import select

        from app.models.system.plugin import Plugin as PluginModel

        result = await self._db.execute(
            select(PluginModel.manifest).where(
                PluginModel.id == plugin_id,
                PluginModel.is_deleted.is_(False),
            )
        )
        manifest_data = result.scalar_one_or_none()
        if not manifest_data or not isinstance(manifest_data, dict):
            return []
        deps = manifest_data.get("dependencies", {})
        if isinstance(deps, dict):
            return deps.get("plugins", [])
        return []

    # ================================================================
    # 内部方法
    # ================================================================

    async def _install_python_deps(
        self, plugin_name: str, requirements: list[str]
    ) -> list[str]:
        """安装 Python 依赖到当前 venv"""
        installed: list[str] = []
        for req in requirements:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", req, "--quiet"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                raise PluginDependencyError(
                    message=f"Failed to install {req}: {result.stderr.strip()}",
                )
            installed.append(req)
            logger.info("Installed %s for plugin %s", req, plugin_name)
        return installed

    async def _uninstall_python_deps(
        self, plugin_name: str, packages: list[str]
    ) -> None:
        """卸载插件独占的 Python 依赖（引用计数检查）"""
        from sqlalchemy import select

        from app.models.system.plugin import Plugin as PluginModel

        # 收集其他插件的依赖
        result = await self._db.execute(
            select(PluginModel.installed_packages).where(
                PluginModel.name != plugin_name,
                PluginModel.is_deleted.is_(False),
            )
        )
        other_deps: set[str] = set()
        for row in result.scalars():
            if row:
                for req in row:
                    pkg = req.split(">=")[0].split("==")[0].split("<")[0].split(">")[0].strip()
                    other_deps.add(pkg.lower())

        for req in packages:
            pkg = req.split(">=")[0].split("==")[0].split("<")[0].split(">")[0].strip()
            if pkg.lower() not in other_deps:
                subprocess.run(
                    [sys.executable, "-m", "pip", "uninstall", pkg, "-y", "--quiet"],
                    capture_output=True,
                    timeout=60,
                )
                logger.info("Uninstalled %s (no longer needed)", pkg)
            else:
                logger.info("Kept %s (still needed by other plugins)", pkg)

    async def _run_alembic_upgrade(self, plugin_name: str) -> None:
        """执行插件 Alembic 迁移"""
        branch_label = f"plugin_{plugin_name.replace('-', '_')}"
        result = subprocess.run(
            ["alembic", "upgrade", f"{branch_label}@head"],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(PLUGINS_DIR.parent),
        )
        if result.returncode != 0:
            logger.warning(
                "Alembic upgrade for %s: %s", plugin_name, result.stderr.strip()
            )

    async def _run_alembic_downgrade(self, plugin_name: str) -> None:
        """回退插件 Alembic 迁移"""
        branch_label = f"plugin_{plugin_name.replace('-', '_')}"
        result = subprocess.run(
            ["alembic", "downgrade", f"{branch_label}@base"],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(PLUGINS_DIR.parent),
        )
        if result.returncode != 0:
            logger.warning(
                "Alembic downgrade for %s: %s", plugin_name, result.stderr.strip()
            )

    async def _rollback_install(
        self, plugin_name: str, completed_steps: list[str]
    ) -> None:
        """安装失败时的回滚"""
        logger.info(
            "Rolling back install for %s (steps: %s)", plugin_name, completed_steps
        )

        if "alembic" in completed_steps:
            try:
                await self._run_alembic_downgrade(plugin_name)
            except Exception as exc:
                logger.warning("Rollback alembic failed: %s", exc)

        if "pip" in completed_steps:
            # 不回滚 pip 安装（可能影响其他插件）
            pass

        if "copy" in completed_steps:
            target_dir = PLUGINS_DIR / plugin_name
            if target_dir.exists():
                shutil.rmtree(target_dir, ignore_errors=True)

    # ================================================================
    # 插件技能记录管理（SkillPackage + Skill）
    # ================================================================

    async def _ensure_plugin_skill_records(
        self,
        plugin_name: str,
        manifest,
        skill_extensions: list,
        active: bool = True,
    ) -> None:
        """
        确保插件的 SkillPackage 和 Skill 记录存在于 DB 中。

        - 如果已有 source_plugin=plugin_name 的 SkillPackage，则复用并更新状态
        - 否则创建新的 SkillPackage（scope=global, is_system=True）
        - 对每个 skill extension 创建或更新 Skill 记录
        """
        from sqlalchemy import select, update

        from app.models.ai.skill import Skill
        from app.models.ai.skill_package import SkillPackage
        from app.enums.common import ResourceScopeEnum
        from app.plugins.preview import resolve_i18n

        # 查找或创建 SkillPackage
        result = await self._db.execute(
            select(SkillPackage).where(
                SkillPackage.source_plugin == plugin_name,
                SkillPackage.is_deleted.is_(False),
            )
        )
        package = result.scalar_one_or_none()

        display_name = resolve_i18n(manifest.display_name)

        if not package:
            package = SkillPackage(
                name=display_name,
                description=resolve_i18n(manifest.description) if manifest.description else None,
                scope=ResourceScopeEnum.GLOBAL.value,
                source_plugin=plugin_name,
                is_system=True,
                is_active=active,
                tenant_id=None,
            )
            self._db.add(package)
            await self._db.flush()
            logger.info(
                "Created SkillPackage '%s' (id=%d) for plugin %s",
                package.name, package.id, plugin_name,
            )
        else:
            # 更新已有包的状态
            package.is_active = active
            package.name = display_name
            await self._db.flush()

        # 预加载包内所有已有的系统技能（用于匹配更新）
        existing_skills_result = await self._db.execute(
            select(Skill).where(
                Skill.package_id == package.id,
                Skill.is_system.is_(True),
                Skill.is_deleted.is_(False),
            )
        )
        existing_skills = list(existing_skills_result.scalars().all())

        # 对每个 skill extension 创建或更新 Skill 记录
        for skill_ext in skill_extensions:
            # 先按 name 匹配，再按 type 匹配，最后取第一个
            existing_skill = next(
                (s for s in existing_skills if s.name == (resolve_i18n(skill_ext.display_name) if skill_ext.display_name else skill_ext.name)),
                next((s for s in existing_skills if s.type == skill_ext.type), None),
            )
            if existing_skill is None and len(existing_skills) == 1 and len(skill_extensions) == 1:
                existing_skill = existing_skills[0]

            skill_display = resolve_i18n(skill_ext.display_name) if skill_ext.display_name else skill_ext.name
            skill_desc = resolve_i18n(skill_ext.description) if skill_ext.description else None

            if not existing_skill:
                skill = Skill(
                    package_id=package.id,
                    name=skill_display,
                    description=skill_desc,
                    type=skill_ext.type,
                    config=skill_ext.config_schema or {},
                    is_system=True,
                    is_active=active,
                    tenant_id=None,
                )
                self._db.add(skill)
                logger.info(
                    "Created Skill '%s' (type=%s) for plugin %s",
                    skill_display, skill_ext.type, plugin_name,
                )
            else:
                existing_skill.is_active = active
                existing_skill.name = skill_display
                existing_skill.description = skill_desc
                existing_skill.type = skill_ext.type

        await self._db.flush()

    async def _deactivate_plugin_skill_records(self, plugin_name: str) -> None:
        """禁用时：将插件的 SkillPackage 和 Skill 标记为不活跃"""
        from sqlalchemy import select, update

        from app.models.ai.skill import Skill
        from app.models.ai.skill_package import SkillPackage

        result = await self._db.execute(
            select(SkillPackage.id).where(
                SkillPackage.source_plugin == plugin_name,
                SkillPackage.is_deleted.is_(False),
            )
        )
        package_id = result.scalar_one_or_none()
        if not package_id:
            return

        # 停用 SkillPackage
        await self._db.execute(
            update(SkillPackage).where(
                SkillPackage.id == package_id,
            ).values(is_active=False)
        )

        # 停用包下所有 Skill
        await self._db.execute(
            update(Skill).where(
                Skill.package_id == package_id,
                Skill.is_deleted.is_(False),
            ).values(is_active=False)
        )

        await self._db.flush()
        logger.info("Deactivated skill records for plugin %s", plugin_name)

    async def _delete_plugin_skill_records(self, plugin_name: str) -> None:
        """卸载时：删除插件创建的 SkillPackage（级联删除 Skill）"""
        from sqlalchemy import delete, select

        from app.models.ai.skill import Skill
        from app.models.ai.skill_package import SkillPackage

        result = await self._db.execute(
            select(SkillPackage.id).where(
                SkillPackage.source_plugin == plugin_name,
                SkillPackage.is_deleted.is_(False),
            )
        )
        package_id = result.scalar_one_or_none()
        if not package_id:
            return

        # 先删子表 Skill，再删 SkillPackage
        await self._db.execute(
            delete(Skill).where(Skill.package_id == package_id)
        )
        await self._db.execute(
            delete(SkillPackage).where(SkillPackage.id == package_id)
        )
        await self._db.flush()
        logger.info("Deleted skill records for plugin %s", plugin_name)

    # ================================================================
    # 模块加载
    # ================================================================

    def _load_handler(self, plugin_name: str, handler_path: str):
        """加载插件处理函数 — 委托给统一加载器"""
        from app.plugins.module_loader import load_plugin_handler
        return load_plugin_handler(plugin_name, handler_path)

    def _load_plugin_executor(self, plugin_name: str, skill_type: str):
        """加载插件 executor 类 — 委托给统一加载器"""
        from app.plugins.module_loader import load_plugin_executor
        return load_plugin_executor(plugin_name, skill_type)
