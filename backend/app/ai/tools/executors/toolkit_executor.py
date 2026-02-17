"""
Toolkit 工具执行器

动态加载 Toolkit Python 源码，实例化 Tools 类，注入 Valves 配置，
调用指定方法并返回结果。支持 async 和 sync 方法。

参考 Open WebUI 的 Workspace Tools 执行模式：进程内 importlib 加载。
"""

from __future__ import annotations

import ast
import asyncio
import hashlib
import importlib
import importlib.util
import inspect
import json
import os
import sys
import tempfile
import time
import types
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.ai.tools.executors.base import BaseToolExecutor
from app.ai.tools.types import ToolDefinition, ToolResult
from app.core.logging import LogManager

if TYPE_CHECKING:
    from app.ai.tools.types import ExecutionContext

logger = LogManager.get_logger("ai.tool.toolkit")

# 沙箱模式：subprocess（子进程隔离）或 inprocess（进程内，开发环境用）
_SANDBOX_MODE = os.environ.get("TOOLKIT_SANDBOX_MODE", "subprocess")

# 沙箱运行器脚本路径
_SANDBOX_RUNNER_PATH = str(Path(__file__).parent / "_sandbox_runner.py")

# 已加载模块的缓存：toolkit_content sha256 → module
_MODULE_CACHE: dict[str, types.ModuleType] = {}
_CACHE_MAX_SIZE = 128

# --------------------------------------------------------------------------- #
# 安全：危险模块 / 内置函数黑名单
# --------------------------------------------------------------------------- #

_BLOCKED_MODULES: frozenset[str] = frozenset({
    # 进程 / OS
    "os", "subprocess", "shutil", "signal",
    "multiprocessing", "threading",
    # 系统内部
    "sys", "ctypes", "importlib",
    # 反序列化攻击
    "pickle", "marshal",
    # 数据库
    "sqlite3",
    # 原始网络
    "socket",
    # 文件系统
    "pathlib", "io", "tempfile", "glob", "fnmatch",
    # 代码生成
    "code", "codeop", "compileall", "py_compile",
    # 杂项
    "webbrowser", "antigravity",
    "builtins", "__builtin__",
})

_BLOCKED_MODULE_PREFIXES: tuple[str, ...] = (
    "app.",       # 应用内部模块
    "config.",    # 配置模块
)

_BLOCKED_BUILTINS: frozenset[str] = frozenset({
    "eval", "exec", "compile", "__import__",
    "open", "breakpoint", "exit", "quit",
})


