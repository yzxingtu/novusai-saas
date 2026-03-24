"""
Code Execution Tool Executor / 代码执行工具执行器

Executes user-provided code in a secure sandbox (subprocess isolation + module whitelist + timeout control).
在安全沙箱中执行用户提供的代码（子进程隔离 + 模块白名单 + 超时控制）。
"""

from __future__ import annotations

import asyncio
import json
import sys
import textwrap
import time
from typing import TYPE_CHECKING, Any

from app.ai.tools.executors.base import BaseToolExecutor
from app.ai.tools.types import ToolDefinition, ToolResult
from app.core.logging import LogManager
from app.core.response import build_public_error_text

if TYPE_CHECKING:
    from app.ai.tools.types import ExecutionContext

logger = LogManager.get_logger("ai.tool.code_execution")

# Security limits / 安全限制
_MAX_OUTPUT_SIZE = 50_000  # 50KB / 最大输出约 50KB
_DEFAULT_TIMEOUT = 30
_DEFAULT_MEMORY_LIMIT_MB = 256

# Absolutely blocked imports (regardless of whitelist settings)
# 绝对禁止的 import（无论白名单如何设置）
_BLOCKED_MODULES = frozenset({
    "os", "subprocess", "shutil", "sys", "importlib",
    "ctypes", "socket", "http", "urllib", "requests",
    "httpx", "aiohttp", "pathlib", "glob", "tempfile",
    "signal", "multiprocessing", "threading", "pickle",
    "shelve", "marshal", "code", "compile", "exec",
    "eval", "builtins", "__builtins__",
})


# Dangerous builtins to exclude from user code namespace (escape surface)
# 用户代码命名空间中必须排除的危险 builtins（exec/eval/compile/open 逃逸面收口）
_DANGEROUS_BUILTINS = frozenset({
    "exec", "eval", "compile", "open", "__import__",
    "globals", "locals", "vars", "breakpoint", "input",
})


def _build_sandbox_script(
    user_code: str,
    allowed_modules: list[str],
) -> str:
    """
    Build sandbox execution script.
    构建沙箱执行脚本。

    1. Create restricted __builtins__ dict (exclude exec/eval/compile/open etc.)
       创建受限 __builtins__ 字典，排除 exec/eval/compile/open 等
    2. Only allow whitelisted module imports / 仅允许白名单模块 import
    3. Capture stdout output / 捕获 stdout 输出
    4. Catch exceptions and return as JSON / 捕获异常并以 JSON 返回
    """
    allowed_set = json.dumps(allowed_modules)
    escaped_code = user_code.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")
    dangerous_set = ", ".join(repr(b) for b in _DANGEROUS_BUILTINS)
    blocked_set = ", ".join(repr(m) for m in _BLOCKED_MODULES)

    return textwrap.dedent(f"""\
import sys
import io
import json

# 1. Restricted builtins for user code (no exec/eval/compile/open) / 用户代码受限 builtins
_orig_builtins = __builtins__ if isinstance(__builtins__, dict) else vars(__builtins__)
_restricted_builtins = {{k: v for k, v in _orig_builtins.items() if k not in ({dangerous_set})}}

_ALLOWED = set({allowed_set})
_BLOCKED = {{{blocked_set}}}

def _safe_import(name, *args, **kwargs):
    top = name.split(".")[0]
    if top in _BLOCKED:
        raise ImportError(f"Module '{{top}}' is not allowed in sandbox")
    if _ALLOWED and top not in _ALLOWED:
        raise ImportError(f"Module '{{top}}' is not in the allowed list")
    return __import__(name, *args, **kwargs)

_restricted_builtins["__import__"] = _safe_import

# 2. Capture stdout / 捕获 stdout
_stdout_capture = io.StringIO()
sys.stdout = _stdout_capture

# 3. Execute user code with restricted builtins / 使用受限 builtins 执行用户代码
try:
    _user_code = '{escaped_code}'
    _code_obj = compile(_user_code, "<sandbox>", "exec")
    _ns = {{"__builtins__": _restricted_builtins}}
    exec(_code_obj, _ns)
    _output = _stdout_capture.getvalue()
    sys.stdout = sys.__stdout__
    print(json.dumps({{"success": True, "output": _output}}))
except Exception as _e:
    sys.stdout = sys.__stdout__
    _partial = _stdout_capture.getvalue()
    print(json.dumps({{"success": False, "error": str(_e), "output": _partial}}))
""")


