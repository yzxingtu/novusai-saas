"""
Plugin startup: auto-discovery + restoration.
/ 插件启动：自动发现 + 恢复

At service startup:
1. discover_and_register: scan plugins/ directory, auto-register new plugins to DB (status=installed)
2. restore_enabled_plugins: restore extension point registration + dependency installation for enabled plugins
/ 服务启动时：1. 扫描注册新插件 2. 恢复已启用插件

Design principles:
- Placing plugin in plugins/ directory is considered installed, no manual upload needed
- Disabled by default, admin enables in panel which triggers dependency installation (with progress push)
- Single plugin failure does not affect other plugins
/ 设计原则：目录即安装、默认禁用、单插件失败不影响全局
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.base_model import utc_now
from app.core.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


async def discover_and_register(db: AsyncSession) -> dict:
    """
    Auto-discover and register plugins (called at service startup, before restore_enabled_plugins).
    / 自动发现并注册插件。

    Scans all subdirectories containing plugin.yaml in plugins/ directory:
    - On disk + not in DB → auto-register as installed (disabled), run Alembic migration + AI features
    - On disk + in DB → sync manifest to DB (hot-update plugin.yaml fields)
    - In DB + not on disk → mark as error (files missing)
    / 磁盘有+DB无→注册，磁盘有+DB有→同步，DB有+磁盘无→标错

    Returns:
        {"discovered": N, "synced": N, "missing": N, "failed": N}
    """
    from sqlalchemy import select

    from app.enums.plugin import (
        PluginInstallSourceEnum,
        PluginStatusEnum,
        PluginTierEnum,
        PluginVersionStatusEnum,
    )
    from app.models.system.plugin import Plugin as PluginModel
    from app.models.system.plugin_version import PluginVersion
    from app.plugins.loader import PLUGINS_DIR, PluginLoader
    from app.plugins.preview import resolve_i18n

    loader = PluginLoader()
    disk_plugins = set(loader.discover_plugins())

    # Query all installed plugins in DB (not soft-deleted) / 查询 DB 中所有已安装插件
    result = await db.execute(
        select(PluginModel).where(PluginModel.is_deleted.is_(False))
    )
    db_plugins = {p.name: p for p in result.scalars().all()}

    discovered = 0
    synced = 0
    missing = 0
    failed = 0

    # ── On disk → check if registration or sync needed / 磁盘有 → 检查注册或同步 ──
    for plugin_name in sorted(disk_plugins):
        try:
            manifest = loader.load_manifest(plugin_name)
        except Exception as exc:
            logger.warning(
                "Discover: skipping %s (invalid manifest): %s", plugin_name, exc,
            )
            failed += 1
            continue

        if plugin_name not in db_plugins:
            # ── New plugin: auto-register / 新插件：自动注册 ──
            try:
                # Security scan (warning level, doesn't block registration, recorded to error_message for admin review)
                # / 安全扫描（警告级别）
                security_warnings: list[str] = []
                try:
                    from app.plugins.security_scan import scan_plugin_directory
                    scan_result = scan_plugin_directory(PLUGINS_DIR / plugin_name)
                    if scan_result.has_warnings:
                        security_warnings = scan_result.warnings[:10]
                        logger.warning(
                            "Discover: plugin %s has %d security warning(s): %s",
                            plugin_name, len(scan_result.warnings),
                            "; ".join(scan_result.warnings[:3]),
                        )
                except Exception as exc:
                    logger.warning("Discover: security scan failed for %s: %s", plugin_name, exc)

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
                    config={},
                    ai_requirements=manifest.ai_requirements.model_dump() if manifest.ai_requirements else None,
                    pricing_type=manifest.pricing.type,
                    pricing_info=manifest.pricing.model_dump() if manifest.pricing.type != "free" else None,
                    error_count=len(security_warnings),
                    error_message=f"Security warnings: {'; '.join(security_warnings)}" if security_warnings else None,
                    installed_packages=manifest.dependencies.python or [],
                    granted_capabilities=manifest.capabilities,
                    installed_at=utc_now(),
                )
                db.add(plugin)
                await db.flush()

                # Version record / 版本记录
                db.add(PluginVersion(
                    plugin_id=plugin.id,
                    version=manifest.version,
                    manifest=manifest.model_dump(),
                    status=PluginVersionStatusEnum.ACTIVE.value,
                    installed_at=utc_now(),
                ))

                # Alembic migration (if any)
                # NOTE: Must commit first because run_alembic_upgrade runs in subprocess,
                # subprocess queries plugins table via psycopg2 new connection to determine version_locations.
                # If only flushed without commit, subprocess cannot see plugin record, migration directory won't be loaded.
                # / Alembic 迁移（必须先 commit）
                migrations_dir = PLUGINS_DIR / plugin_name / "backend" / "migrations" / "versions"
                if migrations_dir.is_dir():
                    try:
                        await db.commit()
                        from app.plugins.lifecycle import PluginLifecycle
                        lifecycle = PluginLifecycle(db)
                        await lifecycle.run_alembic_upgrade(plugin_name)
                        logger.info("Discover: ran alembic for %s", plugin_name)
                    except Exception as exc:
                        logger.warning("Discover: alembic failed for %s: %s", plugin_name, exc)

                # AI features registration (if any) / AI features 注册
                if manifest.ai_requirements and manifest.ai_requirements.features:
                    from app.models.system.agent_assignment import SystemAgentAssignment
                    for feature in manifest.ai_requirements.features:
                        feature_code = f"plugin.{plugin_name}.{feature.feature_code}"
                        existing = await db.execute(
                            select(SystemAgentAssignment.id).where(
                                SystemAgentAssignment.feature_code == feature_code,
                                SystemAgentAssignment.tenant_id.is_(None),
                                SystemAgentAssignment.is_deleted.is_(False),
                            )
                        )
                        if not existing.scalar_one_or_none():
                            db.add(SystemAgentAssignment(
                                feature_code=feature_code,
                                feature_name=feature.display_name.get(
                                    "zh-CN", feature.display_name.get("en", feature.feature_code),
                                ),
                                description=feature.description.get(
                                    "zh-CN", feature.description.get("en", ""),
                                ),
                                agent_id=None,
                                tenant_id=None,
                                is_active=True,
                            ))

                # on_install hook (non-fatal) / on_install 钩子
                try:
                    from app.plugins.context_factory import create_plugin_context
                    plugin_cls = loader.load_plugin_class(plugin_name)
                    ctx = create_plugin_context(
                        plugin_name=plugin_name,
                        manifest=manifest,
                        db=db,
                        granted_capabilities=manifest.capabilities,
                    )
                    await plugin_cls().on_install(ctx)
                except Exception as exc:
                    logger.warning("Discover: on_install failed for %s: %s", plugin_name, exc)

                await db.flush()
                discovered += 1
                logger.info(
                    "Discover: auto-registered plugin %s v%s (disabled)",
                    plugin_name, manifest.version,
                )

            except Exception as exc:
                failed += 1
                logger.error(
                    "Discover: failed to register %s: %s", plugin_name, exc, exc_info=True,
                )
        else:
            # ── Already exists: sync manifest / 已存在：同步 manifest ──
            existing_plugin = db_plugins[plugin_name]
            disk_manifest = manifest.model_dump()
            if existing_plugin.manifest != disk_manifest:
                existing_plugin.manifest = disk_manifest
                existing_plugin.display_name = resolve_i18n(manifest.display_name)
                existing_plugin.description = resolve_i18n(manifest.description) if manifest.description else existing_plugin.description
                existing_plugin.version = manifest.version
                existing_plugin.icon = manifest.icon or existing_plugin.icon
                existing_plugin.icon_color = manifest.icon_color or existing_plugin.icon_color
                existing_plugin.tags = manifest.tags
                existing_plugin.scope = manifest.scope
                existing_plugin.installed_packages = manifest.dependencies.python or []
                existing_plugin.ai_requirements = manifest.ai_requirements.model_dump() if manifest.ai_requirements else existing_plugin.ai_requirements
                existing_plugin.granted_capabilities = manifest.capabilities or existing_plugin.granted_capabilities
                synced += 1
                logger.info("Discover: synced manifest for %s", plugin_name)

    # ── In DB but not on disk → mark error / DB 有但磁盘无 → 标记 error ──
    for plugin_name, plugin in db_plugins.items():
        if plugin_name not in disk_plugins and plugin.status not in (PluginStatusEnum.ERROR.value,):
            plugin.status = PluginStatusEnum.ERROR.value
            plugin.error_message = "Plugin files missing from disk"
            plugin.error_count += 1
            missing += 1
            logger.warning("Discover: plugin %s missing from disk, marked error", plugin_name)

    if discovered > 0 or synced > 0 or missing > 0:
        await db.flush()

    logger.info(
        "Plugin discover complete: discovered=%d, synced=%d, missing=%d, failed=%d",
        discovered, synced, missing, failed,
    )
    return {
        "discovered": discovered,
        "synced": synced,
        "missing": missing,
        "failed": failed,
    }


async def restore_enabled_plugins(
    db: AsyncSession,
    *,
    run_heavy: bool = True,
    mutate_db_status: bool = True,
) -> dict:
    """
    Restore extension point registration for all enabled plugins at service startup.
    / 服务启动时恢复所有已启用插件的扩展点注册。

    Flow:
    1. Query plugins with status=enabled
    2. For each plugin: a. Load manifest b. Register extensions via ExtensionRegistry c. Record success
    3. Single plugin failure → record failure, write back ERROR status based on mutate_db_status
    / 流程：查询启用插件、注册扩展点、失败标记 ERROR

    Returns:
        {"restored": N, "failed": N, "total": N}
    """
    from sqlalchemy import select

    from app.enums.plugin import PluginStatusEnum
    from app.models.system.plugin import Plugin
    from app.plugins.loader import PluginLoader
    from app.plugins.registry import ExtensionRegistry

    result = await db.execute(
        select(Plugin).where(
            Plugin.status == PluginStatusEnum.ENABLED.value,
            Plugin.is_deleted.is_(False),
        )
    )
    enabled_plugins = list(result.scalars().all())

    if not enabled_plugins:
        logger.info("No enabled plugins to restore")
        return {"restored": 0, "failed": 0, "total": 0}

    loader = PluginLoader()
    registry = ExtensionRegistry.get_instance()
    restored = 0
    failed = 0

    from app.plugins._extension_registrar import (
        get_failed_extensions,
        register_all_extensions,
    )
    from app.plugins.lifecycle import PluginLifecycle

    lifecycle = PluginLifecycle(db) if run_heavy else None
    mode_label = "heavy" if run_heavy else "register-only"

    for plugin in enabled_plugins:
        try:
            manifest = loader.load_manifest(plugin.name)

            # NOTE: manifest sync already handled by discover_and_register(), not repeated here
            # / manifest sync 已由 discover_and_register() 处理

            if run_heavy:
                # Ensure Alembic migration has been executed (prevent plugin tables lost after DB rebuild)
                # / 确保 Alembic 迁移已执行
                migrations_dir = loader.plugins_dir / plugin.name / "backend" / "migrations" / "versions"
                if migrations_dir.is_dir():
                    try:
                        await lifecycle.run_alembic_upgrade(plugin.name)
                    except Exception as exc:
                        logger.warning(
                            "Restore(%s): alembic upgrade for %s failed: %s",
                            mode_label,
                            plugin.name,
                            exc,
                        )

                # Ensure Python dependencies installed (prevent missing venv after clone/pull)
                # / 确保 Python 依赖已安装
                if manifest.dependencies.python:
                    await lifecycle._install_python_deps(plugin.name, manifest.dependencies.python)

                # Ensure frontend npm dependencies installed (dev mode, prevent missing deps after clone/pull)
                # / 确保前端 npm 依赖已安装
                frontend_ext = manifest.extensions.frontend if manifest.extensions else None
                npm_deps = frontend_ext.npm_dependencies if frontend_ext else []
                if npm_deps:
                    await lifecycle._install_npm_deps(plugin.name, npm_deps)

            # Register all extension points (shared function, used by lifecycle.enable)
            # / 注册所有扩展点
            menu_overrides = (plugin.config or {}).get("menu_overrides")
            register_all_extensions(registry, manifest, plugin.name, menu_overrides=menu_overrides)

            # fail-close: if critical extension load fails during restore, rollback registration and mark ERROR
            # / fail-close：恢复阶段关键扩展加载失败时回滚
            failed_exts = get_failed_extensions(plugin.name)
            if failed_exts:
                registry.unregister_all(plugin.name)
                failed_summary = "; ".join(
                    f"{item['type']}:{item['entry_point']}" for item in failed_exts[:5]
                )
                raise RuntimeError(
                    f"Extension load failed during startup restore: {failed_summary}"
                )

            # Only restore owner worker is allowed to write DB status, avoid multi-worker concurrent jitter
            # / 仅 owner worker 写库
            if mutate_db_status and plugin.error_count > 0:
                plugin.error_count = 0
                plugin.error_message = None

            restored += 1
            logger.info(
                "Restored plugin(%s): %s (v%s, %d extensions)",
                mode_label,
                plugin.name, plugin.version,
                registry.get_registered_count(plugin.name),
            )

        except Exception as exc:
            failed += 1
            if mutate_db_status:
                plugin.status = PluginStatusEnum.ERROR.value
                plugin.error_message = f"Startup restore failed: {exc}"
                plugin.error_count += 1
            logger.error(
                "Failed to restore plugin(%s) %s: %s",
                mode_label,
                plugin.name,
                exc,
                exc_info=True,
            )

    if mutate_db_status and (restored > 0 or failed > 0):
        await db.flush()

    logger.info(
        "Plugin restore(%s) complete: %d restored, %d failed, %d total",
        mode_label,
        restored,
        failed,
        len(enabled_plugins),
    )

    # Only owner worker summarizes ERROR status, avoid multi-worker duplicate alerts
    # / 仅 owner worker 汇总 ERROR
    if mutate_db_status:
        error_result = await db.execute(
            select(Plugin.name, Plugin.error_message).where(
                Plugin.status == PluginStatusEnum.ERROR.value,
                Plugin.is_deleted.is_(False),
            )
        )
        error_plugins = error_result.all()
        if error_plugins:
            names = [row[0] for row in error_plugins]
            logger.warning(
                "Plugin system: %d plugin(s) in ERROR state and need manual repair: %s. "
                "Go to Admin > Plugins and click the Repair button.",
                len(error_plugins), ", ".join(names),
            )
            for row in error_plugins:
                logger.warning("  ↳ [%s] %s", row[0], (row[1] or "unknown error")[:200])

    return {
        "restored": restored,
        "failed": failed,
        "total": len(enabled_plugins),
    }


def _load_plugin_executor(plugin_name: str, skill_type: str):
    """Load plugin executor class — delegate to unified loader (preserved for external reference)
    / 加载插件的 executor 类"""
    from app.plugins.module_loader import load_plugin_executor
    return load_plugin_executor(plugin_name, skill_type)


def _load_handler_safe(loader, plugin_name: str, handler_path: str):
    """Safely load plugin handler function — delegate to unified loader (preserved for external reference)
    / 安全加载插件处理函数"""
    from app.plugins.module_loader import load_plugin_handler
    return load_plugin_handler(plugin_name, handler_path)
