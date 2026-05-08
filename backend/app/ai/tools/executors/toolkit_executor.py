"""
Toolkit Tool Executor. / Toolkit 工具执行器。

Dynamically loads Toolkit Python source code, instantiates the Tools class, injects Valves configuration,
calls the specified method and returns the result. Supports both async and sync methods.
动态加载 Toolkit Python 源码，实例化 Tools 类，注入 Valves 配置，
调用指定方法并返回结果。支持 async 和 sync 方法。

Reference: Open WebUI's Workspace Tools execution model: in-process importlib loading.
参考 Open WebUI 的 Workspace Tools 执行模式：进程内 importlib 加载。
"""

from __future__ import annotations

import asyncio
import contextvars
import hashlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.ai.tools.executors.base import BaseToolExecutor
from app.ai.tools.executors.toolkit_runtime_support import (
    clear_toolkit_cache as _clear_toolkit_cache,
)
from app.ai.tools.executors.toolkit_runtime_support import (
    format_toolkit_output as _to_string,
)
from app.ai.tools.executors.toolkit_runtime_support import (
    inject_valves as _inject_valves,
)
from app.ai.tools.executors.toolkit_runtime_support import (
    load_toolkit_module as _load_toolkit_module,
)
from app.ai.tools.executors.toolkit_security import (
    get_blocked_modules as _get_blocked_modules,
)
from app.ai.tools.executors.toolkit_security import (
    scan_toolkit_security as _scan_toolkit_security_impl,
)
from app.ai.tools.types import ToolDefinition, ToolResult
from app.core.logging import LogManager
from app.core.response import build_public_error_text
from app.enums.agent import ActionLevelEnum, ActionStatusEnum, ActionTypeEnum
from app.middleware.trace import trace_id_var
from app.services.ai.action_log_service import write_ai_action_log

if TYPE_CHECKING:
    from app.ai.tools.types import ExecutionContext

logger = LogManager.get_logger("ai.tool.toolkit")

# Sandbox mode: subprocess (child process isolation) or inprocess (in-process, for dev environment)
# 沙箱模式：subprocess（子进程隔离）或 inprocess（进程内，开发环境用）
_SANDBOX_MODE = os.environ.get("TOOLKIT_SANDBOX_MODE", "subprocess")

# Sandbox runner script path / 沙箱运行器脚本路径
_SANDBOX_RUNNER_PATH = str(Path(__file__).parent / "_sandbox_runner.py")

# --------------------------------------------------------------------------- #
# Security helpers (delegated) / 安全辅助（下沉）
# --------------------------------------------------------------------------- #


def get_blocked_modules(security_level: str | None = None) -> frozenset[str]:
    """Return the set of blocked modules based on security level. / 根据安全等级返回被阻止的模块集合。"""
    return _get_blocked_modules(security_level)


