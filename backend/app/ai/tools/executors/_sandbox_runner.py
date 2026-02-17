"""
Toolkit 沙箱子进程运行器

独立进程中加载并执行 Toolkit 代码，与主进程隔离。
通过 stdin 接收 JSON 参数，stdout 输出 JSON 结果。

协议:
  stdin:  {"source_path": str, "method": str, "args": dict, "valves_config": dict}
  stdout: {"success": true, "output": str} | {"success": false, "error": str}

资源限制（Linux/macOS）:
  - 内存: 256MB (RLIMIT_AS)
  - CPU: 由父进程 asyncio.wait_for 控制
"""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from typing import Any


def _apply_resource_limits(memory_mb: int = 256) -> None:
    """设置资源限制（仅 Unix 系统）"""
    try:
        import resource

        memory_bytes = memory_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
    except (ImportError, OSError):
        # Windows 或权限不足，跳过
        pass


def _load_module(source_path: str) -> types.ModuleType:
    """从文件路径加载模块"""
    module_name = "_sandbox_toolkit"
    spec = importlib.util.spec_from_file_location(module_name, source_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot create module spec for {source_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _inject_valves(
    tools_instance: Any,
    module: types.ModuleType,
    valves_config: dict[str, Any],
) -> str | None:
    """注入 Valves 配置"""
    if not valves_config:
        return None

    valves_cls = getattr(module, "Valves", None)
    if valves_cls is None:
        return None

    try:
        normalized = {k.lower(): v for k, v in valves_config.items()}
        valves_instance = valves_cls(**normalized)
        tools_instance.valves = valves_instance
        return None
    except Exception as exc:
        return str(exc)


def _to_string(value: Any) -> str:
    """将返回值转为字符串"""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list)):
        try:
            return json.dumps(value, ensure_ascii=False, indent=2)
        except (TypeError, ValueError):
            return str(value)
    return str(value)


def main() -> None:
    """主入口：从 stdin 读取参数，执行后写入 stdout"""
    # 设置资源限制
    _apply_resource_limits()

    try:
        raw = sys.stdin.read()
        params = json.loads(raw)
    except (json.JSONDecodeError, Exception) as exc:
        _write_error(f"Invalid input: {exc}")
        return

    source_path = params.get("source_path", "")
    method_name = params.get("method", "")
    args = params.get("args", {})
    valves_config = params.get("valves_config", {})

    if not source_path or not method_name:
        _write_error("Missing source_path or method")
        return

    try:
        # 加载模块
        module = _load_module(source_path)

        # 实例化 Tools 类
        tools_cls = getattr(module, "Tools", None)
        if tools_cls is None:
            _write_error("Toolkit module has no 'Tools' class")
            return

        tools_instance = tools_cls()

        # 注入 Valves
        valves_error = _inject_valves(tools_instance, module, valves_config)

        # 查找方法
        method = getattr(tools_instance, method_name, None)
        if method is None or not callable(method):
            _write_error(f"Method '{method_name}' not found in Tools class")
            return

        # 执行（同步调用，async 方法用 asyncio.run）
        import asyncio
        import inspect

        if asyncio.iscoroutinefunction(method) or inspect.iscoroutinefunction(method):
            result_value = asyncio.run(method(**args))
        else:
            result_value = method(**args)

        output = _to_string(result_value)

        if valves_error:
            output = (
                f"[WARNING] Valves config injection failed: {valves_error}. "
                f"Tool ran with default values.\n\n{output}"
            )

        _write_result(output)

    except Exception as exc:
        _write_error(str(exc))


def _write_result(output: str) -> None:
    """写入成功结果"""
    sys.stdout.write(json.dumps({
        "success": True,
        "output": output,
    }, ensure_ascii=False))
    sys.stdout.flush()


def _write_error(error: str) -> None:
    """写入错误结果"""
    sys.stdout.write(json.dumps({
        "success": False,
        "error": error,
    }, ensure_ascii=False))
    sys.stdout.flush()


if __name__ == "__main__":
    main()
