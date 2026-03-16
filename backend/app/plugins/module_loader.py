"""
Unified plugin module loader.
/ 插件模块统一加载器

All dynamic imports of plugin modules go through this entry point,
avoiding scattered importlib.util code and ensuring consistent module_name
naming and correct sys.modules cache sharing.
/ 所有插件模块的动态导入统一走此入口。

module_name convention: plugins.{plugin_name}.backend.{dotted_path}
Physical path convention: backend/plugins/{plugin_name}/backend/{path_parts...}.py
/ module_name 约定 / 物理路径约定
"""

from __future__ import annotations

import importlib.util
import inspect
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
    module_file = plugins_dir / plugin_name / "backend" / Path(*parts).with_suffix(".py")

    # Try direct file path / 尝试直接文件路径
    if not module_file.is_file():
        # Try directory __init__.py / 尝试目录 __init__.py
        module_dir = plugins_dir / plugin_name / "backend" / Path(*parts) / "__init__.py"
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
            module_name, exc, exc_info=True,
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
            handler_dotpath, plugin_name,
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
                attr_name, module_dotpath, plugin_name,
            )
        return attr

    # Fallback: try loading from main module's getattr chain
    # (supports cases where handler is directly defined or imported in main.py)
    # / 回退: 尝试从 main module 的 getattr 链加载
    main_mod = load_plugin_module(plugin_name, "main")
    if main_mod is None:
        logger.warning(
            "Failed to load handler '{}' for plugin '{}': "
            "neither submodule '%s' nor main.py found",
            handler_dotpath, plugin_name, module_dotpath,
        )
        return None

    obj = main_mod
    for part in parts:
        obj = getattr(obj, part, None)
        if obj is None:
            logger.warning(
                "Failed to load handler '{}' for plugin '{}': "
                "attribute '%s' not found in getattr chain on main module",
                handler_dotpath, plugin_name, part,
            )
            return None
    return obj


def _find_executor_in_module(mod: Any) -> type | None:
    """Find BaseToolExecutor subclass in module / 在模块中查找 BaseToolExecutor 子类"""
    from app.ai.tools.executors.base import BaseToolExecutor

    for _name, obj in inspect.getmembers(mod, inspect.isclass):
        if issubclass(obj, BaseToolExecutor) and obj is not BaseToolExecutor:
            return obj
    return None


def load_plugin_executor(plugin_name: str, skill_type: str) -> type | None:
    """
    Load a plugin's executor class.
    / 加载插件的 executor 类。

    Lookup order:
    1. Convention path: backend/executors/{skill_type}_executor.py
    2. Fallback scan: all *_executor.py files under backend/executors/
    / 查找顺序：约定路径 → 回退扫描

    Args:
        plugin_name: Plugin name / 插件名称
        skill_type: Skill type (e.g. "toolkit", "weather_widget") / 技能类型

    Returns:
        BaseToolExecutor subclass, or None if not found / BaseToolExecutor 子类，找不到返回 None
    """
    # 1. Look up by convention name / 按约定名称查找
    executor_module_name = f"{skill_type.replace('-', '_')}_executor"
    mod = load_plugin_module(plugin_name, f"executors.{executor_module_name}")
    if mod is not None:
        try:
            cls = _find_executor_in_module(mod)
            if cls:
                return cls
        except Exception as exc:
            logger.warning(
                "Failed to find executor class for skill_type '{}' in plugin '{}': {}",
                skill_type, plugin_name, exc,
            )

    # 2. Fallback: scan all *_executor.py in executors directory
    # / 回退：扫描 executors 目录下所有 *_executor.py
    plugins_dir = _get_plugins_dir()
    executors_dir = plugins_dir / plugin_name / "backend" / "executors"
    if not executors_dir.is_dir():
        return None

    for py_file in executors_dir.glob("*_executor.py"):
        stem = py_file.stem
        if stem == executor_module_name:
            continue  # Already tried / 已经尝试过
        fallback_mod = load_plugin_module(plugin_name, f"executors.{stem}")
        if fallback_mod is None:
            continue
        try:
            cls = _find_executor_in_module(fallback_mod)
            if cls:
                logger.info(
                    "Found plugin executor {} in fallback scan for plugin '{}'",
                    cls.__name__, plugin_name,
                )
                return cls
        except Exception:
            continue

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
    to_remove = [
        key for key in sys.modules
        if key == exact or key.startswith(prefix)
    ]
    for key in to_remove:
        del sys.modules[key]

    if to_remove:
        logger.debug(
            "Unloaded {} modules for plugin '{}'",
            len(to_remove), plugin_name,
        )
    return len(to_remove)
