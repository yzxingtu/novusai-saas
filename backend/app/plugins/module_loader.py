"""
插件模块统一加载器

所有插件模块的动态导入统一走此入口，避免散落各处的 importlib.util 代码，
确保 module_name 命名一致、sys.modules 缓存正确共享。

module_name 约定: plugins.{plugin_name}.backend.{dotted_path}
物理路径约定: backend/plugins/{plugin_name}/backend/{path_parts...}.py
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
    """延迟获取 PLUGINS_DIR，避免循环导入"""
    from app.plugins.loader import PLUGINS_DIR
    return PLUGINS_DIR


def load_plugin_module(plugin_name: str, dotted_path: str) -> Any | None:
    """
    加载插件子模块。

    Args:
        plugin_name: 插件名称 (如 "my-plugin")
        dotted_path: 模块在 backend/ 下的点分路径 (如 "api.handlers", "skills.my_resolver")

    Returns:
        已加载的模块对象，失败返回 None
    """
    plugins_dir = _get_plugins_dir()

    parts = dotted_path.split(".")
    module_file = plugins_dir / plugin_name / "backend" / Path(*parts).with_suffix(".py")

    # 尝试直接文件路径
    if not module_file.is_file():
        # 尝试目录 __init__.py
        module_dir = plugins_dir / plugin_name / "backend" / Path(*parts) / "__init__.py"
        if module_dir.is_file():
            module_file = module_dir
        else:
            logger.debug("Plugin module file not found: %s", module_file)
            return None

    module_name = f"plugins.{plugin_name}.backend.{dotted_path}"
    try:
        if module_name in sys.modules:
            return sys.modules[module_name]

        spec = importlib.util.spec_from_file_location(module_name, module_file)
        if spec is None or spec.loader is None:
            logger.warning("Cannot create module spec for %s", module_name)
            return None

        mod = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = mod
        spec.loader.exec_module(mod)
        return mod
    except Exception as exc:
        # 清理失败的模块条目
        sys.modules.pop(module_name, None)
        logger.warning(
            "Failed to load plugin module %s: %s",
            module_name, exc, exc_info=True,
        )
        return None


def load_plugin_handler(plugin_name: str, handler_dotpath: str) -> Any | None:
    """
    加载插件处理函数/类。

    Args:
        plugin_name: 插件名称
        handler_dotpath: 处理函数的点分路径
            - "api.handlers.handle_current" → 加载 backend/api/handlers.py 的 handle_current
            - "skills.weather_resolver.resolve" → 加载 backend/skills/weather_resolver.py 的 resolve

    Returns:
        函数/类对象，失败返回 None
    """
    if not handler_dotpath:
        return None

    parts = handler_dotpath.split(".")
    if len(parts) < 2:
        logger.warning(
            "Invalid handler path '%s' for plugin '%s': need at least module.attr",
            handler_dotpath, plugin_name,
        )
        return None

    module_dotpath = ".".join(parts[:-1])
    attr_name = parts[-1]

    # 优先尝试子模块加载
    mod = load_plugin_module(plugin_name, module_dotpath)
    if mod is not None:
        attr = getattr(mod, attr_name, None)
        if attr is None:
            logger.warning(
                "Attribute '%s' not found in module '%s' for plugin '%s'",
                attr_name, module_dotpath, plugin_name,
            )
        return attr

    # 回退: 尝试从 main module 的 getattr 链加载
    # (支持 main.py 中直接定义或导入的情况)
    main_mod = load_plugin_module(plugin_name, "main")
    if main_mod is None:
        logger.warning(
            "Failed to load handler '%s' for plugin '%s': "
            "neither submodule '%s' nor main.py found",
            handler_dotpath, plugin_name, module_dotpath,
        )
        return None

    obj = main_mod
    for part in parts:
        obj = getattr(obj, part, None)
        if obj is None:
            logger.warning(
                "Failed to load handler '%s' for plugin '%s': "
                "attribute '%s' not found in getattr chain on main module",
                handler_dotpath, plugin_name, part,
            )
            return None
    return obj


def load_plugin_executor(plugin_name: str, skill_type: str) -> type | None:
    """
    加载插件的 executor 类。

    约定路径: backend/executors/{skill_type}_executor.py 中的 BaseToolExecutor 子类

    Args:
        plugin_name: 插件名称
        skill_type: 技能类型 (如 "weather_widget")

    Returns:
        BaseToolExecutor 子类，找不到返回 None
    """
    executor_module_name = f"{skill_type.replace('-', '_')}_executor"
    mod = load_plugin_module(plugin_name, f"executors.{executor_module_name}")
    if mod is None:
        return None

    try:
        from app.ai.tools.executors.base import BaseToolExecutor

        for _name, obj in inspect.getmembers(mod, inspect.isclass):
            if issubclass(obj, BaseToolExecutor) and obj is not BaseToolExecutor:
                return obj

        logger.warning(
            "No BaseToolExecutor subclass found in executor module for "
            "skill_type '%s' in plugin '%s'",
            skill_type, plugin_name,
        )
        return None
    except Exception as exc:
        logger.warning(
            "Failed to find executor class for skill_type '%s' in plugin '%s': %s",
            skill_type, plugin_name, exc,
        )
        return None


def unload_plugin_modules(plugin_name: str) -> int:
    """
    从 sys.modules 中移除指定插件的所有模块。

    在卸载插件时调用，避免内存泄漏和模块残留。

    Returns:
        移除的模块数量
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
            "Unloaded %d modules for plugin '%s'",
            len(to_remove), plugin_name,
        )
    return len(to_remove)