class ToolkitExecutor(BaseToolExecutor):
    """
    Toolkit 工具执行器

    从 ToolDefinition.config 中读取：
    - _toolkit_content: Toolkit Python 源码
    - _toolkit_method: 要调用的方法名
    - _toolkit_is_async: 方法是否为 async
    - _valves_config: Valves 配置值 dict

    支持两种执行模式（通过 TOOLKIT_SANDBOX_MODE 环境变量控制）:
    - subprocess: 在子进程中执行（默认，安全隔离）
    - inprocess: 在主进程中执行（开发环境用）
    """

    def __init__(
        self,
        timeout: int = 30,
        max_output_size: int = 10000,
        sandbox_mode: str | None = None,
    ) -> None:
        self._timeout = timeout
        self._max_output_size = max_output_size
        self._sandbox_mode = sandbox_mode or _SANDBOX_MODE

    async def execute(
        self,
        definition: ToolDefinition,
        tool_call_id: str,
        arguments: dict[str, Any],
        context: ExecutionContext | None = None,
    ) -> ToolResult:
        """执行 Toolkit 方法调用"""
        start = time.perf_counter()
        method_name = definition.config.get("_toolkit_method", definition.name)
        toolkit_content = definition.config.get("_toolkit_content", "")
        valves_config = definition.config.get("_valves_config", {})
        trusted = definition.config.get("_toolkit_trusted", False)

        if not toolkit_content:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error="Toolkit source code is empty",
            )

        try:
            # 0. 安全扫描（非信任工具包）
            if not trusted:
                violations = _scan_toolkit_security(toolkit_content)
                if violations:
                    detail = "; ".join(violations[:5])
                    logger.warning(
                        "Toolkit security violation in %s: %s",
                        definition.name, detail,
                    )
                    return ToolResult(
                        tool_call_id=tool_call_id,
                        name=definition.name,
                        success=False,
                        error=f"Toolkit blocked: {detail}",
                    )

            # 根据沙箱模式选择执行方式
            if self._sandbox_mode == "subprocess":
                output = await self._execute_in_subprocess(
                    toolkit_content, method_name, arguments, valves_config,
                )
            else:
                output = await self._execute_inprocess(
                    toolkit_content, method_name, arguments, valves_config,
                )

            # 截断
            if len(output) > self._max_output_size:
                output = output[: self._max_output_size] + "\n... (truncated)"

            duration_ms = int((time.perf_counter() - start) * 1000)
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=True,
                output=output,
                duration_ms=duration_ms,
            )

        except asyncio.TimeoutError:
            duration_ms = int((time.perf_counter() - start) * 1000)
            logger.warning(
                "Toolkit execution timeout: %s.%s (%ds)",
                definition.name, method_name, self._timeout,
            )
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=f"Execution timed out after {self._timeout}s",
                duration_ms=duration_ms,
            )

        except TypeError as exc:
            # 参数不匹配
            duration_ms = int((time.perf_counter() - start) * 1000)
            logger.warning(
                "Toolkit method argument error: %s.%s: %s",
                definition.name,
                method_name,
                str(exc),
            )
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=f"Argument error: {exc}",
                duration_ms=duration_ms,
            )

        except Exception as exc:
            duration_ms = int((time.perf_counter() - start) * 1000)
            logger.error(
                "Toolkit execution error: %s.%s: %s",
                definition.name,
                method_name,
                str(exc),
                exc_info=True,
            )
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=str(exc),
                duration_ms=duration_ms,
            )

    async def _execute_in_subprocess(
        self,
        toolkit_content: str,
        method_name: str,
        arguments: dict[str, Any],
        valves_config: dict[str, Any],
    ) -> str:
        """
        在子进程中执行 Toolkit 代码（安全隔离）

        通过 _sandbox_runner.py 辅助脚本在独立进程中运行，
        主进程不受用户代码影响。

        Raises:
            asyncio.TimeoutError: 执行超时
            RuntimeError: 子进程执行失败
        """
        # 写入临时文件
        content_hash = hashlib.sha256(toolkit_content.encode("utf-8")).hexdigest()[:16]
        tmp_dir = Path(tempfile.gettempdir()) / "novusai_toolkits"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        source_path = tmp_dir / f"_toolkit_{content_hash}.py"
        source_path.write_text(toolkit_content, encoding="utf-8")

        # 构建 stdin 参数
        stdin_data = json.dumps({
            "source_path": str(source_path),
            "method": method_name,
            "args": arguments,
            "valves_config": valves_config,
        }, ensure_ascii=False)

        # 启动子进程
        proc = await asyncio.create_subprocess_exec(
            sys.executable, _SANDBOX_RUNNER_PATH,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=stdin_data.encode("utf-8")),
                timeout=self._timeout,
            )
        except asyncio.TimeoutError:
            # 超时：强制终止子进程
            try:
                proc.kill()
                await proc.wait()
            except ProcessLookupError:
                pass
            raise

        # 解析结果
        if proc.returncode != 0:
            err_msg = stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(
                f"Sandbox process exited with code {proc.returncode}: {err_msg}"
            )

        try:
            result = json.loads(stdout.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Invalid sandbox output: {exc}"
            ) from exc

        if not result.get("success"):
            raise RuntimeError(result.get("error", "Unknown sandbox error"))

        return result.get("output", "")

    async def _execute_inprocess(
        self,
        toolkit_content: str,
        method_name: str,
        arguments: dict[str, Any],
        valves_config: dict[str, Any],
    ) -> str:
        """
        在主进程中执行 Toolkit 代码（开发环境用）

        保留原有的 importlib 加载逻辑，不做进程隔离。
        """
        # 1. 加载模块（带缓存）
        module = _load_toolkit_module(toolkit_content)

        # 2. 实例化 Tools 类
        tools_cls = getattr(module, "Tools", None)
        if tools_cls is None:
            raise RuntimeError("Toolkit module has no 'Tools' class")

        tools_instance = tools_cls()

        # 3. 注入 Valves 配置
        valves_error = _inject_valves(tools_instance, module, valves_config)

        # 4. 查找目标方法
        method = getattr(tools_instance, method_name, None)
        if method is None or not callable(method):
            raise RuntimeError(f"Method '{method_name}' not found in Tools class")

        # 5. 调用方法（以运行时检测为准，忽略 config 中的 is_async 标记）
        if asyncio.iscoroutinefunction(method):
            result_value = await method(**arguments)
        else:
            # sync 方法在线程池中执行，避免阻塞事件循环
            loop = asyncio.get_running_loop()
            result_value = await loop.run_in_executor(
                None, lambda: method(**arguments)
            )

        # 6. 转为字符串
        output = _to_string(result_value)

        # 如果 Valves 注入失败，在输出前附加警告
        if valves_error:
            output = (
                f"[WARNING] Valves config injection failed: {valves_error}. "
                f"Tool ran with default values.\n\n{output}"
            )

        return output

    async def validate(
        self,
        definition: ToolDefinition,
        arguments: dict[str, Any],
    ) -> bool:
        """校验参数"""
        for param in definition.parameters:
            if param.required and param.name not in arguments:
                return False
        return True


