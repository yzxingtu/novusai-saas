"""
工具执行安全沙箱

提供工具执行的安全外壳：超时控制、输出截断、域名过滤、
EventBus 事件发布和 Hook 触发
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from app.ai.events.bus import get_event_bus
from app.ai.events.hooks import HookPoint, get_hook_registry
from app.ai.events.types import ToolCallCompleted, ToolCallFailed, ToolCallRequested
from app.ai.tools.security import (
    InputValidator,
    OutputSanitizer,
    ExecutionLimiter,
    ToolSecurityError,
)
from app.ai.tools.executors.base import BaseToolExecutor
from app.ai.tools.executors.builtin_executor import BuiltinToolExecutor
from app.ai.tools.executors.code_executor import CodeToolExecutor
from app.ai.tools.executors.database_executor import DatabaseToolExecutor
from app.ai.tools.executors.email_executor import EmailToolExecutor
from app.ai.tools.executors.http_executor import HttpToolExecutor
from app.ai.tools.registry import ToolRegistry, get_tool_registry
from app.ai.tools.types import ToolDefinition, ToolResult
from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.agent import ToolTypeEnum

logger = LogManager.get_logger("ai.tool.sandbox")


@dataclass
class SandboxConfig:
    """
    沙箱配置

    Attributes:
        timeout_seconds: 单次工具调用超时秒数
        max_output_size: 最大输出字符数
        allowed_domains: HTTP 工具允许访问的域名列表
        blocked_domains: HTTP 工具禁止访问的域名列表
    """

    timeout_seconds: int = 30
    max_output_size: int = 10000
    max_tool_calls_per_conversation: int = 20
    allowed_domains: list[str] = field(default_factory=list)
    blocked_domains: list[str] = field(default_factory=list)


class ToolSandbox:
    """
    工具执行安全沙箱

    编排工具执行的完整生命周期：
    1. 参数校验
    2. 触发 BEFORE_TOOL_CALL 钩子
    3. 超时控制下分发到对应 Executor
    4. 输出截断
    5. 触发 AFTER_TOOL_CALL 钩子
    6. 发布 EventBus 事件

    使用示例:
        sandbox = ToolSandbox(tenant_id=1, agent_id=42)
        result = await sandbox.execute("call_xxx", "weather_api", {"city": "Shanghai"})
    """

    def __init__(
        self,
        tenant_id: int,
        agent_id: int,
        config: SandboxConfig | None = None,
        registry: ToolRegistry | None = None,
    ):
        """
        Args:
            tenant_id: 租户 ID
            agent_id: 智能体 ID
            config: 沙箱配置
            registry: 工具注册表（默认使用全局单例）
        """
        self.tenant_id = tenant_id
        self.agent_id = agent_id
        self.config = config or SandboxConfig()
        self.registry = registry or get_tool_registry(tenant_id)

        # 初始化执行器
        self._executors: dict[str, BaseToolExecutor] = {}
        self._init_executors()

    def _init_executors(self) -> None:
        """初始化各类型执行器"""
        self._executors[ToolTypeEnum.HTTP.value] = HttpToolExecutor(
            allowed_domains=self.config.allowed_domains,
            blocked_domains=self.config.blocked_domains,
            max_response_size=self.config.max_output_size,
            timeout=self.config.timeout_seconds,
        )
        self._executors[ToolTypeEnum.BUILTIN.value] = BuiltinToolExecutor()
        self._executors[ToolTypeEnum.DATABASE.value] = DatabaseToolExecutor(
            timeout=self.config.timeout_seconds,
        )
        self._executors[ToolTypeEnum.EMAIL.value] = EmailToolExecutor(
            tenant_id=self.tenant_id,
        )
        self._executors[ToolTypeEnum.CODE.value] = CodeToolExecutor(
            timeout=self.config.timeout_seconds,
        )

    def get_executor(self, tool_type: str) -> BaseToolExecutor | None:
        """获取指定类型的执行器"""
        return self._executors.get(tool_type)

    def register_executor(self, tool_type: str, executor: BaseToolExecutor) -> None:
        """注册自定义执行器"""
        self._executors[tool_type] = executor

    async def execute(
        self,
        tool_call_id: str,
        name: str,
        arguments: dict[str, Any],
        definitions: list[ToolDefinition] | None = None,
        conversation_id: int = 0,
    ) -> ToolResult:
        """
        执行工具调用

        Args:
            tool_call_id: LLM 返回的 tool_call_id
            name: 工具名称
            arguments: LLM 传入的参数
            definitions: 当前对话的工具定义列表（可选，优先从中查找）
            conversation_id: 对话 ID（用于工具调用次数限制）

        Returns:
            ToolResult 执行结果
        """
        start = time.perf_counter()
        event_bus = get_event_bus()
        hook_registry = get_hook_registry()

        # 1. 查找工具定义
        definition = self._find_definition(name, definitions)
        if not definition:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=name,
                success=False,
                error=_("tool.error.not_found", name=name),
            )

        # 1.5 安全检查：输入参数校验 + 调用次数限制
        try:
            InputValidator.validate(definition.input_schema, arguments)
            if conversation_id > 0:
                await ExecutionLimiter.check_and_increment(
                    conversation_id,
                    max_calls=self.config.max_tool_calls_per_conversation,
                )
        except ToolSecurityError as sec_err:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=name,
                success=False,
                error=str(sec_err),
            )

        # 2. 发布请求事件
        await event_bus.publish(ToolCallRequested(
            tenant_id=self.tenant_id,
            conversation_id=conversation_id,
            tool_name=name,
            tool_call_id=tool_call_id,
            arguments=arguments,
        ))

        # 3. BEFORE_TOOL_CALL 钩子
        hook_context = await hook_registry.trigger(
            HookPoint.BEFORE_TOOL_CALL,
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            tool_name=name,
            arguments=arguments,
            definition=definition,
        )

        # 钩子可修改 arguments
        arguments = hook_context.get("arguments", arguments)

        # 钩子可阻止执行
        if hook_context.get("blocked"):
            reason = hook_context.get("block_reason", _("tool.error.blocked_by_hook"))
            return ToolResult(
                tool_call_id=tool_call_id,
                name=name,
                success=False,
                error=reason,
            )

        # 4. 获取执行器
        executor = self._executors.get(definition.tool_type)
        if not executor:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=name,
                success=False,
                error=_("tool.error.no_executor", tool_type=definition.tool_type),
            )

        # 5. 超时控制下执行（优先使用工具独立超时，否则回退到全局配置）
        tool_timeout = definition.timeout or self.config.timeout_seconds
        try:
            result = await asyncio.wait_for(
                executor.execute(definition, tool_call_id, arguments),
                timeout=tool_timeout,
            )
        except asyncio.TimeoutError:
            duration_ms = int((time.perf_counter() - start) * 1000)
            logger.warning(
                "Tool execution timed out: %s after %dms (timeout=%ds)",
                name,
                duration_ms,
                tool_timeout,
            )
            result = ToolResult(
                tool_call_id=tool_call_id,
                name=name,
                success=False,
                error=_("tool.error.execution_timeout", timeout=tool_timeout),
                duration_ms=duration_ms,
            )
        except Exception as exc:
            duration_ms = int((time.perf_counter() - start) * 1000)
            logger.error(
                "Tool execution error: %s: %s",
                name,
                str(exc),
                exc_info=True,
            )
            result = ToolResult(
                tool_call_id=tool_call_id,
                name=name,
                success=False,
                error=str(exc),
                duration_ms=duration_ms,
            )

        # 6. 输出脱敏 + 截断
        if result.success:
            result.output, _ = OutputSanitizer.sanitize(
                result.output,
                max_size=self.config.max_output_size,
            )

        # 7. AFTER_TOOL_CALL 钩子
        await hook_registry.trigger(
            HookPoint.AFTER_TOOL_CALL,
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            tool_name=name,
            result=result,
        )

        # 8. 发布结果事件
        if result.success:
            await event_bus.publish(ToolCallCompleted(
                tenant_id=self.tenant_id,
                conversation_id=conversation_id,
                tool_name=name,
                tool_call_id=tool_call_id,
                result=result.output,
                duration_ms=result.duration_ms,
            ))
        else:
            await event_bus.publish(ToolCallFailed(
                tenant_id=self.tenant_id,
                conversation_id=conversation_id,
                tool_name=name,
                tool_call_id=tool_call_id,
                error=result.error,
            ))

        return result

    async def execute_batch(
        self,
        tool_calls: list[dict[str, Any]],
        definitions: list[ToolDefinition] | None = None,
    ) -> list[ToolResult]:
        """
        批量执行工具调用（串行）

        Args:
            tool_calls: 工具调用列表，每个元素含 id/name/arguments
            definitions: 工具定义列表

        Returns:
            ToolResult 列表
        """
        results: list[ToolResult] = []
        for call in tool_calls:
            result = await self.execute(
                tool_call_id=call.get("id", ""),
                name=call.get("name", ""),
                arguments=call.get("arguments", {}),
                definitions=definitions,
            )
            results.append(result)
        return results

    def _find_definition(
        self,
        name: str,
        definitions: list[ToolDefinition] | None = None,
    ) -> ToolDefinition | None:
        """
        查找工具定义

        优先从传入的 definitions 列表查找，然后从注册表查找
        """
        if definitions:
            for d in definitions:
                if d.name == name:
                    return d

        return self.registry.get(name)


__all__ = [
    "SandboxConfig",
    "ToolSandbox",
]
