"""
Unified plugin module loader.
/ 插件模块统一加载器

All dynamic imports of plugin modules go through this entry point,
avoiding scattered importlib.util code and ensuring consistent module_name
naming and correct sys.modules cache sharing.
/ 所有插件模块的动态导入统一走此入口。

module_name convention: plugins.{plugin_name}.backend.{dotted_path}
Physical path convention:
backend/plugins/{plugin_name}/backend/{path_parts...}.py or package __init__.py
/ module_name 约定 / 物理路径约定
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


def _get_plugins_dir() -> Path:
    """Lazily get PLUGINS_DIR to avoid circular imports / 延迟获取 PLUGINS_DIR，避免循环导入"""
    from app.plugins.loader import PLUGINS_DIR

    return PLUGINS_DIR


def load_plugin_module(plugin_name: str, dotted_path: str) -> Any | None:
    """
    Load a plugin submodule.
    / 加载插件子模块。

    Args:
        plugin_name: Plugin name (e.g. "my-plugin") / 插件名称
        dotted_path: Dot-separated path under backend/ (e.g. "api.handlers", "skills.my_resolver")
                     / 模块在 backend/ 下的点分路径

    Returns:
        Loaded module object, or None on failure / 已加载的模块对象，失败返回 None
    """
    plugins_dir = _get_plugins_dir()

    parts = dotted_path.split(".")
    module_file = (
        plugins_dir / plugin_name / "backend" / Path(*parts).with_suffix(".py")
    )

    # 中文: 仅解析精确模块文件或显式包模块路径，不扫描目录寻找替代模块。
    # EN: Resolve only exact module files or explicit package modules; do not scan for substitutes.
    if not module_file.is_file():
        module_dir = (
            plugins_dir / plugin_name / "backend" / Path(*parts) / "__init__.py"
        )
        if module_dir.is_file():
            module_file = module_dir
        else:
            logger.debug("Plugin module file not found: {}", module_file)
            return None

    module_name = f"plugins.{plugin_name}.backend.{dotted_path}"
    try:
        if module_name in sys.modules:
            return sys.modules[module_name]

        spec = importlib.util.spec_from_file_location(module_name, module_file)
        if spec is None or spec.loader is None:
            logger.warning("Cannot create module spec for {}", module_name)
            return None

        mod = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = mod
        spec.loader.exec_module(mod)
        return mod
    except Exception as exc:
        # Clean up failed module entry / 清理失败的模块条目
        sys.modules.pop(module_name, None)
        logger.warning(
            "Failed to load plugin module {}: {}",
            module_name,
            exc,
            exc_info=True,
        )
        return None


def load_plugin_handler(plugin_name: str, handler_dotpath: str) -> Any | None:
    """
    Load a plugin handler function/class.
    / 加载插件处理函数/类。

    Args:
        plugin_name: Plugin name / 插件名称
        handler_dotpath: Dot-separated path to the handler
            / 处理函数的点分路径
            - "api.handlers.handle_current" → load handle_current from backend/api/handlers.py
            - "skills.weather_resolver.resolve" → load resolve from backend/skills/weather_resolver.py

    Returns:
        Function/class object, or None on failure / 函数/类对象，失败返回 None
    """
    if not handler_dotpath:
        return None

    parts = handler_dotpath.split(".")
    if len(parts) < 2:
        logger.warning(
            "Invalid handler path '{}' for plugin '{}': need at least module.attr",
            handler_dotpath,
            plugin_name,
        )
        return None

    module_dotpath = ".".join(parts[:-1])
    attr_name = parts[-1]

    # Try submodule loading first / 优先尝试子模块加载
    mod = load_plugin_module(plugin_name, module_dotpath)
    if mod is not None:
        attr = getattr(mod, attr_name, None)
        if attr is None:
            logger.warning(
                "Attribute '{}' not found in module '{}' for plugin '{}'",
                attr_name,
                module_dotpath,
                plugin_name,
            )
        return attr

    logger.warning(
        "Failed to load handler '{}' for plugin '{}': module '{}' not found",
        handler_dotpath,
        plugin_name,
        module_dotpath,
    )
    return None


def unload_plugin_modules(plugin_name: str) -> int:
    """
    Remove all modules of the specified plugin from sys.modules.
    / 从 sys.modules 中移除指定插件的所有模块。

    Called during plugin uninstall to avoid memory leaks and module residue.
    / 在卸载插件时调用，避免内存泄漏和模块残留。

    Returns:
        Number of modules removed / 移除的模块数量
    """
    prefix = f"plugins.{plugin_name}."
    exact = f"plugins.{plugin_name}"
    to_remove = [key for key in sys.modules if key == exact or key.startswith(prefix)]
    for key in to_remove:
        del sys.modules[key]

    if to_remove:
        logger.debug(
            "Unloaded {} modules for plugin '{}'",
            len(to_remove),
            plugin_name,
        )
    return len(to_remove)