# --------------------------------------------------------------------------- #
# 内部：安全扫描
# --------------------------------------------------------------------------- #


def _scan_toolkit_security(source: str) -> list[str]:
    """
    AST 静态分析：检测 Toolkit 源码中的危险 import 和内置函数调用。

    Returns:
        违规描述列表（空列表表示安全）。
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        # 语法错误由后续 importlib 加载时报告
        return []

    violations: list[str] = []

    for node in ast.walk(tree):
        # 检查 import xxx
        if isinstance(node, ast.Import):
            for alias in node.names:
                _check_module(alias.name, node.lineno, violations)

        # 检查 from xxx import yyy
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                _check_module(node.module, node.lineno, violations)

        # 检查危险内置函数调用：eval(), exec(), open() 等
        elif isinstance(node, ast.Call):
            func_name = _get_call_name(node)
            if func_name and func_name in _BLOCKED_BUILTINS:
                violations.append(
                    f"Blocked builtin '{func_name}()' at line {node.lineno}"
                )

    return violations


def _check_module(module_name: str, lineno: int, violations: list[str]) -> None:
    """检查模块名是否在黑名单中"""
    top_level = module_name.split(".")[0]
    if top_level in _BLOCKED_MODULES:
        violations.append(
            f"Blocked import '{module_name}' at line {lineno}"
        )
        return

    for prefix in _BLOCKED_MODULE_PREFIXES:
        if module_name.startswith(prefix):
            violations.append(
                f"Blocked import '{module_name}' at line {lineno}"
            )
            return


def _get_call_name(node: ast.Call) -> str | None:
    """从 AST Call 节点中提取函数名"""
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


# --------------------------------------------------------------------------- #
# 内部：模块加载
# --------------------------------------------------------------------------- #


def _load_toolkit_module(source: str) -> types.ModuleType:
    """
    动态加载 Toolkit Python 源码为模块。

    使用 content hash 做缓存，避免重复编译。
    """
    content_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()

    cached = _MODULE_CACHE.get(content_hash)
    if cached is not None:
        return cached

    # 写入临时文件后用 importlib 加载
    # 使用临时文件而非 exec() 以获得正确的 __file__ 和更好的错误追踪
    module_name = f"_toolkit_{content_hash[:16]}"

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

        # 缓存（LRU 简易实现）
        if len(_MODULE_CACHE) >= _CACHE_MAX_SIZE:
            # 移除最早的条目
            oldest_key = next(iter(_MODULE_CACHE))
            old_mod = _MODULE_CACHE.pop(oldest_key)
            # 清理 sys.modules
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
        # 清理失败的模块
        if module_name in sys.modules:
            del sys.modules[module_name]
        raise RuntimeError(f"Failed to load toolkit module: {exc}") from exc


def _inject_valves(
    tools_instance: Any,
    module: types.ModuleType,
    valves_config: dict[str, Any],
) -> str | None:
    """
    向 Tools 实例注入 Valves 配置。

    查找模块中的 Valves 类，用 valves_config 创建实例，
    赋值给 tools_instance.valves。

    Returns:
        None 表示成功（或无需注入），str 表示注入失败的错误描述。
    """
    if not valves_config:
        return None

    valves_cls = getattr(module, "Valves", None)
    if valves_cls is None:
        return None

    try:
        # Valves 继承自 BaseModel，用 dict 参数构造
        # 统一 lowercase：兼容旧版 UPPERCASE key 的 valves_config
        normalized = {k.lower(): v for k, v in valves_config.items()}
        valves_instance = valves_cls(**normalized)
        tools_instance.valves = valves_instance
        return None
    except Exception as exc:
        logger.warning(
            "Failed to inject Valves config: %s. Using defaults.",
            str(exc),
        )
        return str(exc)


def _to_string(value: Any) -> str:
    """将方法返回值转为字符串"""
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
    """清空 Toolkit 模块缓存（测试或热更新时使用）"""
    for mod in _MODULE_CACHE.values():
        mod_name = getattr(mod, "__name__", None)
        if mod_name and mod_name in sys.modules:
            del sys.modules[mod_name]
    _MODULE_CACHE.clear()
    logger.info("Toolkit module cache cleared")


__all__ = ["ToolkitExecutor", "clear_toolkit_cache"]
