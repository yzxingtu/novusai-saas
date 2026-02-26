"""
插件生命周期管理

install / enable / disable / uninstall 四个核心操作。
"""

from __future__ import annotations

import functools
import json
import shutil
import subprocess
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

import anyio

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
    PluginSecurityError,
)
from app.plugins.loader import PLUGINS_DIR, PluginLoader
from app.plugins.preview import resolve_i18n

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.system.plugin import Plugin

logger = get_logger(__name__)


_IS_WINDOWS = sys.platform == "win32"


async def _run_subprocess_async(
    *args: str,
    timeout: int = 120,
    cwd: str | None = None,
    text: bool = True,
    capture_output: bool = True,
    shell: bool | None = None,
) -> subprocess.CompletedProcess:
    """Run subprocess.run in a thread to avoid blocking the async event loop.

    Args:
        shell: Explicit shell mode. None = auto (_IS_WINDOWS for .cmd scripts).
               Pass False for direct binaries (e.g. sys.executable -m pip)
               to avoid shell metachar issues (>=, |, & etc.).
    """
    use_shell = shell if shell is not None else _IS_WINDOWS
    return await anyio.to_thread.run_sync(
        functools.partial(
            subprocess.run,
            list(args),
            capture_output=capture_output,
            text=text,
            timeout=timeout,
            cwd=cwd,
            shell=use_shell,
            encoding="utf-8" if text else None,
            errors="replace" if text else None,
        )
    )


