"""
插件启动：自动发现 + 恢复

服务启动时：
1. discover_and_register: 扫描 plugins/ 目录，自动注册新插件到 DB（status=installed）
2. restore_enabled_plugins: 恢复已启用插件的扩展点注册 + 依赖补装

设计原则：
- 插件放到 plugins/ 目录下即视为已安装，无需手动上传
- 默认禁用，管理员在面板中启用时才安装依赖（有进度推送）
- 单个插件失败不影响其他插件
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
    自动发现并注册插件（服务启动时调用，在 restore_enabled_plugins 之前）。

    扫描 plugins/ 目录中所有含 plugin.yaml 的子目录：
    - 磁盘有 + DB 无 → 自动注册为 installed（disabled），执行 Alembic 迁移 + AI features
    - 磁盘有 + DB 有 → 同步 manifest 到 DB（热更新 plugin.yaml 字段）
    - DB 有 + 磁盘无 → 标记为 error（文件缺失）

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

    # 查询 DB 中所有已安装插件（未软删除）
    result = await db.execute(
        select(PluginModel).where(PluginModel.is_deleted.is_(False))
    )
    db_plugins = {p.name: p for p in result.scalars().all()}

    discovered = 0
    synced = 0
    missing = 0
    failed = 0

    # ── 磁盘有 → 检查是否需要注册或同步 ──
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
            # ── 新插件：自动注册 ──
            try:
                # 安全扫描（警告级别，不阻止注册，记录到 error_message 供管理员查看）
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

                # 版本记录
                db.add(PluginVersion(
                    plugin_id=plugin.id,
                    version=manifest.version,
                    manifest=manifest.model_dump(),
                    status=PluginVersionStatusEnum.ACTIVE.value,
                    installed_at=utc_now(),
                ))

                # Alembic 迁移（如果有）
                # NOTE: 必须先 commit，因为 run_alembic_upgrade 在子进程中运行，
                # 子进程通过 psycopg2 新连接查询 plugins 表来确定 version_locations。
                # 如果只 flush 未 commit，子进程看不到插件记录，迁移目录不会被加载。
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

                # AI features 注册（如果有）
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

                # on_install 钩子（non-fatal）
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
            # ── 已存在：同步 manifest ──
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
                synced += 1
                logger.info("Discover: synced manifest for %s", plugin_name)

    # ── DB 有但磁盘无 → 标记 error ──
    for plugin_name, plugin in db_plugins.items():
        if plugin_name not in disk_plugins:
            if plugin.status not in (PluginStatusEnum.ERROR.value,):
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


async def restore_enabled_plugins(db: AsyncSession) -> dict:
    """
    服务启动时恢复所有已启用插件的扩展点注册。

    流程：
    1. 查询 status=enabled 的插件
    2. 对每个插件：
       a. 加载 manifest
       b. 通过 ExtensionRegistry 注册扩展点（hooks/events/webhooks）
       c. 记录成功
    3. 单个插件失败 → 标记 error，继续其他插件

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

    from app.plugins._extension_registrar import register_all_extensions
    from app.plugins.lifecycle import PluginLifecycle

    lifecycle = PluginLifecycle(db)

    for plugin in enabled_plugins:
        try:
            manifest = loader.load_manifest(plugin.name)

            # NOTE: manifest sync 已由 discover_and_register() 处理，此处不再重复

            # 确保 Alembic 迁移已执行（防止 DB 重建后插件表丢失）
            migrations_dir = loader.plugins_dir / plugin.name / "backend" / "migrations" / "versions"
            if migrations_dir.is_dir():
                try:
                    await lifecycle.run_alembic_upgrade(plugin.name)
                except Exception as exc:
                    logger.warning(
                        "Restore: alembic upgrade for %s failed: %s",
                        plugin.name, exc,
                    )

            # 确保 Python 依赖已安装（防止克隆/拉取后 venv 缺失）
            if manifest.dependencies.python:
                await lifecycle._install_python_deps(plugin.name, manifest.dependencies.python)

            # 确保前端 npm 依赖已安装（dev 模式，防止克隆/拉取后依赖缺失）
            frontend_ext = manifest.extensions.frontend if manifest.extensions else None
            npm_deps = frontend_ext.npm_dependencies if frontend_ext else []
            if npm_deps:
                await lifecycle._install_npm_deps(plugin.name, npm_deps)

            # 注册所有扩展点（公共函数，与 lifecycle.enable 共用）
            menu_overrides = (plugin.config or {}).get("menu_overrides")
            register_all_extensions(registry, manifest, plugin.name, menu_overrides=menu_overrides)

            # 重置错误计数（恢复成功）
            if plugin.error_count > 0:
                plugin.error_count = 0
                plugin.error_message = None

            restored += 1
            logger.info(
                "Restored plugin: %s (v%s, %d extensions)",
                plugin.name, plugin.version,
                registry.get_registered_count(plugin.name),
            )

        except Exception as exc:
            failed += 1
            plugin.status = PluginStatusEnum.ERROR.value
            plugin.error_message = f"Startup restore failed: {exc}"
            plugin.error_count += 1
            logger.error(
                "Failed to restore plugin %s: %s",
                plugin.name, exc, exc_info=True,
            )

    if restored > 0 or failed > 0:
        await db.flush()

    logger.info(
        "Plugin restore complete: %d restored, %d failed, %d total",
        restored, failed, len(enabled_plugins),
    )
    return {
        "restored": restored,
        "failed": failed,
        "total": len(enabled_plugins),
    }


def _load_plugin_executor(plugin_name: str, skill_type: str):
    """加载插件的 executor 类 — 委托给统一加载器（保留供外部引用）"""
    from app.plugins.module_loader import load_plugin_executor
    return load_plugin_executor(plugin_name, skill_type)


def _load_handler_safe(loader, plugin_name: str, handler_path: str):
    """安全加载插件处理函数 — 委托给统一加载器（保留供外部引用）"""
    from app.plugins.module_loader import load_plugin_handler
    return load_plugin_handler(plugin_name, handler_path)