class CodeExecutionExecutor(BaseToolExecutor):
    """
    Code execution tool executor.
    代码执行工具执行器。

    Reads from ToolDefinition.config:
    从 ToolDefinition.config 中读取：
    - _code_language: Programming language (currently only python supported)
      编程语言（当前仅支持 python）
    - _code_timeout: Execution timeout in seconds / 执行超时秒数
    - _code_memory_limit_mb: Memory limit / 内存限制
    - _code_allowed_modules: List of allowed import modules / 允许导入的模块列表
    """

    async def execute(
        self,
        definition: ToolDefinition,
        tool_call_id: str,
        arguments: dict[str, Any],
        context: ExecutionContext | None = None,
    ) -> ToolResult:
        """Execute code in a subprocess sandbox / 在子进程沙箱中执行代码"""
        _ = context
        start = time.perf_counter()
        cfg = definition.config or {}

        code = arguments.get("code", "")
        if not code or not code.strip():
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error="No code provided",
            )

        language = cfg.get("_code_language", "python")
        if language != "python":
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=f"Language '{language}' is not supported. Only 'python' is available.",
            )

        timeout = cfg.get("_code_timeout", _DEFAULT_TIMEOUT)
        allowed_modules = cfg.get("_code_allowed_modules", [])

        # Static security scan / 静态安全扫描
        violations = self._static_scan(code)
        if violations:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=f"Code blocked: {'; '.join(violations[:3])}",
            )

        # Build sandbox script / 构建沙箱脚本
        sandbox_script = _build_sandbox_script(code, allowed_modules)

        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-c", sandbox_script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                duration_ms = int((time.perf_counter() - start) * 1000)
                return ToolResult(
                    tool_call_id=tool_call_id,
                    name=definition.name,
                    success=False,
                    error=f"Code execution timed out after {timeout}s",
                    duration_ms=duration_ms,
                )

            duration_ms = int((time.perf_counter() - start) * 1000)
            stdout_text = stdout_bytes.decode("utf-8", errors="replace").strip()

            # Parse JSON result / 解析 JSON 结果
            try:
                result_data = json.loads(stdout_text)
                output = result_data.get("output", "")
                if len(output) > _MAX_OUTPUT_SIZE:
                    output = output[:_MAX_OUTPUT_SIZE] + "\n... (truncated)"

                if result_data.get("success"):
                    return ToolResult(
                        tool_call_id=tool_call_id,
                        name=definition.name,
                        success=True,
                        output=output if output else "(no output)",
                        duration_ms=duration_ms,
                    )
                else:
                    error_msg = result_data.get("error", "Unknown error")
                    partial = result_data.get("output", "")
                    return ToolResult(
                        tool_call_id=tool_call_id,
                        name=definition.name,
                        success=False,
                        error=build_public_error_text(
                            message="Code execution failed",
                            detail=(
                                f"{error_msg}\nPartial output: {partial}"
                                if partial
                                else error_msg
                            ),
                        ),
                        duration_ms=duration_ms,
                    )
            except json.JSONDecodeError:
                # Subprocess output is not valid JSON (possibly a crash or syntax error)
                # 子进程输出不是有效 JSON（可能是崩溃或语法错误）
                stderr_text = stderr_bytes.decode("utf-8", errors="replace").strip()
                error = stderr_text or stdout_text or "Unknown execution error"
                return ToolResult(
                    tool_call_id=tool_call_id,
                    name=definition.name,
                    success=False,
                    error=build_public_error_text(
                        message="Code execution failed",
                        detail=error[:1000],
                    ),
                    duration_ms=duration_ms,
                )

        except Exception as exc:
            duration_ms = int((time.perf_counter() - start) * 1000)
            logger.error("Code execution error: {}", str(exc), exc_info=True)
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=build_public_error_text(
                    message="Code execution failed",
                    exc=exc,
                ),
                duration_ms=duration_ms,
            )

    async def validate(
        self,
        definition: ToolDefinition,
        arguments: dict[str, Any],
    ) -> bool:
        """Validate code execution arguments / 校验代码执行参数"""
        _ = definition
        return bool(arguments.get("code"))

    @staticmethod
    def _static_scan(code: str) -> list[str]:
        """
        Static security scan: detect dangerous patterns. / 静态安全扫描：检测危险模式。

        Returns:
            List of violations (empty list means safe)
            违规列表（空列表表示安全）
        """
        violations: list[str] = []
        import re

        # Detect direct import of dangerous modules / 检测直接 import 危险模块
        for mod in _BLOCKED_MODULES:
            pattern = rf'\b(?:import\s+{re.escape(mod)}|from\s+{re.escape(mod)}\s+import)\b'
            if re.search(pattern, code):
                violations.append(f"Blocked import: {mod}")

        # Detect eval/exec calls / 检测 eval/exec 调用
        if re.search(r'\b(?:eval|exec|compile)\s*\(', code):
            violations.append("Direct eval/exec/compile calls are not allowed")

        # Detect file operations / 检测文件操作
        if re.search(r'\bopen\s*\(', code):
            violations.append("File operations (open) are not allowed")

        return violations


__all__ = ["CodeExecutionExecutor"]
