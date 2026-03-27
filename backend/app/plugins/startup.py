"""
Plugin startup: auto-discovery + restoration. / 插件启动：自动发现 + 恢复。

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
from app.core.response import resolve_public_error_message
from app.plugins.dependencies import (
    build_plugin_dependency_states,
    build_python_dependency_states,
    normalize_plugin_dependencies,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

_STALE_PLUGIN_ERROR_MARKERS = (
    "Manifest drift detected on disk.",
    "Disk plugin version drift detected:",
    "Plugin files missing from disk",
    "admin_and_assigned",
    "admin_and_all",
)


def _infer_reconciled_status(plugin) -> str:
    from app.enums.plugin import PluginStatusEnum

    return (
        PluginStatusEnum.DISABLED.value
        if getattr(plugin, "enabled_at", None)
        else PluginStatusEnum.INSTALLED.value
    )


def _reconcile_stale_plugin_error(plugin) -> bool:
    from app.enums.plugin import PluginStatusEnum

    message = str(getattr(plugin, "error_message", "") or "")
    if not message:
        return False

    if not any(marker in message for marker in _STALE_PLUGIN_ERROR_MARKERS):
        return False

    status = getattr(plugin, "status", None)
    if status == PluginStatusEnum.ERROR.value:
        plugin.status = _infer_reconciled_status(plugin)

    plugin.error_message = None
    plugin.error_count = 0
    return True


async def _collect_startup_dependency_errors(db: AsyncSession, manifest) -> list[str]:
    """Collect runtime dependency errors during startup restore. / 启动恢复阶段收集依赖错误。"""
    from sqlalchemy import select

    from app.models.system.plugin import Plugin as PluginModel

    errors: list[str] = []

    plugin_requirements = normalize_plugin_dependencies(manifest)
    if plugin_requirements:
        dependency_names = sorted({item.plugin for item in plugin_requirements})
        result = await db.execute(
            select(PluginModel.name, PluginModel.version, PluginModel.status).where(
                PluginModel.name.in_(dependency_names),
                PluginModel.is_deleted.is_(False),
            )
        )
        plugin_rows = {
            row[0]: {
                "name": row[0],
                "status": row[2],
                "version": row[1],
            }
            for row in result.all()
        }
        for state in build_plugin_dependency_states(
            plugin_requirements,
            plugin_rows,
            require_enabled=True,
        ):
            if state.state != "ready":
                errors.append(state.message)

    for state in build_python_dependency_states(
        getattr(manifest.dependencies, "python", []) or []
    ):
        if not state["satisfied"]:
            errors.append(str(state["message"]))

    return errors


async def discover_and_register(db: AsyncSession) -> dict:
    """
    Auto-discover and register plugins (called at service startup, before restore_enabled_plugins).
    / 自动发现并注册插件。

    Scans all subdirectories containing plugin.yaml in plugins/ directory:
    - On disk + not in DB → auto-register as installed (disabled), run Alembic migration + AI features
    - On disk + in DB + same version but manifest drift → mark sync_required, do not hot-sync DB
    - On disk + in DB + version drift → mark upgrade_required, do not hot-upgrade DB/runtime
    - In DB + not on disk → mark as error (files missing)
    / 磁盘有+DB无→注册；磁盘有+DB有但同版本漂移→提示显式 sync；版本漂移→提示正式 upgrade；DB有磁盘无→标错

    Returns:
        {"discovered": N, "sync_required": N, "upgrade_required": N, "missing": N, "failed": N}
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
    from app.plugins.frontend_contract import validate_runtime_frontend_contract
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
    sync_required = 0
    upgrade_required = 0
    missing = 0
    failed = 0
    reconciled = 0

    # ── On disk → check if registration or sync needed / 磁盘有 → 检查注册或同步 ──
    for plugin_name in sorted(disk_plugins):
        try:
            manifest = loader.load_manifest(plugin_name)
            validate_runtime_frontend_contract(loader.plugins_dir / plugin_name, manifest)
        except Exception as exc:
            logger.warning(
                "Discover: skipping {} (invalid manifest): {}", plugin_name, exc,
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
                            "Discover: plugin {} has {} security warning(s): {}",
                            plugin_name, len(scan_result.warnings),
                            "; ".join(scan_result.warnings[:3]),
                        )
                except Exception as exc:
                    logger.warning("Discover: security scan failed for {}: {}", plugin_name, exc)

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
                        logger.info("Discover: ran alembic for {}", plugin_name)
                    except Exception as exc:
                        logger.warning("Discover: alembic failed for {}: {}", plugin_name, exc)

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
                    logger.warning("Discover: on_install failed for {}: {}", plugin_name, exc)

                await db.flush()
                discovered += 1
                logger.info(
                    "Discover: auto-registered plugin {} v{} (disabled)",
                    plugin_name, manifest.version,
                )

            except Exception as exc:
                failed += 1
                logger.error(
                    "Discover: failed to register {}: {}", plugin_name, exc, exc_info=True,
                )
        else:
            # ── Already exists: detect drift only, do not hot-sync / 已存在：仅检测漂移，不热同步 ──
            existing_plugin = db_plugins[plugin_name]
            disk_manifest = manifest.model_dump()
            if existing_plugin.manifest != disk_manifest:
                if manifest.version != existing_plugin.version:
                    upgrade_required += 1
                    existing_plugin.error_message = (
                        "Disk plugin version drift detected: "
                        f"DB={existing_plugin.version}, disk={manifest.version}. "
                        "Use formal upgrade instead of startup discover."
                    )
                    logger.warning(
                        "Discover: plugin {} version drift detected (db={} disk={}), formal upgrade required",
                        plugin_name,
                        existing_plugin.version,
                        manifest.version,
                    )
                else:
                    sync_required += 1
                    existing_plugin.error_message = (
                        "Manifest drift detected on disk. "
                        "Run explicit sync-manifest to apply non-version changes."
                    )
                    logger.info(
                        "Discover: plugin {} manifest drift detected, explicit sync required",
                        plugin_name,
                    )
            elif _reconcile_stale_plugin_error(existing_plugin):
                reconciled += 1
                logger.info(
                    "Discover: reconciled stale plugin error state for {} -> {}",
                    plugin_name,
                    existing_plugin.status,
                )

    # ── In DB but not on disk → mark error / DB 有但磁盘无 → 标记 error ──
    for plugin_name, plugin in db_plugins.items():
        if plugin_name not in disk_plugins and plugin.status not in (PluginStatusEnum.ERROR.value,):
            plugin.status = PluginStatusEnum.ERROR.value
            plugin.error_message = "Plugin files missing from disk"
            plugin.error_count += 1
            missing += 1
            try:
                from app.plugins.lifecycle import PluginLifecycle

                await PluginLifecycle(db)._set_plugin_permissions_enabled(plugin_name, False)
            except Exception as perm_exc:
                logger.warning(
                    "Discover: failed to disable permissions for missing plugin {}: {}",
                    plugin_name,
                    perm_exc,
                )
            logger.warning("Discover: plugin {} missing from disk, marked error", plugin_name)

    if discovered > 0 or sync_required > 0 or upgrade_required > 0 or missing > 0 or reconciled > 0:
        await db.flush()

    logger.info(
        "Plugin discover complete: discovered={}, sync_required={}, upgrade_required={}, missing={}, reconciled={}, failed={}",
        discovered, sync_required, upgrade_required, missing, reconciled, failed,
    )
    return {
        "discovered": discovered,
        "sync_required": sync_required,
        "upgrade_required": upgrade_required,
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
    status_changed = False

    from app.plugins._extension_registrar import (
        get_failed_extensions,
        register_all_extensions,
    )
    from app.plugins.frontend_contract import validate_runtime_frontend_contract
    from app.plugins.lifecycle import PluginLifecycle

    lifecycle = PluginLifecycle(db) if run_heavy or mutate_db_status else None
    mode_label = "heavy" if run_heavy else "register-only"

    async def _fail_close_plugin_runtime(plugin_name: str) -> None:
        try:
            registry.unregister_all(plugin_name)
        except Exception as cleanup_exc:
            logger.warning(
                "Restore({}) failed to unregister runtime extensions for {}: {}",
                mode_label,
                plugin_name,
                cleanup_exc,
            )
        if lifecycle is None:
            return
        try:
            await lifecycle._set_plugin_permissions_enabled(plugin_name, False)
        except Exception as perm_exc:
            logger.warning(
                "Restore({}) failed to disable permissions for {}: {}",
                mode_label,
                plugin_name,
                perm_exc,
            )

    for plugin in enabled_plugins:
        try:
            from app.plugins.license import get_plugin_runtime_license_status

            license_status = await get_plugin_runtime_license_status(
                plugin.id,
                plugin.pricing_type,
                db,
            )
            if not license_status.get("runtime_allowed", False):
                if mutate_db_status:
                    plugin.status = PluginStatusEnum.DISABLED.value
                    plugin.error_message = (
                        "Startup restore skipped: "
                        + (license_status.get("message") or "license inactive")
                    )
                    plugin.error_count = 0
                    status_changed = True
                    await _fail_close_plugin_runtime(plugin.name)
                logger.warning(
                    "Restore({}) skipped plugin {} due to inactive license: {}",
                    mode_label,
                    plugin.name,
                    license_status.get("status"),
                )
                continue

            manifest = loader.load_manifest(plugin.name)
            validate_runtime_frontend_contract(loader.plugins_dir / plugin.name, manifest)
            if manifest.version != plugin.version:
                raise RuntimeError(
                    "Disk plugin version drift detected: "
                    f"DB={plugin.version}, disk={manifest.version}. "
                    "Formal upgrade is required before startup restore."
                )
            disk_manifest = manifest.model_dump()
            if isinstance(plugin.manifest, dict) and plugin.manifest != disk_manifest:
                raise RuntimeError(
                    "Manifest drift detected on disk. "
                    "Run explicit sync-manifest before startup restore."
                )

            # NOTE: manifest sync already handled by discover_and_register(), not repeated here
            # / 启动阶段不做 manifest 同步，显式 sync-manifest 才允许写回 DB

            dependency_errors = await _collect_startup_dependency_errors(db, manifest)
            if dependency_errors:
                raise RuntimeError(
                    "Dependency validation failed: " + "; ".join(dependency_errors)
                )

            if run_heavy and getattr(manifest.extensions, "tasks", None):
                # Database startup already runs `alembic upgrade heads` with plugin
                # version_locations injected, so plugin tables are ensured before
                # restore_enabled_plugins() executes. Avoid spawning a second
                # per-plugin Alembic subprocess here during startup restore.
                # / 数据库启动阶段已经带插件 version_locations 执行全量 `upgrade heads`，
                # / 进入 restore_enabled_plugins() 前插件表应已完成迁移；此处不再重复
                # / 为每个插件启动一次 Alembic 子进程，避免开发态/Windows 下的冗余抖动。
                # Restore plugin task definitions so Celery Beat can still see plugin tasks after startup recovery.
                # / 恢复插件任务定义记录，确保启动恢复后 Celery Beat 仍能看到任务。
                await lifecycle._sync_plugin_task_definitions(
                    plugin.name,
                    manifest.extensions.tasks,
                )

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

            if lifecycle is not None:
                await lifecycle._restore_plugin_permissions(
                    plugin.name,
                    auto_grant_plans=True,
                )

            # Only restore owner worker is allowed to write DB status, avoid multi-worker concurrent jitter
            # / 仅 owner worker 写库
            if mutate_db_status and plugin.error_count > 0:
                plugin.error_count = 0
                plugin.error_message = None
                status_changed = True

            restored += 1
            logger.info(
                "Restored plugin({}): {} (v{}, {} extensions)",
                mode_label,
                plugin.name,
                plugin.version,
                registry.get_registered_count(plugin.name),
            )

        except Exception as exc:
            failed += 1
            await _fail_close_plugin_runtime(plugin.name)
            if mutate_db_status:
                plugin.status = PluginStatusEnum.ERROR.value
                plugin.error_message = resolve_public_error_message(
                    exc,
                    fallback_message="Startup restore failed",
                )
                plugin.error_count += 1
                status_changed = True
            logger.error(
                "Failed to restore plugin({}) {}: {}",
                mode_label,
                plugin.name,
                exc,
                exc_info=True,
            )

    if mutate_db_status and status_changed:
        await db.flush()

    logger.info(
        "Plugin restore({}) complete: {} restored, {} failed, {} total",
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
                "Plugin system: {} plugin(s) in ERROR state and need manual repair: {}. "
                "Go to Admin > Plugins and click the Repair button.",
                len(error_plugins), ", ".join(names),
            )
            for row in error_plugins:
                logger.warning("  ↳ [{}] {}", row[0], (row[1] or "unknown error")[:200])

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