class ToolkitExecutor(BaseToolExecutor):
    """
    Toolkit tool executor. / Toolkit 工具执行器。

    Reads from ToolDefinition.config:
    从 ToolDefinition.config 中读取：
    - _toolkit_content: Toolkit Python source code / Toolkit Python 源码
    - _toolkit_method: Method name to call / 要调用的方法名
    - _toolkit_is_async: Whether the method is async / 方法是否为 async
    - _valves_config: Valves configuration values dict / Valves 配置值 dict

    Supports two execution modes (controlled by TOOLKIT_SANDBOX_MODE env var):
    支持两种执行模式（通过 TOOLKIT_SANDBOX_MODE 环境变量控制）:
    - subprocess: Execute in child process (default, secure isolation)
      在子进程中执行（默认，安全隔离）
    - inprocess: Execute in main process (for dev environment)
      在主进程中执行（开发环境用）
    """

    def __init__(
        self,
        timeout: int = 30,
        max_output_size: int = 10000,
        sandbox_mode: str | None = None,
        security_level: str = "normal",
        memory_limit_mb: int = 256,
    ) -> None:
        self._timeout = timeout
        self._max_output_size = max_output_size
        self._sandbox_mode = sandbox_mode or _SANDBOX_MODE
        self._security_level = security_level
        self._memory_limit_mb = memory_limit_mb

    async def execute(
        self,
        definition: ToolDefinition,
        tool_call_id: str,
        arguments: dict[str, Any],
        context: ExecutionContext | None = None,
    ) -> ToolResult:
        """Execute Toolkit method call / 执行 Toolkit 方法调用"""
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
            # 0. Security scan (untrusted toolkits) / 安全扫描（非信任工具包）
            if not trusted:
                violations = _scan_toolkit_security(
                    toolkit_content,
                    self._security_level,
                )
                if violations:
                    detail = "; ".join(violations[:5])
                    logger.warning(
                        "Toolkit security violation in {}: {}",
                        definition.name,
                        detail,
                    )
                    return ToolResult(
                        tool_call_id=tool_call_id,
                        name=definition.name,
                        success=False,
                        error=f"Toolkit blocked: {detail}",
                    )

            # Choose execution mode based on sandbox mode / 根据沙箱模式选择执行方式
            if self._sandbox_mode == "subprocess":
                output = await self._execute_in_subprocess(
                    toolkit_content,
                    method_name,
                    arguments,
                    valves_config,
                )
            else:
                output = await self._execute_inprocess(
                    toolkit_content,
                    method_name,
                    arguments,
                    valves_config,
                )

            # Truncate / 截断
            if len(output) > self._max_output_size:
                output = output[: self._max_output_size] + "\n... (truncated)"

            duration_ms = int((time.perf_counter() - start) * 1000)
            result = ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=True,
                output=output,
                duration_ms=duration_ms,
            )
            await self._audit_toolkit_action(
                definition=definition,
                context=context,
                tool_call_id=tool_call_id,
                method_name=method_name,
                arguments=arguments,
                status=ActionStatusEnum.SUCCESS.value,
                duration_ms=duration_ms,
                error_message=None,
            )
            return result

        except asyncio.TimeoutError:
            duration_ms = int((time.perf_counter() - start) * 1000)
            logger.warning(
                "Toolkit execution timeout: {}.{} ({}s)",
                definition.name,
                method_name,
                self._timeout,
            )
            result = ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=f"Execution timed out after {self._timeout}s",
                duration_ms=duration_ms,
            )
            await self._audit_toolkit_action(
                definition=definition,
                context=context,
                tool_call_id=tool_call_id,
                method_name=method_name,
                arguments=arguments,
                status=ActionStatusEnum.FAILED.value,
                duration_ms=duration_ms,
                error_message=result.error,
            )
            return result

        except TypeError as exc:
            # Argument mismatch / 参数不匹配
            duration_ms = int((time.perf_counter() - start) * 1000)
            logger.warning(
                "Toolkit method argument error: {}.{}: {}",
                definition.name,
                method_name,
                str(exc),
            )
            result = ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=build_public_error_text(
                    message="Toolkit argument error",
                    exc=exc,
                ),
                duration_ms=duration_ms,
            )
            await self._audit_toolkit_action(
                definition=definition,
                context=context,
                tool_call_id=tool_call_id,
                method_name=method_name,
                arguments=arguments,
                status=ActionStatusEnum.FAILED.value,
                duration_ms=duration_ms,
                error_message=result.error,
            )
            return result

        except Exception as exc:
            duration_ms = int((time.perf_counter() - start) * 1000)
            logger.error(
                "Toolkit execution error: {}.{}: {}",
                definition.name,
                method_name,
                str(exc),
                exc_info=True,
            )
            result = ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=build_public_error_text(
                    message="Toolkit execution failed",
                    exc=exc,
                ),
                duration_ms=duration_ms,
            )
            await self._audit_toolkit_action(
                definition=definition,
                context=context,
                tool_call_id=tool_call_id,
                method_name=method_name,
                arguments=arguments,
                status=ActionStatusEnum.FAILED.value,
                duration_ms=duration_ms,
                error_message=result.error,
            )
            return result

    async def _audit_toolkit_action(
        self,
        *,
        definition: ToolDefinition,
        context: ExecutionContext | None,
        tool_call_id: str,
        method_name: str,
        arguments: dict[str, Any],
        status: str,
        duration_ms: int,
        error_message: str | None,
    ) -> None:
        if not context or not context.db:
            return
        try:
            await write_ai_action_log(
                context.db,
                tenant_id=context.tenant_id,
                agent_id=context.agent_id,
                operator_id=context.user_id,
                operator_type=context.user_role,
                conversation_id=context.conversation_id,
                tool_call_id=tool_call_id,
                skill_id=context.skill_id,
                action_name=f"toolkit_{method_name}",
                action_type=ActionTypeEnum.ACTION.value,
                action_level=ActionLevelEnum.DANGEROUS.value,
                request_data={
                    "tool_name": definition.name,
                    "trace_id": trace_id_var.get() or None,
                    "method_name": method_name,
                    "arguments": arguments,
                    "trusted": bool(definition.config.get("_toolkit_trusted", False)),
                },
                response_data=None,
                status=status,
                error_message=error_message,
                duration_ms=duration_ms,
            )
        except Exception as exc:
            logger.warning("Failed to write toolkit audit log: {}", str(exc))

    async def _execute_in_subprocess(
        self,
        toolkit_content: str,
        method_name: str,
        arguments: dict[str, Any],
        valves_config: dict[str, Any],
    ) -> str:
        """
        Execute Toolkit code in a child process (secure isolation).
        在子进程中执行 Toolkit 代码（安全隔离）。

        Runs via the _sandbox_runner.py helper script in an independent process,
        so the main process is not affected by user code.
        通过 _sandbox_runner.py 辅助脚本在独立进程中运行，
        主进程不受用户代码影响。

        Raises:
            asyncio.TimeoutError: Execution timeout / 执行超时
            RuntimeError: Child process execution failed / 子进程执行失败
        """
        # Write to temporary file / 写入临时文件
        content_hash = hashlib.sha256(toolkit_content.encode("utf-8")).hexdigest()[:16]
        tmp_dir = Path(tempfile.gettempdir()) / "novusai_toolkits"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        source_path = tmp_dir / f"_toolkit_{content_hash}.py"
        source_path.write_text(toolkit_content, encoding="utf-8")

        # Build stdin arguments / 构建 stdin 参数
        stdin_data = json.dumps(
            {
                "source_path": str(source_path),
                "method": method_name,
                "args": arguments,
                "valves_config": valves_config,
                "memory_limit_mb": self._memory_limit_mb,
            },
            ensure_ascii=False,
        )

        # Start child process / 启动子进程
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            _SANDBOX_RUNNER_PATH,
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
            # Timeout: forcefully terminate child process / 超时：强制终止子进程
            try:
                proc.kill()
                await proc.wait()
            except ProcessLookupError:
                pass
            raise

        # Parse result / 解析结果
        if proc.returncode != 0:
            err_msg = stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(
                f"Sandbox process exited with code {proc.returncode}: {err_msg}"
            )

        try:
            result = json.loads(stdout.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Invalid sandbox output: {exc}") from exc

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
        在主进程中执行 Toolkit 代码（开发环境用）/ Execute Toolkit code in the main process (for dev environment).

        Keeps the original importlib loading logic, no process isolation.
        保留原有的 importlib 加载逻辑，不做进程隔离。
        """
        # 1. Load module (with cache) / 加载模块（带缓存）
        module = _load_toolkit_module(toolkit_content)

        # 2. Instantiate Tools class / 实例化 Tools 类
        tools_cls = getattr(module, "Tools", None)
        if tools_cls is None:
            raise RuntimeError("Toolkit module has no 'Tools' class")

        tools_instance = tools_cls()

        # 3. Inject Valves configuration / 注入 Valves 配置
        _inject_valves(tools_instance, module, valves_config)

        # 4. Find target method / 查找目标方法
        method = getattr(tools_instance, method_name, None)
        if method is None or not callable(method):
            raise RuntimeError(f"Method '{method_name}' not found in Tools class")

        # 5. Call method (use runtime detection, ignore is_async flag in config)
        # 5. 调用方法（以运行时检测为准，忽略 config 中的 is_async 标记）
        if asyncio.iscoroutinefunction(method):
            result_value = await method(**arguments)
        else:
            # sync methods run in thread pool to avoid blocking the event loop
            # sync 方法在线程池中执行，避免阻塞事件循环
            loop = asyncio.get_running_loop()
            ctx = contextvars.copy_context()
            result_value = await loop.run_in_executor(
                None, lambda: ctx.run(method, **arguments)
            )

        # 6. Convert to string / 转为字符串
        output = _to_string(result_value)

        return output

    async def validate(
        self,
        definition: ToolDefinition,
        arguments: dict[str, Any],
    ) -> bool:
        """Validate parameters / 校验参数"""
        for param in definition.parameters:
            if param.required and param.name not in arguments:
                return False
        return True


# --------------------------------------------------------------------------- #
# Internal: delegated wrappers / 内部：委托封装
# --------------------------------------------------------------------------- #


def _scan_toolkit_security(
    source: str,
    security_level: str | None = None,
) -> list[str]:
    return _scan_toolkit_security_impl(source, security_level)


def clear_toolkit_cache() -> None:
    """清空 Toolkit 模块缓存（测试或热更新时使用）/ Clear Toolkit module cache (used during testing or hot updates)."""
    _clear_toolkit_cache()


__all__ = ["ToolkitExecutor", "clear_toolkit_cache"]
