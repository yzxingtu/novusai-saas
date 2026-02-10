"""
自定义代码工具执行器

在受限环境中执行 Python 代码片段，禁止危险操作（IO/网络/系统调用）
通过线程隔离避免阻塞事件循环
"""

import io
import json
import math
import multiprocessing
import multiprocessing.connection
import re
import time
from contextlib import redirect_stdout, redirect_stderr
from typing import Any

from app.ai.tools.executors.base import BaseToolExecutor
from app.ai.tools.types import ToolDefinition, ToolResult
from app.core.i18n import _
from app.core.logging import LogManager

logger = LogManager.get_logger("ai.tool.code")

# 禁止的导入模块（黑名单）
_BLOCKED_MODULES = frozenset({
    "os", "sys", "subprocess", "shutil", "pathlib",
    "socket", "http", "urllib", "requests", "httpx",
    "ctypes", "multiprocessing", "threading",
    "signal", "resource", "pty", "fcntl",
    "importlib", "pickle", "shelve", "marshal",
    "builtins", "__builtin__",
    "code", "codeop", "compile", "compileall",
})

# 禁止的内置函数
_BLOCKED_BUILTINS = frozenset({
    "exec", "eval", "compile", "__import__",
    "open", "input", "breakpoint",
    "exit", "quit",
    "globals", "locals", "vars", "dir",
    "getattr", "setattr", "delattr",
    "memoryview",
})

# 危险模式正则（import 语句 + __开头的魔术属性访问）
_DANGEROUS_PATTERNS = [
    re.compile(r"\bimport\s+(" + "|".join(_BLOCKED_MODULES) + r")\b"),
    re.compile(r"\bfrom\s+(" + "|".join(_BLOCKED_MODULES) + r")\s+import\b"),
    re.compile(r"__\w+__"),  # 禁止魔术属性访问
]

# 允许注入到执行环境的安全模块/函数
_SAFE_BUILTINS: dict[str, Any] = {
    # 类型
    "int": int,
    "float": float,
    "str": str,
    "bool": bool,
    "list": list,
    "dict": dict,
    "tuple": tuple,
    "set": set,
    "frozenset": frozenset,
    "bytes": bytes,
    "bytearray": bytearray,
    "type": type,
    "object": object,
    # 数学 / 转换
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sum": sum,
    "pow": pow,
    "divmod": divmod,
    "len": len,
    "range": range,
    "enumerate": enumerate,
    "zip": zip,
    "map": map,
    "filter": filter,
    "sorted": sorted,
    "reversed": reversed,
    "any": any,
    "all": all,
    # 格式化 / 字符串
    "repr": repr,
    "chr": chr,
    "ord": ord,
    "hex": hex,
    "oct": oct,
    "bin": bin,
    "format": format,
    "isinstance": isinstance,
    "issubclass": issubclass,
    "hash": hash,
    "id": id,
    "print": print,
    # 异常
    "Exception": Exception,
    "ValueError": ValueError,
    "TypeError": TypeError,
    "KeyError": KeyError,
    "IndexError": IndexError,
    "RuntimeError": RuntimeError,
    "StopIteration": StopIteration,
    "None": None,
    "True": True,
    "False": False,
}

# 默认限制
DEFAULT_TIMEOUT = 10
DEFAULT_MAX_OUTPUT = 5000


