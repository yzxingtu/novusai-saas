"""
插件开发模式热重载

开发模式下监听 plugins/ 目录的 .py 文件变更，自动重载对应插件。
生产模式不启用。

依赖：watchfiles（uvicorn[standard] 已包含）

使用方式：
    from app.plugins.dev_watcher import start_plugin_watcher
    # 在 app startup 中调用
    await start_plugin_watcher(app)
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

from app.core.logging import LogManager

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = LogManager.get_logger("app")

# 插件目录（相对于 backend/app/plugins/）
_PLUGINS_DIR = Path(__file__).resolve().parent


async def start_plugin_watcher(app: FastAPI) -> None:
    """
    启动插件文件监听（仅开发模式）

    检测 plugins/ 目录下 .py 文件的创建/修改/删除，
    触发对应插件的重载（disable → re-import → enable）。

    Args:
        app: FastAPI 应用实例
    """
    from app.core.config import settings

    if not getattr(settings, "DEBUG", False):
        logger.debug("Plugin dev watcher: skipped (not in DEBUG mode)")
        return

    try:
        from watchfiles import awatch, Change
    except ImportError:
        logger.warning(
            "Plugin dev watcher: watchfiles not installed. "
            "Install with: pip install watchfiles"
        )
        return

    watch_dir = _PLUGINS_DIR
    logger.info("Plugin dev watcher: watching %s for .py changes", watch_dir)

    async def _watch_loop() -> None:
        try:
            async for changes in awatch(watch_dir, recursive=True):
                plugin_names: set[str] = set()
                for change_type, path_str in changes:
                    path = Path(path_str)
                    # 只关注 .py 文件
                    if path.suffix != ".py":
                        continue
                    # 跳过 __pycache__
                    if "__pycache__" in path.parts:
                        continue
                    # 跳过框架核心文件（manager.py, base.py 等）
                    if path.parent == _PLUGINS_DIR:
                        continue

                    # 推导插件名称：plugins/{name}/... 或 plugins/builtin/{name}/...
                    try:
                        relative = path.relative_to(_PLUGINS_DIR)
                        parts = relative.parts
                        if len(parts) >= 2:
                            # 跳过 examples/, extensions/ 等非插件目录
                            if parts[0] in ("examples", "extensions", "__pycache__"):
                                continue
                            if parts[0] == "builtin" and len(parts) >= 3:
                                plugin_names.add(parts[1])
                            else:
                                plugin_names.add(parts[0])
                    except ValueError:
                        continue

                for name in plugin_names:
                    logger.info(
                        "Plugin dev watcher: detected change in '%s', reloading...",
                        name,
                    )
                    await _try_reload_plugin(name)

        except asyncio.CancelledError:
            logger.info("Plugin dev watcher: stopped")
        except Exception:
            logger.error("Plugin dev watcher: unexpected error", exc_info=True)

    # 作为后台任务运行
    task = asyncio.create_task(_watch_loop())

    # 在 app shutdown 时取消
    @app.on_event("shutdown")
    async def _stop_watcher() -> None:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


async def _try_reload_plugin(plugin_name: str) -> None:
    """
    尝试重载插件（降级为日志警告，不崩溃）

    流程：
    1. 清除 Python 模块缓存中的插件模块
    2. 从 PluginManager 实例缓存中移除
    3. 重新加载（如果插件已在数据库中启用）

    Args:
        plugin_name: 插件名称
    """
    import sys

    try:
        from app.plugins.manager import PluginManager

        manager = PluginManager.get_instance()

        # 清除已缓存的模块
        modules_to_remove = [
            key for key in sys.modules
            if f"plugins.{plugin_name}" in key
            or f"plugins.builtin.{plugin_name}" in key
        ]
        for mod_key in modules_to_remove:
            del sys.modules[mod_key]

        # 从 manager 实例缓存中移除
        if plugin_name in manager._instances:
            instance = manager._instances.pop(plugin_name)
            logger.info(
                "Plugin dev watcher: cleared cached instance for '%s'",
                plugin_name,
            )

        logger.info(
            "Plugin dev watcher: '%s' module cache cleared. "
            "Plugin will reload on next enable/access.",
            plugin_name,
        )

    except Exception:
        logger.warning(
            "Plugin dev watcher: failed to reload '%s'",
            plugin_name,
            exc_info=True,
        )


__all__ = ["start_plugin_watcher"]