# 插件级分布式锁（防止并发 enable/disable/uninstall）
_LOCK_PREFIX = "plugin:lifecycle:lock:"
_LOCK_TTL = 120  # 秒，自动过期防死锁
_UNLOCK_IF_OWNER_LUA = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
end
return 0
"""


@asynccontextmanager
async def _plugin_lock(plugin_id: int):
    """
    Redis 分布式锁，粒度为单个插件。

    获取失败时抛出 PluginError(409)，调用方无需手动释放。
    TTL 120s 自动过期防死锁。
    """
    from app.core.redis import get_redis_client
    from app.plugins.exceptions import PluginError

    key = f"{_LOCK_PREFIX}{plugin_id}"
    client = get_redis_client()
    owner_token = str(uuid.uuid4())
    acquired = await client.set(key, owner_token, nx=True, ex=_LOCK_TTL)
    if not acquired:
        raise PluginError(
            message=f"Plugin {plugin_id} is being modified by another operation. Please retry later.",
            status_code=409,
        )
    try:
        yield
    finally:
        try:
            await client.eval(_UNLOCK_IF_OWNER_LUA, 1, key, owner_token)
        except Exception as exc:
            logger.warning("Failed to release plugin lock %s safely: %s", key, exc)


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
        *,
        operator_id: int | None = None,
    ) -> Plugin:
        """
        安装插件（10 步流程）

        Args:
            source_path: 插件源目录（已解压）
            config: 初始配置（可选）
            operator_id: 操作者管理员 ID（用于 WebSocket 进度推送）
        """
        from sqlalchemy import select

        from app.models.system.plugin import Plugin as PluginModel
        from app.models.system.plugin_version import PluginVersion
        from app.plugins.context_factory import create_plugin_context
        from app.plugins.crypto import encrypt_plugin_config

        # 1. 复制到 plugins 目录（如果 source 已在 plugins/ 中则跳过）
        manifest = self._loader.load_manifest_from_path(source_path)
        plugin_name = manifest.name
        target_dir = PLUGINS_DIR / plugin_name

        # 防止并发安装同名插件（基于 Redis 名称锁）
        from app.core.redis import get_redis_client
        _install_lock_key = f"plugin:install:lock:{plugin_name}"
        _redis = get_redis_client()
        _install_owner = str(uuid.uuid4())
        _install_locked = await _redis.set(
            _install_lock_key, _install_owner, nx=True, ex=300,
        )
        if not _install_locked:
            raise PluginInstallError(
                message=f"Plugin '{plugin_name}' is already being installed by another operation. Please retry later.",
            )

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

        from app.plugins.progress import PluginProgressEmitter
        emitter = PluginProgressEmitter(operator_id, plugin_name, "install")
        await emitter.emit_step("copy", "success", f"Plugin files copied to {target_dir}")

        try:
            # 2. 解析 manifest（已在上面完成）
            # 3. 校验兼容性 + 插件依赖检查
            from app.enums.plugin import PluginStatusEnum

            # 3a. 平台版本兼容性检查
            if manifest.compatibility and manifest.compatibility.platform_version != "*":
                try:
                    from packaging.specifiers import SpecifierSet
                    from packaging.version import Version
                    from app.core.config import settings

                    platform_spec = SpecifierSet(manifest.compatibility.platform_version)
                    if Version(settings.APP_VERSION) not in platform_spec:
                        raise PluginInstallError(
                            message=f"Plugin '{plugin_name}' requires platform version "
                            f"{manifest.compatibility.platform_version}, "
                            f"but current is {settings.APP_VERSION}",
                        )
                except ImportError:
                    logger.warning("packaging library not available, skipping version check")

            # 3b. 插件依赖检查（dependencies.plugins — 名称级）
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

            # 3c. 插件依赖版本检查（compatibility.requires — 含版本约束）
            if manifest.compatibility and manifest.compatibility.requires:
                version_errors: list[str] = []
                for req in manifest.compatibility.requires:
                    dep_result = await self._db.execute(
                        select(PluginModel.version, PluginModel.status).where(
                            PluginModel.name == req.plugin,
                            PluginModel.is_deleted.is_(False),
                        )
                    )
                    dep_row = dep_result.one_or_none()
                    if not dep_row:
                        version_errors.append(f"{req.plugin} (not installed)")
                    elif dep_row[1] != PluginStatusEnum.ENABLED.value:
                        version_errors.append(f"{req.plugin} (not enabled)")
                    elif req.version != "*":
                        try:
                            from packaging.specifiers import SpecifierSet
                            from packaging.version import Version

                            spec = SpecifierSet(req.version)
                            if Version(dep_row[0]) not in spec:
                                version_errors.append(
                                    f"{req.plugin} requires {req.version}, "
                                    f"installed {dep_row[0]}"
                                )
                        except Exception as exc:
                            logger.warning(
                                "Version check failed for %s: %s", req.plugin, exc,
                            )
                if version_errors:
                    raise PluginDependencyError(
                        message=f"Plugin dependency version mismatch: {'; '.join(version_errors)}",
                    )

                logger.info("Plugin dependency check passed for %s", plugin_name)

            # 3d. 安全扫描（高风险 fail-close）
            from app.plugins.security_scan import scan_plugin_directory

            scan_target = target_dir if target_dir.is_dir() else source_path
            scan_result = scan_plugin_directory(scan_target)
            if scan_result.has_warnings:
                top_warnings = "; ".join(scan_result.warnings[:5])
                raise PluginSecurityError(
                    message=(
                        f"Plugin '{plugin_name}' blocked by security scan: "
                        f"{top_warnings}"
                    ),
                )

            # 4. 记录声明的依赖（pip/npm 实际安装延迟到 enable 阶段）
            installed_packages = manifest.dependencies.python or []

            # 5. 执行 Alembic 迁移
            migrations_dir = target_dir / "backend" / "migrations" / "versions"
            if migrations_dir.is_dir():
                await emitter.emit_step("alembic", "running", "Running database migrations...")
                await self.run_alembic_upgrade(plugin_name)
                await emitter.emit_step("alembic", "success", "Database migrations complete")
                completed_steps.append("alembic")

            # 6. 注册 AI features → SystemAgentAssignment
            if manifest.ai_requirements and manifest.ai_requirements.features:
                await emitter.emit_step("ai_features", "running", "Registering AI features...")
                from app.models.system.agent_assignment import SystemAgentAssignment
                for feature in manifest.ai_requirements.features:
                    feature_code = f"plugin.{plugin_name}.{feature.feature_code}"
                    feature_name = feature.display_name.get(
                        "zh-CN", feature.display_name.get("en", feature.feature_code)
                    )
                    feature_desc = feature.description.get(
                        "zh-CN", feature.description.get("en", "")
                    )
                    # 检查全局默认是否已存在（只查 tenant_id IS NULL）
                    existing = await self._db.execute(
                        select(SystemAgentAssignment.id).where(
                            SystemAgentAssignment.feature_code == feature_code,
                            SystemAgentAssignment.tenant_id.is_(None),
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
                await emitter.emit_step("ai_features", "success", f"Registered {len(manifest.ai_requirements.features)} AI features")
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
            await emitter.emit_step("on_install", "running", "Running plugin install hook...")
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
                await emitter.emit_step("on_install", "success", "Install hook completed")
            except Exception as exc:
                await emitter.emit_step("on_install", "success", f"Install hook warning: {exc}")
                logger.warning(
                    "Plugin %s on_install failed (non-fatal): %s",
                    plugin_name, exc,
                )

            # 9. 写入 plugins 表
            await emitter.emit_step("db", "running", "Writing plugin record...")
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

            await emitter.emit_step("db", "success", "Plugin record saved")

            logger.info(
                "Plugin %s v%s installed successfully",
                plugin_name, manifest.version,
            )
            await emitter.emit_done(f"Plugin {plugin_name} v{manifest.version} installed successfully")
            return plugin

        except Exception as exc:
            logger.error(
                "Plugin %s install failed at step %s: %s",
                plugin_name, completed_steps[-1] if completed_steps else "init", exc,
            )
            await emitter.emit_error(str(exc))
            await self._rollback_install(plugin_name, completed_steps)
            if isinstance(exc, (PluginError, PluginInstallError, PluginDependencyError)):
                raise
            raise PluginInstallError(
                message=f"Failed to install plugin '{plugin_name}': {exc}",
            )
        finally:
            # 释放安装锁
            try:
                await _redis.eval(_UNLOCK_IF_OWNER_LUA, 1, _install_lock_key, _install_owner)
            except Exception:
                pass

    # ================================================================
    # enable
    # ================================================================

    async def enable(self, plugin_id: int, *, operator_id: int | None = None) -> None:
        """启用插件（带分布式锁）"""
        async with _plugin_lock(plugin_id):
            await self._enable_impl(plugin_id, operator_id=operator_id)

    async def _enable_impl(self, plugin_id: int, *, operator_id: int | None = None) -> None:
        """启用插件实现（调用方须持锁）"""
        from sqlalchemy import select

        from app.enums.plugin import PluginStatusEnum
        from app.models.system.plugin import Plugin as PluginModel
        from app.plugins.context_factory import create_plugin_context
        from app.plugins.progress import PluginProgressEmitter
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
        emitter = PluginProgressEmitter(operator_id, plugin_name, "enable")
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
            plugin.ai_requirements = manifest.ai_requirements.model_dump() if manifest.ai_requirements else plugin.ai_requirements
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

        # 检查 compatibility.requires 版本约束
        if manifest.compatibility and manifest.compatibility.requires:
            version_errors: list[str] = []
            for req in manifest.compatibility.requires:
                dep_result = await self._db.execute(
                    select(PluginModel.version, PluginModel.status).where(
                        PluginModel.name == req.plugin,
                        PluginModel.is_deleted.is_(False),
                    )
                )
                dep_row = dep_result.one_or_none()
                if not dep_row:
                    version_errors.append(f"{req.plugin} (not installed)")
                elif dep_row[1] != PluginStatusEnum.ENABLED.value:
                    version_errors.append(f"{req.plugin} (not enabled)")
                elif req.version != "*":
                    try:
                        from packaging.specifiers import SpecifierSet
                        from packaging.version import Version

                        if Version(dep_row[0]) not in SpecifierSet(req.version):
                            version_errors.append(
                                f"{req.plugin} requires {req.version}, "
                                f"installed {dep_row[0]}"
                            )
                    except Exception as exc:
                        logger.warning(
                            "Version check failed for %s: %s", req.plugin, exc,
                        )
            if version_errors:
                raise PluginDependencyError(
                    message=f"Cannot enable '{plugin_name}': version mismatch: {'; '.join(version_errors)}",
                )

        # 安装 Python 依赖
        if manifest.dependencies.python:
            await emitter.emit_step("pip", "running", f"Installing {len(manifest.dependencies.python)} Python package(s)...")
            try:
                await self._install_python_deps(plugin_name, manifest.dependencies.python)
            except Exception as exc:
                await emitter.emit_error(f"pip install failed: {exc}")
                raise
            await emitter.emit_step("pip", "success", f"Installed {len(manifest.dependencies.python)} package(s)")
        else:
            await emitter.emit_step("pip", "success", "No Python dependencies")

        # 安装前端 npm 依赖（dev 模式）
        frontend_ext = manifest.extensions.frontend if manifest.extensions else None
        npm_deps = frontend_ext.npm_dependencies if frontend_ext else []
        if npm_deps:
            await emitter.emit_step("npm", "running", f"Installing {len(npm_deps)} npm package(s)...")
            await self._install_npm_deps(plugin_name, npm_deps)
            await emitter.emit_step("npm", "success", f"Installed {len(npm_deps)} npm package(s)")
        else:
            await emitter.emit_step("npm", "success", "No npm dependencies")

        # 注册扩展点
        await emitter.emit_step("extensions", "running", "Registering extensions...")
        registry = ExtensionRegistry.get_instance()

        from app.plugins._extension_registrar import (
            get_failed_extensions,
            register_all_extensions,
        )

        register_all_extensions(registry, manifest, plugin_name)

        # fail-close：若有关键扩展加载失败，回滚注册并标记 error
        failed = get_failed_extensions(plugin_name)
        if failed:
            registry.unregister_all(plugin_name)
            failed_summary = "; ".join(
                f"{f['type']}:{f['entry_point']}" for f in failed[:5]
            )
            plugin.status = PluginStatusEnum.ERROR.value
            plugin.error_message = f"Extension load failed: {failed_summary}"
            plugin.error_count += 1
            await self._db.flush()
            await emitter.emit_error(f"{len(failed)} extension(s) failed to load")
            raise PluginError(
                message=f"Cannot enable '{plugin_name}': {len(failed)} extension(s) failed to load: {failed_summary}",
            )

        # 自动创建 SkillPackage + Skill 记录（供 Agent 绑定）
        ext = manifest.extensions
        if ext.skills:
            await self._ensure_plugin_skill_records(
                plugin_name, manifest, ext.skills, active=True,
            )

        await emitter.emit_step("extensions", "success", f"Registered {registry.get_registered_count(plugin_name)} extension(s)")

        # 调用 on_enable
        await emitter.emit_step("on_enable", "running", "Running enable hook...")
        try:
            plugin_cls = self._loader.load_plugin_class(plugin_name)
            ctx = create_plugin_context(
                plugin_name=plugin_name,
                manifest=manifest,
                db=self._db,
                granted_capabilities=plugin.granted_capabilities or [],
            )
            await plugin_cls().on_enable(ctx)
            await emitter.emit_step("on_enable", "success", "Enable hook completed")
        except Exception as exc:
            # on_enable 失败：回滚注册，标记 error 状态
            logger.warning("Plugin %s on_enable failed: %s", plugin_name, exc)
            registry.unregister_all(plugin_name)
            plugin.status = PluginStatusEnum.ERROR.value
            plugin.error_message = f"on_enable failed: {exc}"
            plugin.error_count += 1
            await self._db.flush()
            await emitter.emit_error(f"on_enable failed: {exc}")
            raise PluginError(
                message=f"Plugin '{plugin_name}' on_enable failed: {exc}",
            )

        # 更新状态
        plugin.status = PluginStatusEnum.ENABLED.value
        plugin.enabled_at = utc_now()
        plugin.error_message = None
        plugin.error_count = 0
        await self._db.flush()

        # 清除路由正则缓存（DEBUG 模式下路由可能变化）
        from app.plugins.api_dispatcher import _compile_route_regex
        _compile_route_regex.cache_clear()

        await emitter.emit_done(f"Plugin {plugin_name} enabled successfully")
        logger.info("Plugin %s enabled", plugin_name)

    # ================================================================
    # disable
    # ================================================================

    async def disable(self, plugin_id: int, *, operator_id: int | None = None) -> None:
        """禁用插件（带分布式锁）"""
        async with _plugin_lock(plugin_id):
            await self._disable_impl(plugin_id, operator_id=operator_id)

    async def _disable_impl(self, plugin_id: int, *, operator_id: int | None = None) -> None:
        """禁用插件实现（调用方须持锁）"""
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

        # 检查存储驱动是否正在被使用
        await self._check_storage_driver_in_use(plugin_name, plugin.manifest or {})

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

        # 禁用不卸载依赖 — 依赖仅在 uninstall 时清理
        # 这样用户重新启用时无需等待重新安装

        # 更新状态
        plugin.status = PluginStatusEnum.DISABLED.value
        plugin.enabled_at = None
        await self._db.flush()

        logger.info("Plugin %s disabled", plugin_name)

    # ================================================================
    # uninstall
    # ================================================================

    async def uninstall(
        self, plugin_id: int, confirm_data_delete: bool = False, *, operator_id: int | None = None,
    ) -> None:
        """卸载插件（带分布式锁）"""
        async with _plugin_lock(plugin_id):
            await self._uninstall_impl(plugin_id, confirm_data_delete, operator_id=operator_id)

    async def _uninstall_impl(
        self, plugin_id: int, confirm_data_delete: bool = False, *, operator_id: int | None = None,
    ) -> None:
        """卸载插件实现（14 步清理）"""
        from sqlalchemy import delete, select

        from app.models.system.plugin import Plugin as PluginModel
        from app.models.system.plugin_license import PluginLicense
        from app.models.system.resource_tenant_assignment import ResourceTenantAssignment
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

        from app.plugins.progress import PluginProgressEmitter
        emitter = PluginProgressEmitter(operator_id, plugin_name, "uninstall")

        # 1. 检查依赖（其他插件依赖此插件）
        dependents = await self._get_dependents(plugin_name)
        if dependents:
            raise PluginDependencyError(
                message=f"Cannot uninstall '{plugin_name}': plugins [{', '.join(dependents)}] depend on it. Uninstall them first.",
            )

        # 2. 禁用（如果启用中）
        if plugin.status == PluginStatusEnum.ENABLED.value:
            await emitter.emit_step("disable", "running", "Disabling plugin...")
            await self._disable_impl(plugin_id)
            await emitter.emit_step("disable", "success", "Plugin disabled")

        # 3. 调用 on_uninstall
        await emitter.emit_step("on_uninstall", "running", "Running uninstall hook...")
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
            await emitter.emit_step("on_uninstall", "success", "Uninstall hook completed")
        except Exception as exc:
            await emitter.emit_step("on_uninstall", "success", f"Uninstall hook warning: {exc}")
            logger.warning("Plugin %s on_uninstall failed: %s", plugin_name, exc)

        # 4. 反注册所有扩展点
        await emitter.emit_step("cleanup_extensions", "running", "Unregistering extensions...")
        ExtensionRegistry.get_instance().unregister_all(plugin_name)
        await emitter.emit_step("cleanup_extensions", "success", "Extensions unregistered")

        # 5. 删除插件创建的 SkillPackage + Skill 记录
        await emitter.emit_step("cleanup_skills", "running", "Removing skill records...")
        await self._delete_plugin_skill_records(plugin_name)
        await emitter.emit_step("cleanup_skills", "success", "Skill records removed")

        # 6-8. 移除 AI features
        await emitter.emit_step("cleanup_ai_features", "running", "Removing AI features...")
        try:
            from app.models.system.agent_assignment import SystemAgentAssignment
            await self._db.execute(
                delete(SystemAgentAssignment).where(
                    SystemAgentAssignment.feature_code.like(f"plugin.{plugin_name}.%")
                )
            )
            await emitter.emit_step("cleanup_ai_features", "success", "AI features removed")
        except Exception as exc:
            await emitter.emit_step("cleanup_ai_features", "success", f"AI features warning: {exc}")
            logger.warning("Failed to cleanup AI features for %s: %s", plugin_name, exc)

        # 9. 数据库清理
        await emitter.emit_step("cleanup_db", "running", "Cleaning up database tables...")
        await self._cleanup_plugin_database(plugin_name)
        await emitter.emit_step("cleanup_db", "success", "Database tables cleaned")

        # 10. 卸载 Python 依赖（共享检查：其他插件/项目/反向依赖）
        if plugin.installed_packages:
            await emitter.emit_step("cleanup_pip", "running", "Uninstalling Python dependencies...")
            await self._uninstall_python_deps(plugin_name, plugin.installed_packages)
            await emitter.emit_step("cleanup_pip", "success", "Python dependencies cleaned")

        # 10.5 卸载 npm 依赖（共享检查：其他插件是否也声明了同名包）
        try:
            manifest = self._loader.load_manifest(plugin_name)
            frontend_ext = manifest.extensions.frontend if manifest.extensions else None
            npm_deps = frontend_ext.npm_dependencies if frontend_ext else []
            if npm_deps:
                await emitter.emit_step("cleanup_npm", "running", "Uninstalling npm dependencies...")
                await self._uninstall_npm_deps(plugin_name, npm_deps)
                await emitter.emit_step("cleanup_npm", "success", "npm dependencies cleaned")
        except Exception as exc:
            logger.warning("Failed to cleanup npm deps for %s: %s", plugin_name, exc)

        # 11-13. 删除关联记录
        await emitter.emit_step("cleanup_records", "running", "Removing plugin records...")
        await self._db.execute(
            delete(PluginVersion).where(PluginVersion.plugin_id == plugin_id)
        )
        await self._db.execute(
            delete(ResourceTenantAssignment).where(
                ResourceTenantAssignment.resource_type == "plugin",
                ResourceTenantAssignment.resource_id == plugin_id,
            )
        )
        await self._db.execute(
            delete(PluginLicense).where(PluginLicense.plugin_id == plugin_id)
        )
        await emitter.emit_step("cleanup_records", "success", "Plugin records removed")

        # 14. 删除 plugins 记录 + 物理文件
        await emitter.emit_step("cleanup_files", "running", "Removing plugin files...")
        await self._db.execute(
            delete(PluginModel).where(PluginModel.id == plugin_id)
        )
        await self._db.flush()

        plugin_dir = PLUGINS_DIR / plugin_name
        if plugin_dir.exists():
            shutil.rmtree(plugin_dir, ignore_errors=True)

        from app.plugins.module_loader import unload_plugin_modules
        unload_plugin_modules(plugin_name)
        await emitter.emit_step("cleanup_files", "success", "Plugin files removed")

        logger.info("Plugin %s uninstalled completely", plugin_name)
        await emitter.emit_done(f"Plugin {plugin_name} uninstalled completely")

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

    async def _check_storage_driver_in_use(
        self, plugin_name: str, manifest_data: dict
    ) -> None:
        """
        Check if this plugin provides storage drivers that are currently in use.

        Queries platform_storage_driver and all tenant tenant_storage_driver configs.
        If any reference a driver code from this plugin, block the disable.
        """
        extensions = manifest_data.get("extensions", {})
        storage_drivers = extensions.get("storage_drivers", [])
        if not storage_drivers:
            return

        driver_codes = {
            sd.get("code") for sd in storage_drivers if sd.get("code")
        }
        if not driver_codes:
            return

        from app.configs.service import ConfigService

        config_service = ConfigService(self._db)

        # Check platform storage driver
        platform_driver = await config_service.get_platform_config(
            "platform_storage_driver", default="local"
        )
        if str(platform_driver) in driver_codes:
            raise PluginError(
                message=(
                    f"Cannot disable '{plugin_name}': storage driver "
                    f"'{platform_driver}' is used as platform storage driver. "
                    f"Switch to another driver first."
                ),
            )

        # Check tenant storage drivers
        from sqlalchemy import select, and_

        from app.models.system.config import SystemConfig, SystemConfigValue

        config_result = await self._db.execute(
            select(SystemConfig.id).where(
                SystemConfig.key == "tenant_storage_driver",
                SystemConfig.is_deleted.is_(False),
            )
        )
        config_id = config_result.scalar_one_or_none()
        if config_id:
            values_result = await self._db.execute(
                select(SystemConfigValue.tenant_id, SystemConfigValue.value).where(
                    and_(
                        SystemConfigValue.config_id == config_id,
                        SystemConfigValue.is_deleted.is_(False),
                    )
                )
            )
            for row in values_result.all():
                tenant_id, raw_value = row
                if raw_value:
                    try:
                        val = json.loads(raw_value)
                    except (json.JSONDecodeError, TypeError):
                        val = raw_value
                    if str(val) in driver_codes:
                        # Also check if that tenant is actually using custom mode
                        mode = await config_service.get_tenant_config(
                            tenant_id, "tenant_storage_mode", default="platform"
                        )
                        if str(mode) in ("custom", "admin_override"):
                            raise PluginError(
                                message=(
                                    f"Cannot disable '{plugin_name}': storage driver "
                                    f"'{val}' is used by tenant {tenant_id}. "
                                    f"Switch the tenant to another driver first."
                                ),
                            )

    async def _install_python_deps(
        self, plugin_name: str, requirements: list[str]
    ) -> list[str]:
        """安装 Python 依赖到当前 venv"""
        from packaging.requirements import Requirement

        installed: list[str] = []
        for req in requirements:
            normalized_req = req.strip()
            try:
                req_obj = Requirement(normalized_req)
            except Exception as exc:
                raise PluginDependencyError(
                    message=f"Invalid requirement '{normalized_req}': {exc}",
                ) from exc

            if req_obj.url:
                raise PluginDependencyError(
                    message=(
                        f"Direct URL requirement is not allowed for plugin '{plugin_name}': "
                        f"{normalized_req}"
                    ),
                )

            result = await _run_subprocess_async(
                sys.executable, "-m", "pip", "install", normalized_req, "--quiet",
                timeout=120,
                shell=False,
            )
            if result.returncode != 0:
                raise PluginDependencyError(
                    message=f"Failed to install {normalized_req}: {result.stderr.strip()}",
                )
            installed.append(normalized_req)
            logger.info("Installed %s for plugin %s", normalized_req, plugin_name)
        return installed

    async def _install_npm_deps(
        self, plugin_name: str, packages: list[str]
    ) -> None:
        """安装插件声明的 npm 依赖到宿主前端项目（仅 dev 模式）

        生产环境插件使用预编译的 UMD 包（dist/index.js），不需要 npm 依赖。
        dev 模式下 Vite 直接编译插件 SFC 源码，需要宿主 node_modules 提供依赖。
        """
        from app.core.config import settings

        if not settings.DEBUG:
            logger.info(
                "Skipping npm deps install for %s (production mode uses UMD bundles)",
                plugin_name,
            )
            return

        if not packages:
            return

        # 定位前端项目根目录: backend/ 的兄弟目录 frontend/
        frontend_root = PLUGINS_DIR.parent.parent / "frontend"
        if not frontend_root.is_dir():
            logger.warning(
                "Frontend directory not found at %s, skipping npm deps for %s",
                frontend_root, plugin_name,
            )
            return

        # 检查 pnpm 是否可用
        try:
            await _run_subprocess_async(
                "pnpm", "--version",
                timeout=10,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            logger.warning("pnpm not found, skipping npm deps install for %s", plugin_name)
            return

        # pnpm add <packages> --filter=@vben/web-antd
        cmd = ["pnpm", "add", *packages, "--filter=@vben/web-antd"]
        logger.info("Installing npm deps for %s: %s", plugin_name, " ".join(packages))

        try:
            result = await _run_subprocess_async(
                *cmd,
                timeout=120,
                cwd=str(frontend_root),
            )
            if result.returncode != 0:
                err = result.stderr.strip() or result.stdout.strip()
                logger.warning(
                    "npm deps install for %s failed (non-fatal): %s",
                    plugin_name, err[:500],
                )
            else:
                logger.info("npm deps installed for %s", plugin_name)
        except subprocess.TimeoutExpired:
            logger.warning("npm deps install for %s timed out", plugin_name)
        except Exception as exc:
            logger.warning("npm deps install for %s failed: %s", plugin_name, exc)

    @staticmethod
    def _normalize_pkg_name(raw: str) -> str:
        """Normalize a pip requirement string to a lowercase package name.

        Handles version specifiers (>=, ==, <, >, !=, ~=) and PEP 503 name normalization
        (hyphens, underscores, dots → unified lowercase).
        """
        import re
        pkg = re.split(r"[><=!~;@\[]", raw, maxsplit=1)[0].strip()
        return re.sub(r"[-_.]+", "-", pkg).lower()

    def _load_project_requirements(self) -> set[str]:
        """Load package names from the main project requirements.txt."""
        protected: set[str] = set()
        req_file = PLUGINS_DIR.parent / "requirements.txt"
        if not req_file.is_file():
            return protected
        try:
            for line in req_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("-"):
                    continue
                protected.add(self._normalize_pkg_name(line))
        except Exception as exc:
            logger.warning("Failed to read requirements.txt: %s", exc)
        return protected

    async def _uninstall_python_deps(
        self, plugin_name: str, packages: list[str]
    ) -> None:
        """卸载插件独占的 Python 依赖（三层安全检查）

        安全策略（任一命中则保留不删）：
        1. 其他已安装插件的 installed_packages 中声明了同名包
        2. 主项目 requirements.txt 中声明了同名包
        3. pip show 的 Required-by 非空（有其他包反向依赖它）
        """
        from sqlalchemy import select

        from app.models.system.plugin import Plugin as PluginModel

        # Layer 1: 收集其他插件的依赖
        result = await self._db.execute(
            select(PluginModel.installed_packages).where(
                PluginModel.name != plugin_name,
                PluginModel.is_deleted.is_(False),
            )
        )
        other_plugin_deps: set[str] = set()
        for row in result.scalars():
            if row:
                for req in row:
                    other_plugin_deps.add(self._normalize_pkg_name(req))

        # Layer 2: 主项目 requirements.txt 保护名单
        project_deps = self._load_project_requirements()

        for req in packages:
            pkg = self._normalize_pkg_name(req)
            if not pkg:
                continue

            # Check 1: other plugin needs it
            if pkg in other_plugin_deps:
                logger.info("Kept %s (still needed by other plugins)", pkg)
                continue

            # Check 2: main project needs it
            if pkg in project_deps:
                logger.info("Kept %s (declared in project requirements.txt)", pkg)
                continue

            # Check 3: pip reverse dependency check
            try:
                pip_result = await _run_subprocess_async(
                    sys.executable, "-m", "pip", "show", pkg,
                    timeout=30,
                    shell=False,
                )
                if pip_result.returncode == 0:
                    for line in pip_result.stdout.splitlines():
                        if line.startswith("Required-by:"):
                            required_by = line.split(":", 1)[1].strip()
                            if required_by:
                                logger.info(
                                    "Kept %s (Required-by: %s)", pkg, required_by,
                                )
                                break
                    else:
                        # No Required-by found or empty → safe to remove
                        await _run_subprocess_async(
                            sys.executable, "-m", "pip", "uninstall", pkg, "-y", "--quiet",
                            timeout=60,
                            shell=False,
                        )
                        logger.info("Uninstalled %s (no longer needed)", pkg)
                else:
                    logger.info("Package %s not installed, skipping", pkg)
            except Exception as exc:
                logger.warning("Failed to check/uninstall %s: %s", pkg, exc)

    async def _uninstall_npm_deps(
        self, plugin_name: str, packages: list[str]
    ) -> None:
        """卸载插件独占的 npm 依赖（仅 dev 模式，带共享检查）

        安全策略（任一命中则保留不删）：
        1. 其他已启用/已安装插件的 manifest 中声明了同名 npm 包
        2. 宿主 package.json 的 dependencies 中声明了同名包（非插件安装的）
        """
        from app.core.config import settings

        if not settings.DEBUG:
            return

        if not packages:
            return

        frontend_root = PLUGINS_DIR.parent.parent / "frontend"
        if not frontend_root.is_dir():
            return

        # Layer 1: 收集其他插件声明的 npm 依赖
        from sqlalchemy import select
        from app.models.system.plugin import Plugin as PluginModel

        result = await self._db.execute(
            select(PluginModel.manifest).where(
                PluginModel.name != plugin_name,
                PluginModel.is_deleted.is_(False),
            )
        )
        other_npm_deps: set[str] = set()
        for manifest_data in result.scalars():
            if not manifest_data or not isinstance(manifest_data, dict):
                continue
            ext = manifest_data.get("extensions", {})
            fe = ext.get("frontend", {}) if isinstance(ext, dict) else {}
            npm_list = fe.get("npm_dependencies", []) if isinstance(fe, dict) else []
            if isinstance(npm_list, list):
                other_npm_deps.update(npm_list)

        # Layer 2: 读取宿主 package.json 的原始 dependencies（排除插件安装的）
        host_pkg_json = frontend_root / "apps" / "web-antd" / "package.json"
        host_deps: set[str] = set()
        if host_pkg_json.is_file():
            try:
                import json as _json
                pkg_data = _json.loads(host_pkg_json.read_text(encoding="utf-8"))
                for dep_key in ("dependencies", "devDependencies", "peerDependencies"):
                    deps_dict = pkg_data.get(dep_key, {})
                    if isinstance(deps_dict, dict):
                        host_deps.update(deps_dict.keys())
            except Exception as exc:
                logger.warning("Failed to read host package.json: %s", exc)

        to_remove: list[str] = []
        for pkg in packages:
            if pkg in other_npm_deps:
                logger.info("Kept npm %s (still needed by other plugins)", pkg)
                continue
            # 不移除宿主原有依赖（防止删除非插件安装的包）
            # 注意：插件安装时会加入 package.json，所以这里仅检查其他插件是否也需要
            to_remove.append(pkg)

        if not to_remove:
            return

        try:
            await _run_subprocess_async(
                "pnpm", "--version",
                timeout=10,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            logger.warning("pnpm not found, skipping npm deps removal for %s", plugin_name)
            return

        cmd = ["pnpm", "remove", *to_remove, "--filter=@vben/web-antd"]
        logger.info("Removing npm deps for %s: %s", plugin_name, " ".join(to_remove))

        try:
            result = await _run_subprocess_async(
                *cmd,
                timeout=120,
                cwd=str(frontend_root),
            )
            if result.returncode != 0:
                err = result.stderr.strip() or result.stdout.strip()
                logger.warning(
                    "npm deps removal for %s failed (non-fatal): %s",
                    plugin_name, err[:500],
                )
            else:
                logger.info("npm deps removed for %s: %s", plugin_name, ", ".join(to_remove))
        except subprocess.TimeoutExpired:
            logger.warning("npm deps removal for %s timed out", plugin_name)
        except Exception as exc:
            logger.warning("npm deps removal for %s failed: %s", plugin_name, exc)

    async def run_alembic_upgrade(self, plugin_name: str) -> None:
        """执行插件 Alembic 迁移（公共接口，供 version_manager 等调用）"""
        branch_label = f"plugin_{plugin_name.replace('-', '_')}"
        result = await _run_subprocess_async(
            "alembic", "upgrade", f"{branch_label}@head",
            timeout=120,
            cwd=str(PLUGINS_DIR.parent),
        )
        if result.returncode != 0:
            err_output = result.stderr.strip() or result.stdout.strip() or "unknown error"
            raise PluginInstallError(
                message=f"Alembic upgrade failed for '{plugin_name}': {err_output}",
            )

    def _plugin_has_migrations(self, plugin_name: str) -> bool:
        """检查插件是否有 Alembic 迁移文件"""
        migrations_dir = PLUGINS_DIR / plugin_name / "backend" / "migrations" / "versions"
        if not migrations_dir.is_dir():
            return False
        return any(f.suffix == ".py" and f.name != "__init__.py" for f in migrations_dir.iterdir())

    async def run_alembic_downgrade(self, plugin_name: str) -> None:
        """回退插件 Alembic 迁移（公共接口，供 version_manager 等调用）

        安全检查：
        - 插件必须有迁移文件，否则跳过（防止误回退主项目迁移）
        - 使用插件的 revision ID 前缀匹配，而非 branch_label（插件迁移可能未声明 branch_labels）
        """
        if not self._plugin_has_migrations(plugin_name):
            logger.info("Plugin %s has no migration files, skipping alembic downgrade", plugin_name)
            return

        # 使用插件 revision 前缀直接定位（比 branch_label 更可靠）
        version_prefix = plugin_name.replace("-", "_")

        # 查询 alembic_version 中是否有该插件的版本戳
        check_result = await _run_subprocess_async(
            "alembic", "current",
            timeout=30,
            cwd=str(PLUGINS_DIR.parent),
        )
        current_versions = check_result.stdout if check_result.returncode == 0 else ""

        # 只有当 alembic_version 中存在插件版本戳时才执行 downgrade
        if version_prefix not in current_versions:
            logger.info("Plugin %s has no alembic version stamp, skipping downgrade", plugin_name)
            return

        branch_label = f"plugin_{version_prefix}"
        result = await _run_subprocess_async(
            "alembic", "downgrade", f"{branch_label}@base",
            timeout=120,
            cwd=str(PLUGINS_DIR.parent),
        )
        if result.returncode != 0:
            logger.warning(
                "Alembic downgrade for %s: %s", plugin_name, result.stderr.strip()
            )

    async def _cleanup_plugin_database(self, plugin_name: str) -> None:
        """清理插件数据库资源：DROP 插件表 + 清理 alembic 版本戳

        策略：
        1. 尝试 alembic downgrade（优雅回退，保留数据完整性）
        2. 若 alembic 失败，直接 DROP 所有 px_{plugin_name}_* 表（兜底）
        3. 无论如何，清理 alembic_version 中的插件版本戳
        """
        from sqlalchemy import text

        table_prefix = f"px_{plugin_name.replace('-', '_')}_"

        # Step 1: 尝试 alembic downgrade（仅当插件有迁移文件时）
        alembic_ok = False
        if self._plugin_has_migrations(plugin_name):
            try:
                await self.run_alembic_downgrade(plugin_name)
                alembic_ok = True
            except Exception as exc:
                logger.warning("Plugin %s alembic downgrade failed: %s", plugin_name, exc)
        else:
            logger.info("Plugin %s has no migrations, skipping alembic downgrade", plugin_name)

        # Step 2: 检查是否还有残留表，若有则直接 DROP
        try:
            result = await self._db.execute(
                text(
                    "SELECT tablename FROM pg_tables "
                    "WHERE schemaname = 'public' AND tablename LIKE :prefix "
                    "ORDER BY tablename"
                ),
                {"prefix": f"{table_prefix}%"},
            )
            remaining_tables = [row[0] for row in result.fetchall()]

            if remaining_tables:
                if alembic_ok:
                    logger.warning(
                        "Plugin %s: alembic downgrade succeeded but %d tables remain, dropping directly",
                        plugin_name, len(remaining_tables),
                    )
                for tbl in remaining_tables:
                    try:
                        await self._db.execute(text(f'DROP TABLE IF EXISTS "{tbl}" CASCADE'))
                        logger.info("Plugin %s: dropped table %s", plugin_name, tbl)
                    except Exception as exc:
                        logger.error("Plugin %s: failed to drop table %s: %s", plugin_name, tbl, exc)
                await self._db.flush()
        except Exception as exc:
            logger.error("Plugin %s: failed to query/drop residual tables: %s", plugin_name, exc)

        # Step 3: 清理 alembic_version 中的插件版本戳
        # 插件迁移 revision ID 约定以 {plugin_name_underscored}_ 开头
        version_prefix = plugin_name.replace("-", "_") + "_"
        try:
            result = await self._db.execute(
                text(
                    "DELETE FROM alembic_version WHERE version_num LIKE :prefix"
                ),
                {"prefix": f"{version_prefix}%"},
            )
            deleted_count = result.rowcount
            if deleted_count:
                logger.info(
                    "Plugin %s: cleaned %d alembic_version stamps",
                    plugin_name, deleted_count,
                )
            await self._db.flush()
        except Exception as exc:
            logger.warning("Plugin %s: failed to clean alembic_version: %s", plugin_name, exc)

    async def _rollback_install(
        self, plugin_name: str, completed_steps: list[str]
    ) -> None:
        """安装失败时的完整回滚（零残留）

        回滚策略：
        1. DB 事务回滚 — 撤销所有 ORM 写入（plugins/versions/agent_assignments 等）
        2. Alembic + 插件表 — 复用 _cleanup_plugin_database（downgrade → DROP → 清戳）
        3. 文件清理 — 删除复制到 plugins/ 的目录
        （pip/npm 依赖在 install 阶段不安装，无需回滚）
        """
        logger.info(
            "Rolling back install for %s (steps: %s)", plugin_name, completed_steps
        )

        # Step 1: 回滚 DB 事务
        try:
            await self._db.rollback()
            logger.info("Rollback: DB transaction rolled back for %s", plugin_name)
        except Exception as exc:
            logger.warning("Rollback: DB rollback failed for %s: %s", plugin_name, exc)

        # Step 2: 清理 alembic 迁移 + 插件表 + 版本戳
        if "alembic" in completed_steps:
            try:
                await self._cleanup_plugin_database(plugin_name)
                logger.info("Rollback: cleaned plugin database for %s", plugin_name)
            except Exception as exc:
                logger.warning("Rollback: database cleanup failed for %s: %s", plugin_name, exc)

        # Step 3: 删除复制的插件目录
        if "copy" in completed_steps:
            target_dir = PLUGINS_DIR / plugin_name
            if target_dir.exists():
                shutil.rmtree(target_dir, ignore_errors=True)
                logger.info("Rollback: removed plugin directory %s", target_dir)

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
                scope=ResourceScopeEnum.ADMIN_AND_ALL.value,
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