class CodeToolExecutor(BaseToolExecutor):
    """
    自定义代码工具执行器

    安全策略:
    - 代码模板由管理员在 config.code_template 中配置，LLM 只能传入参数
    - 静态检查：正则过滤危险导入和魔术属性
    - 运行时：使用受限 __builtins__ 字典，仅暴露安全函数
    - 线程隔离：通过 asyncio.to_thread 避免阻塞事件循环
    - stdout/stderr 捕获：重定向输出为字符串返回
    """

    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT,
        max_output_size: int = DEFAULT_MAX_OUTPUT,
    ):
        """
        Args:
            timeout: 执行超时秒数
            max_output_size: 最大输出字符数
        """
        self.timeout = timeout
        self.max_output_size = max_output_size

    async def execute(
        self,
        definition: ToolDefinition,
        tool_call_id: str,
        arguments: dict[str, Any],
    ) -> ToolResult:
        """
        执行自定义代码

        config 格式:
            code_template: Python 代码模板（含 {param} 占位符）
            allowed_modules: 额外允许导入的模块列表（可选，白名单追加）
        """
        import asyncio

        start = time.perf_counter()
        config = definition.config

        # 获取代码模板
        code_template: str = config.get("code_template", "")
        if not code_template:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=_("tool.error.code_missing_template"),
            )

        # 将参数注入模板
        try:
            code = code_template.format(**arguments)
        except (KeyError, IndexError) as e:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=_("tool.error.code_template_param_error", detail=str(e)),
            )

        # 静态安全检查
        safety_error = self._static_safety_check(code)
        if safety_error:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=safety_error,
            )

        # 构建执行环境
        allowed_modules = config.get("allowed_modules", [])
        exec_globals = self._build_exec_globals(allowed_modules)

        # 在子进程中执行（支持超时强制 kill，避免死循环占用线程）
        try:
            import asyncio

            output = await asyncio.to_thread(
                self._run_code_in_process, code, exec_globals, self.timeout,
            )

            # 截断输出
            if len(output) > self.max_output_size:
                output = output[: self.max_output_size] + "\n...[truncated]"

            duration_ms = int((time.perf_counter() - start) * 1000)

            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=True,
                output=output,
                duration_ms=duration_ms,
            )

        except TimeoutError:
            duration_ms = int((time.perf_counter() - start) * 1000)
            logger.warning(
                "Code tool timed out: %s after %dms (timeout=%ds)",
                definition.name,
                duration_ms,
                self.timeout,
            )
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=_("tool.error.code_execution_timeout", timeout=self.timeout),
                duration_ms=duration_ms,
            )

        except Exception as exc:
            duration_ms = int((time.perf_counter() - start) * 1000)
            logger.error(
                "Code tool error: %s: %s",
                definition.name,
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

    async def validate(
        self,
        definition: ToolDefinition,
        arguments: dict[str, Any],
    ) -> bool:
        """校验代码工具参数"""
        config = definition.config
        if not config.get("code_template"):
            return False

        for param in definition.parameters:
            if param.required and param.name not in arguments:
                return False

        return True

    # ========================================
    # 安全检查
    # ========================================

    @staticmethod
    def _static_safety_check(code: str) -> str:
        """
        静态安全检查

        Returns:
            错误信息字符串，为空表示通过
        """
        for pattern in _DANGEROUS_PATTERNS:
            match = pattern.search(code)
            if match:
                return _("tool.error.code_prohibited_pattern", pattern=match.group())

        return ""

    @staticmethod
    def _build_exec_globals(allowed_modules: list[str] | None = None) -> dict[str, Any]:
        """
        构建受限执行环境

        Args:
            allowed_modules: 额外允许的模块（仅 json/math/re/datetime/collections）
        """
        safe_globals: dict[str, Any] = {
            "__builtins__": _SAFE_BUILTINS.copy(),
        }

        # 安全模块白名单（仅允许纯计算模块）
        safe_importable = {
            "json": json,
            "math": math,
            "re": re,
        }

        # 仅注入管理员显式允许的模块
        for mod_name in (allowed_modules or []):
            if mod_name in safe_importable:
                safe_globals[mod_name] = safe_importable[mod_name]

        # 默认总是注入 json 和 math（常用且安全）
        safe_globals["json"] = json
        safe_globals["math"] = math

        return safe_globals

    @staticmethod
    def _run_code_in_process(
        code: str,
        exec_globals: dict[str, Any],
        timeout: int,
    ) -> str:
        """
        在子进程中执行代码，支持超时强制终止。

        使用 multiprocessing.Process + Pipe 而非 to_thread，
        確保死循环代码可被 kill，不会永久占用线程。

        Args:
            code: 待执行代码
            exec_globals: 受限执行环境
            timeout: 超时秒数

        Returns:
            执行输出字符串

        Raises:
            TimeoutError: 执行超时
            RuntimeError: 执行失败
        """
        parent_conn, child_conn = multiprocessing.Pipe(duplex=False)

        proc = multiprocessing.Process(
            target=CodeToolExecutor._code_worker,
            args=(code, exec_globals, child_conn),
            daemon=True,
        )
        proc.start()
        child_conn.close()  # 父进程不写

        # 等待子进程完成
        if parent_conn.poll(timeout):
            result = parent_conn.recv()  # {"ok": str} or {"error": str}
        else:
            # 超时：强制终止子进程
            proc.kill()
            proc.join(timeout=2)
            parent_conn.close()
            raise TimeoutError(f"Code execution timed out after {timeout}s")

        proc.join(timeout=2)
        parent_conn.close()

        if "error" in result:
            raise RuntimeError(result["error"])
        return result.get("ok", "(no output)")

    @staticmethod
    def _code_worker(
        code: str,
        exec_globals: dict[str, Any],
        conn: multiprocessing.connection.Connection,
    ) -> None:
        """子进程工作函数：执行代码并通过 Pipe 回传结果"""
        try:
            stdout_buf = io.StringIO()
            stderr_buf = io.StringIO()
            exec_locals: dict[str, Any] = {}

            with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
                exec(code, exec_globals, exec_locals)  # noqa: S102

            # 优先使用 result 变量
            if "result" in exec_locals:
                result_val = exec_locals["result"]
                if isinstance(result_val, str):
                    conn.send({"ok": result_val})
                else:
                    try:
                        conn.send({"ok": json.dumps(result_val, ensure_ascii=False, default=str)})
                    except (TypeError, ValueError):
                        conn.send({"ok": str(result_val)})
                return

            output = stdout_buf.getvalue()
            errors = stderr_buf.getvalue()
            if errors:
                text = f"{output}\n[stderr]\n{errors}" if output else f"[stderr]\n{errors}"
            else:
                text = output or "(no output)"
            conn.send({"ok": text})
        except Exception as exc:
            conn.send({"error": str(exc)})
        finally:
            conn.close()


__all__ = ["CodeToolExecutor"]
