"""
插件发现与自动加载

提供两种插件发现机制：
1. 目录扫描：扫描 backend/app/plugins/ 下的子目录，读取 manifest.json
2. 数据库加载：启动时从 DB 加载已启用的插件并注册扩展点
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import LogManager
from app.enums.plugin import PluginStatusEnum

logger = LogManager.get_logger("app")

# 插件目录扫描根路径
PLUGINS_DIR = Path(__file__).parent


def discover_local_plugins() -> list[dict[str, Any]]:
    """
    扫描 plugins/ 目录，发现本地插件

    遍历 backend/app/plugins/ 下的子目录，读取 manifest.json 文件。
    跳过以 _ 开头的目录（如 __pycache__）和 extensions 目录。

    Returns:
        manifest 字典列表，每个包含 entry_point 和元数据
    """
    discovered: list[dict[str, Any]] = []

    if not PLUGINS_DIR.is_dir():
        return discovered

    skip_dirs = {"__pycache__", "extensions", "builtin", "examples"}

    for child in sorted(PLUGINS_DIR.iterdir()):
        if not child.is_dir():
            continue
        if child.name.startswith("_") or child.name in skip_dirs:
            continue

        manifest_path = child / "manifest.json"
        if not manifest_path.exists():
            continue

        try:
            with open(manifest_path, encoding="utf-8") as f:
                manifest = json.load(f)

            if "entry_point" not in manifest or "name" not in manifest:
                logger.warning(
                    "Plugin manifest missing required fields: %s", manifest_path
                )
                continue

            discovered.append(manifest)
            logger.debug("Discovered local plugin: %s", manifest.get("name"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(
                "Failed to read plugin manifest %s: %s", manifest_path, exc
            )

    return discovered


async def load_enabled_plugins(db: AsyncSession) -> dict[str, Any]:
    """
    启动时加载所有已启用的插件

    从数据库读取状态为 enabled 的插件，动态加载并注册扩展点。
    单个插件加载失败不影响其他插件，状态会被标记为 error。

    Args:
        db: 数据库会话

    Returns:
        加载结果统计 {"loaded": int, "failed": int, "errors": list[str]}
    """
    from app.plugins.manager import get_plugin_manager
    from app.repositories.system.plugin_repository import PluginRepository

    manager = get_plugin_manager()
    repo = PluginRepository(db)

    enabled_plugins = await repo.get_enabled_plugins()

    loaded = 0
    failed = 0
    errors: list[str] = []

    for plugin in enabled_plugins:
        try:
            manager.load_and_register(
                plugin.name, plugin.entry_point, db=db
            )

            loaded += 1
            logger.info(
                "Plugin loaded: %s v%s (type=%s)",
                plugin.name, plugin.version, plugin.plugin_type,
            )
        except Exception as exc:
            failed += 1
            error_msg = f"{plugin.name}: {exc}"
            errors.append(error_msg)
            logger.error(
                "Failed to load plugin %s: %s",
                plugin.name, exc, exc_info=True,
            )
            # 标记为 error 状态
            try:
                await repo.update(
                    plugin.id, {"status": PluginStatusEnum.ERROR.value}
                )
            except Exception:
                pass

    result = {"loaded": loaded, "failed": failed, "errors": errors}

    if loaded > 0 or failed > 0:
        logger.info(
            "Plugin loading complete: loaded=%d, failed=%d",
            loaded, failed,
        )

    return result


async def auto_install_local_plugins(db: AsyncSession) -> dict[str, Any]:
    """
    自动安装本地发现的插件（仅安装未注册的）

    扫描 plugins/ 目录，对比 DB 已有记录，自动安装新发现的插件。
    适用于将插件代码直接放入 plugins/ 目录的开发模式。

    Args:
        db: 数据库会话

    Returns:
        安装结果 {"installed": int, "skipped": int, "errors": list[str]}
    """
    from app.plugins.manager import get_plugin_manager
    from app.repositories.system.plugin_repository import PluginRepository

    manager = get_plugin_manager()
    repo = PluginRepository(db)

    manifests = discover_local_plugins()

    installed = 0
    skipped = 0
    errors: list[str] = []

    for manifest in manifests:
        name = manifest["name"]
        entry_point = manifest["entry_point"]

        # 检查是否已安装
        existing = await repo.get_by_name(name)
        if existing:
            # 开发模式：同步磁盘 manifest 到 DB（确保路由/菜单等配置最新）
            if existing.manifest != manifest:
                await repo.update(existing.id, {"manifest": manifest})
                await db.commit()
                logger.info("Synced manifest for plugin: %s", name)
            skipped += 1
            continue

        try:
            is_system = manifest.get("is_system", False)
            await manager.install(db, entry_point, is_system=is_system)
            await db.commit()
            installed += 1
            logger.info("Auto-installed local plugin: %s", name)
        except Exception as exc:
            await db.rollback()
            errors.append(f"{name}: {exc}")
            logger.error(
                "Failed to auto-install plugin %s: %s",
                name, exc, exc_info=True,
            )

    if installed > 0 or errors:
        logger.info(
            "Local plugin scan: installed=%d, skipped=%d, errors=%d",
            installed, skipped, len(errors),
        )

    return {"installed": installed, "skipped": skipped, "errors": errors}


# 内置插件清单：(entry_point, is_system)
# OpenAI Compatible Adapter 已集成到核心系统（main.py），不再作为插件注册
BUILTIN_PLUGINS: list[tuple[str, bool]] = []


async def register_builtin_plugins(db: AsyncSession) -> dict[str, Any]:
    """
    注册内置插件（仅安装未注册的，自动启用）

    内置插件标记为 is_system=True，安装后自动设为 enabled 状态。

    Args:
        db: 数据库会话

    Returns:
        注册结果 {"registered": int, "skipped": int, "errors": list[str]}
    """
    from app.plugins.manager import get_plugin_manager
    from app.repositories.system.plugin_repository import PluginRepository

    manager = get_plugin_manager()
    repo = PluginRepository(db)

    registered = 0
    skipped = 0
    errors: list[str] = []

    for entry_point, is_system in BUILTIN_PLUGINS:
        try:
            plugin_cls = manager.load_plugin_class(entry_point)
            instance = plugin_cls()
            plugin_name = instance.name

            existing = await repo.get_by_name(plugin_name)
            if existing:
                skipped += 1
                continue

            plugin = await manager.install(db, entry_point, is_system=is_system)
            # 自动启用内置插件
            await manager.enable_platform(db, plugin.id)
            await db.commit()
            registered += 1
            logger.info("Builtin plugin registered: %s", plugin_name)
        except Exception as exc:
            await db.rollback()
            errors.append(f"{entry_point}: {exc}")
            logger.error(
                "Failed to register builtin plugin %s: %s",
                entry_point, exc, exc_info=True,
            )

    if registered > 0 or errors:
        logger.info(
            "Builtin plugin registration: registered=%d, skipped=%d, errors=%d",
            registered, skipped, len(errors),
        )

    return {"registered": registered, "skipped": skipped, "errors": errors}


__all__ = [
    "discover_local_plugins",
    "load_enabled_plugins",
    "auto_install_local_plugins",
    "register_builtin_plugins",
]
