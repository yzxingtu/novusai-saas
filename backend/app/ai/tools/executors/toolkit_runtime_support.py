"""
Toolkit runtime helpers for module loading, valves injection, and output formatting.
Toolkit 运行时支持：模块加载、Valves 注入与输出格式化。
"""

from __future__ import annotations

import hashlib
import importlib.util
import inspect
import sys
import tempfile
import types
from pathlib import Path
from typing import Any

from app.core.logging import LogManager
from app.core.response import build_public_error_text

logger = LogManager.get_logger("ai.tool.toolkit")

_MODULE_CACHE: dict[str, types.ModuleType] = {}
_CACHE_MAX_SIZE = 128


def _validate_valves_config_keys(
    valves_cls: type,
    valves_config: dict[str, Any],
) -> None:
    model_fields = getattr(valves_cls, "model_fields", None) or getattr(
        valves_cls,
        "__fields__",
        None,
    )
    if isinstance(model_fields, dict):
        allowed = {str(key) for key in model_fields}
    else:
        signature = inspect.signature(valves_cls)
        parameters = list(signature.parameters.values())
        if any(param.kind == inspect.Parameter.VAR_KEYWORD for param in parameters):
            return
        allowed = {
            param.name
            for param in parameters
            if param.name != "self"
            and param.kind
            in {inspect.Parameter.KEYWORD_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD}
        }

    unknown = sorted(str(key) for key in valves_config if str(key) not in allowed)
    if unknown:
        raise ValueError(f"Unknown Valves config keys: {', '.join(unknown)}")


def load_toolkit_module(source: str) -> types.ModuleType:
    """
    动态加载 Toolkit Python 源码为模块 / Dynamically load Toolkit Python source code as a module.

    Uses content hash for caching to avoid repeated compilation.
    使用 content hash 做缓存，避免重复编译。
    """
    content_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()

    cached = _MODULE_CACHE.get(content_hash)
    if cached is not None:
        return cached

    # Write to temp file then load with importlib
    # Use temp file instead of exec() for correct __file__ and better error tracing
    # 写入临时文件后用 importlib 加载
    # 使用临时文件而非 exec() 以获得正确的 __file__ 和更好的错误追踪
    module_name = f"_toolkit_{content_hash[:16]}"

    # If module name already exists in sys.modules, reuse directly
    # 如果模块名已存在于 sys.modules 中，直接复用
    if module_name in sys.modules:
        mod = sys.modules[module_name]
        _MODULE_CACHE[content_hash] = mod
        return mod

    tmp_dir = Path(tempfile.gettempdir()) / "novusai_toolkits"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_file = tmp_dir / f"{module_name}.py"

    try:
        tmp_file.write_text(source, encoding="utf-8")

        spec = importlib.util.spec_from_file_location(module_name, str(tmp_file))
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Cannot create module spec for {tmp_file}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        # Cache (simple LRU implementation) / 缓存（LRU 简易实现）
        if len(_MODULE_CACHE) >= _CACHE_MAX_SIZE:
            # Remove oldest entry / 移除最早的条目
            oldest_key = next(iter(_MODULE_CACHE))
            old_mod = _MODULE_CACHE.pop(oldest_key)
            # Clean up sys.modules / 清理 sys.modules
            mod_name = getattr(old_mod, "__name__", None)
            if mod_name and mod_name in sys.modules:
                del sys.modules[mod_name]

        _MODULE_CACHE[content_hash] = module
        return module

    except SyntaxError as exc:
        raise RuntimeError(
            f"Toolkit syntax error at line {exc.lineno}: {exc.msg}"
        ) from exc
    except Exception as exc:
        # Clean up failed module / 清理失败的模块
        if module_name in sys.modules:
            del sys.modules[module_name]
        raise RuntimeError(f"Failed to load toolkit module: {exc}") from exc


def inject_valves(
    tools_instance: Any,
    module: types.ModuleType,
    valves_config: dict[str, Any],
) -> None:
    """
    向 Tools 实例注入 Valves 配置 / Inject Valves configuration into the Tools instance.

    Finds the Valves class in the module, creates an instance with valves_config,
    and assigns it to tools_instance.valves.
    查找模块中的 Valves 类，用 valves_config 创建实例，
    赋值给 tools_instance.valves。

    Raises:
        RuntimeError when Valves config cannot be injected. / Valves 配置无法注入时抛出 RuntimeError。
    """
    if not valves_config:
        return

    valves_cls = getattr(module, "Valves", None)
    if valves_cls is None:
        return

    try:
        # 中文: Valves 配置只接受 canonical 字段名，避免旧 key 大小写兼容继续改写运行时契约。
        # EN: Valves config accepts only canonical field names so legacy key casing cannot rewrite the runtime contract.
        _validate_valves_config_keys(valves_cls, valves_config)
        valves_instance = valves_cls(**valves_config)
        tools_instance.valves = valves_instance
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Failed to inject Valves config: {}",
            str(exc),
        )
        raise RuntimeError(
            build_public_error_text(
                message="Valves config injection failed",
                exc=exc,
            )
        ) from exc


def format_toolkit_output(value: Any) -> str:
    """Convert method return value to string / 将方法返回值转为字符串"""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list)):
        import json

        try:
            return json.dumps(value, ensure_ascii=False, indent=2)
        except (TypeError, ValueError):
            return str(value)
    return str(value)


def clear_toolkit_cache() -> None:
    """清空 Toolkit 模块缓存（测试或热更新时使用）/ Clear Toolkit module cache (used during testing or hot updates)."""
    for mod in _MODULE_CACHE.values():
        mod_name = getattr(mod, "__name__", None)
        if mod_name and mod_name in sys.modules:
            del sys.modules[mod_name]
    _MODULE_CACHE.clear()
    logger.info("Toolkit module cache cleared")


__all__ = [
    "clear_toolkit_cache",
    "format_toolkit_output",
    "inject_valves",
    "load_toolkit_module",
]
