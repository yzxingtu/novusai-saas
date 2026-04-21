"""
Tool Execution Security Sandbox. / 工具执行安全沙箱。

Provides a security shell for tool execution: timeout control, output truncation,
domain filtering, EventBus event publishing and Hook triggering.
提供工具执行的安全外壳：超时控制、输出截断、域名过滤、
EventBus 事件发布和 Hook 触发。
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from app.ai.events.bus import get_event_bus
from app.ai.events.hooks import HookPoint, get_hook_registry
from app.ai.events.types import ToolCallCompleted, ToolCallFailed, ToolCallRequested
from app.ai.tools.executors.base import BaseToolExecutor
from app.ai.tools.executors.builtin_executor import BuiltinToolExecutor
from app.ai.tools.executors.toolkit_executor import ToolkitExecutor
from app.ai.tools.security import (
    ExecutionLimiter,
    InputValidator,
    OutputSanitizer,
    ToolSecurityError,
)
from app.ai.tools.types import ExecutionContext, ToolDefinition, ToolResult
from app.core.i18n import _
from app.core.logging import LogManager
from app.core.response import build_public_error_text
from app.enums.agent import ToolTypeEnum
from app.enums.common import UserRoleEnum

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.ai.gateway import AIGateway
    from app.models.ai.agent import Agent

logger = LogManager.get_logger("ai.tool.sandbox")


@dataclass
class SandboxConfig:
    """
    Sandbox Configuration / 沙箱配置

    Attributes:
        timeout_seconds: Single tool call timeout in seconds / 单次工具调用超时秒数
        max_output_size: Maximum output character count / 最大输出字符数
        allowed_domains: Allowed domain list for HTTP tools / HTTP 工具允许访问的域名列表
        blocked_domains: Blocked domain list for HTTP tools / HTTP 工具禁止访问的域名列表
    """

    timeout_seconds: int = 30
    max_output_size: int = 10000
    max_tool_calls_per_conversation: int = 20
    allowed_domains: list[str] = field(default_factory=list)
    blocked_domains: list[str] = field(default_factory=list)


class ToolSandbox:
    """
    Tool Execution Security Sandbox / 工具执行安全沙箱

    Orchestrates the complete lifecycle of tool execution:
    编排工具执行的完整生命周期：
    1. Parameter validation / 参数校验
    2. Trigger BEFORE_TOOL_CALL hook / 触发 BEFORE_TOOL_CALL 钩子
    3. Dispatch to corresponding Executor under timeout control / 超时控制下分发
    4. Output truncation / 输出截断
    5. Trigger AFTER_TOOL_CALL hook / 触发 AFTER_TOOL_CALL 钩子
    6. Publish EventBus events / 发布 EventBus 事件

    Usage / 使用示例:
        sandbox = ToolSandbox(tenant_id=1, agent_id=42)
        result = await sandbox.execute("call_xxx", "weather_api", {"city": "Shanghai"})
    """

    def __init__(
        self,
        tenant_id: int,
        agent_id: int,
        config: SandboxConfig | None = None,
        user_id: int | None = None,
        user_role: str = UserRoleEnum.TENANT_ADMIN.value,
        permissions: set[str] | None = None,
        gateway: AIGateway | None = None,
        db: AsyncSession | None = None,
        agent: Agent | None = None,
        toolkit_security_level: str = "normal",
        toolkit_memory_limit_mb: int = 256,
        input_variables: dict[str, Any] | None = None,
        page_session_id: str | None = None,
        conversation_id: int | None = None,
        trust_policy_ref: dict[str, Any] | None = None,
        interaction_mode: str = "trusted_auto",
    ):
        """
        Args:
            tenant_id: Tenant ID / 企业 ID
            agent_id: Agent ID / 智能体 ID
            config: Sandbox configuration / 沙箱配置
            user_id: Current user ID (optional, passed to ExecutionContext) / 当前操作用户 ID
            user_role: User role (platform_admin / tenant_admin / tenant_user) / 用户角色
            permissions: User RBAC permission code set / 用户 RBAC 权限码集合
            gateway: AI gateway (reserved for executor integrations) / AI 网关（预留给执行器集成）
            db: Database session (for DB-backed executors) / 数据库会话（供数据库相关执行器使用）
            agent: Agent model instance (optional executor context) / 智能体模型实例（执行器可选上下文）
            toolkit_security_level: Toolkit security level (strict/normal/permissive) / 安全等级
            toolkit_memory_limit_mb: Toolkit subprocess memory limit (MB) / 子进程内存限制
            input_variables: Runtime variables (page context, etc.) / 运行时变量
            page_session_id: Frontend page session ID (for PageOperationExecutor) / 页面会话 ID
            conversation_id: Conversation ID for audit correlation / 会话 ID（用于审计串联）
        """
        self.tenant_id = tenant_id
        self.agent_id = agent_id
        self.user_id = user_id
        self.user_role = user_role
        self.permissions = permissions or set()
        self.consented_actions: set[str] = set()
        self.input_variables: dict[str, Any] = input_variables or {}
        self.config = config or SandboxConfig()
        self._gateway = gateway
        self._db = db
        self._agent = agent
        self._toolkit_security_level = toolkit_security_level
        self._toolkit_memory_limit_mb = toolkit_memory_limit_mb
        self._page_session_id = page_session_id
        self._conversation_id = conversation_id
        self._runtime_model_info: dict[str, Any] | None = None
        self.trust_policy_ref = trust_policy_ref
        self.interaction_mode = interaction_mode
        # Bumped when a non-readonly page tool succeeds; ToolCallProcessor folds into readonly cache keys.
        # 非只读页面工具成功执行后递增，供 ToolCallProcessor 只读快照缓存键区分同页状态。
        self._page_readonly_cache_epoch: int = 0

        # Initialize executors / 初始化执行器
        self._executors: dict[str, BaseToolExecutor] = {}
        self._named_executors: dict[str, BaseToolExecutor] = {}
        self._init_executors()

    def _init_executors(self) -> None:
        """Initialize executors for each type / 初始化各类型执行器"""
        # Toolkit executor (new architecture core) / Toolkit 执行器
        self._executors[ToolTypeEnum.TOOLKIT.value] = ToolkitExecutor(
            timeout=self.config.timeout_seconds,
            max_output_size=self.config.max_output_size,
            security_level=self._toolkit_security_level,
            memory_limit_mb=self._toolkit_memory_limit_mb,
        )
        self._executors[ToolTypeEnum.BUILTIN.value] = BuiltinToolExecutor()
        # HTTP/Webhook executor / HTTP/Webhook 执行器
        from app.ai.tools.executors.http_executor import HttpToolExecutor

        self._executors[ToolTypeEnum.HTTP.value] = HttpToolExecutor()
        # Email executor / 邮件执行器
        from app.ai.tools.executors.email_executor import EmailToolExecutor

        self._executors[ToolTypeEnum.EMAIL.value] = EmailToolExecutor()
        # Code executor / 代码执行器
        from app.ai.tools.executors.code_execution_executor import CodeExecutionExecutor

        self._executors[ToolTypeEnum.CODE_EXECUTION.value] = CodeExecutionExecutor()
        # Page runtime executor (matched by tool name, prioritized over type-based lookup) / 页面 runtime 执行器
        from app.ai.tools.executors.ui_snapshot_executor import UISnapshotExecutor
        from app.ai.tools.page_runtime.executor import PageRuntimeToolExecutor
        from app.ai.tools.page_runtime.live_bridge import SocketIOPageRuntimeBridge

        page_runtime_executor = PageRuntimeToolExecutor(SocketIOPageRuntimeBridge())
        self._named_executors["ui_get_snapshot"] = UISnapshotExecutor()
        for tool_name in {
            "ui_read_region",
            "ui_read_table",
            "ui_list_interactables",
            "ui_click",
            "ui_open_surface",
            "ui_get_form_state",
            "ui_set_field",
            "ui_fill_form",
            "ui_submit_form",
        }:
            self._named_executors[tool_name] = page_runtime_executor

    def get_executor(self, tool_type: str) -> BaseToolExecutor | None:
        """Get executor for specified type / 获取指定类型的执行器"""
        return self._executors.get(tool_type)

    def register_executor(self, tool_type: str, executor: BaseToolExecutor) -> None:
        """Register custom executor / 注册自定义执行器"""
        self._executors[tool_type] = executor

    def set_runtime_model_info(self, runtime_model_info: dict[str, Any] | None) -> None:
        """
        Set runtime provider/model info for subsequent tool executions.
        为后续工具执行设置运行时 provider/model 信息。
        """
        if isinstance(runtime_model_info, dict):
            self._runtime_model_info = dict(runtime_model_info)
            return
        self._runtime_model_info = None

    async def execute(
        self,
        tool_call_id: str,
        name: str,
        arguments: dict[str, Any],
        definitions: list[ToolDefinition] | None = None,
        conversation_id: int = 0,
    ) -> ToolResult:
        """
        Execute tool call / 执行工具调用

        Args:
            tool_call_id: tool_call_id returned by LLM / LLM 返回的 tool_call_id
            name: Tool name / 工具名称
            arguments: Arguments passed by LLM / LLM 传入的参数
            definitions: Tool definition list for current conversation (optional) / 工具定义列表
            conversation_id: Conversation ID (for tool call count limiting) / 对话 ID

        Returns:
            ToolResult execution result / 执行结果
        """
        start = time.perf_counter()
        event_bus = get_event_bus()
        hook_registry = get_hook_registry()

        # 1. Find tool definition / 查找工具定义
        definition = self._find_definition(name, definitions)

        if not definition:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=name,
                success=False,
                error=_("tool.error.not_found", name=name),
            )

        # 1.5 Security check: input validation + call count limit / 安全检查
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
                error=build_public_error_text(message=str(sec_err)),
            )

        # 2. Publish request event / 发布请求事件
        await event_bus.publish(
            ToolCallRequested(
                tenant_id=self.tenant_id,
                conversation_id=conversation_id,
                tool_name=name,
                tool_call_id=tool_call_id,
                arguments=arguments,
            )
        )

        # 3. BEFORE_TOOL_CALL hook / BEFORE_TOOL_CALL 钩子
        hook_context = await hook_registry.trigger(
            HookPoint.BEFORE_TOOL_CALL,
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            tool_name=name,
            arguments=arguments,
            definition=definition,
        )

        # Hook can modify arguments / 钩子可修改 arguments
        arguments = hook_context.get("arguments", arguments)

        # Hook can block execution / 钩子可阻止执行
        if hook_context.get("blocked"):
            reason = hook_context.get("block_reason", _("tool.error.blocked_by_hook"))
            return ToolResult(
                tool_call_id=tool_call_id,
                name=name,
                success=False,
                error=reason,
            )

        # 4. Get executor (plugin priority → builtin fallback) / 获取执行器
        executor = None
        if definition.source_plugin:
            try:
                from app.plugins.registry import ExtensionRegistry

                executor = ExtensionRegistry.get_instance().get_plugin_executor(
                    definition.source_plugin
                )
            except Exception as pe:
                logger.warning(
                    "Plugin executor lookup failed for {}: {}",
                    definition.source_plugin,
                    pe,
                )
        if not executor:
            executor = self._named_executors.get(name) or self._executors.get(
                definition.tool_type
            )
        if not executor:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=name,
                success=False,
                error=_("tool.error.no_executor", tool_type=definition.tool_type),
            )

        # 5. Build ExecutionContext (with RBAC permissions + session consent) / 构建执行上下文
        context = ExecutionContext(
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            user_id=self.user_id,
            user_role=self.user_role,
            permissions=self.permissions,
            db=self._db,
            consented_actions=self.consented_actions,
            trust_policy_ref=self.trust_policy_ref,
            skill_id=definition.source_skill_id,
            variables=self.input_variables,
            page_session_id=self._page_session_id,
            conversation_id=self._conversation_id,
            interaction_mode=self.interaction_mode,
            runtime_provider_id=(
                self._runtime_model_info.get("provider_id")
                if isinstance(self._runtime_model_info, dict)
                else None
            ),
            runtime_provider_name=(
                str(self._runtime_model_info.get("provider_name") or "")
                if isinstance(self._runtime_model_info, dict)
                and self._runtime_model_info.get("provider_name") is not None
                else None
            ),
            runtime_model_id=(
                self._runtime_model_info.get("model_id")
                if isinstance(self._runtime_model_info, dict)
                else None
            ),
            runtime_model_name=(
                str(self._runtime_model_info.get("model_name") or "")
                if isinstance(self._runtime_model_info, dict)
                and self._runtime_model_info.get("model_name") is not None
                else None
            ),
            runtime_model_code=(
                str(self._runtime_model_info.get("model_code") or "")
                if isinstance(self._runtime_model_info, dict)
                and self._runtime_model_info.get("model_code") is not None
                else None
            ),
        )

        # 5.5 Executor-level parameter validation / 执行器级参数校验
        try:
            valid = await executor.validate(definition, arguments)
            if not valid:
                return ToolResult(
                    tool_call_id=tool_call_id,
                    name=name,
                    success=False,
                    error=_("tool.error.validation_failed", name=name),
                )
        except Exception as val_exc:
            logger.warning(
                "Executor validate() error for {}: {}",
                name,
                str(val_exc),
            )
            return ToolResult(
                tool_call_id=tool_call_id,
                name=name,
                success=False,
                error=build_public_error_text(
                    message=_("tool.error.validation_failed", name=name),
                    exc=val_exc,
                ),
            )

        # 6. Execute under timeout control (prefer tool-specific timeout, fallback to global) / 超时控制下执行
        tool_timeout = definition.timeout or self.config.timeout_seconds
        context.tool_timeout_seconds = float(tool_timeout)
        context.tool_started_monotonic = start
        context.tool_deadline_monotonic = start + float(tool_timeout)
        try:
            result = await asyncio.wait_for(
                executor.execute(definition, tool_call_id, arguments, context=context),
                timeout=tool_timeout,
            )
            # Ensure result.name is set (some executors omit on error paths) / 确保 result.name 有值（部分执行器错误路径未设）
            if not result.name:
                result.name = name
            # Persist executor-mutated page session identity (navigation / reconnect) for subsequent tools + cache keys.
            # 将执行器写回的页面会话身份持久化到沙箱，供后续工具与只读缓存键使用。
            try:
                if context.page_session_id is not None:
                    self._page_session_id = context.page_session_id
                    if isinstance(self.input_variables, dict):
                        self.input_variables["page_session_id"] = (
                            context.page_session_id
                        )
            except Exception:
                pass
        except asyncio.TimeoutError:
            duration_ms = int((time.perf_counter() - start) * 1000)
            logger.warning(
                "Tool execution timed out: {} after {}ms (timeout={}s)",
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
                "Tool execution error: {}: {}",
                name,
                str(exc),
                exc_info=True,
            )
            result = ToolResult(
                tool_call_id=tool_call_id,
                name=name,
                success=False,
                error=build_public_error_text(
                    message=_("common.server_error"),
                    exc=exc,
                ),
                duration_ms=duration_ms,
            )

        # 7. Output sanitization + truncation / 输出脱敏 + 截断
        if result.success:
            result.output = OutputSanitizer.sanitize(
                result.output,
                max_size=self.config.max_output_size,
            )[0]

        # 9. AFTER_TOOL_CALL hook / AFTER_TOOL_CALL 钩子
        await hook_registry.trigger(
            HookPoint.AFTER_TOOL_CALL,
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            tool_name=name,
            result=result,
        )

        # 10. Publish result event / 发布结果事件
        if result.success:
            await event_bus.publish(
                ToolCallCompleted(
                    tenant_id=self.tenant_id,
                    conversation_id=conversation_id,
                    tool_name=name,
                    tool_call_id=tool_call_id,
                    result=result.output,
                    duration_ms=result.duration_ms,
                )
            )
        else:
            await event_bus.publish(
                ToolCallFailed(
                    tenant_id=self.tenant_id,
                    conversation_id=conversation_id,
                    tool_name=name,
                    tool_call_id=tool_call_id,
                    error=result.error,
                )
            )

        # 11. Log skill call (fire-and-forget, non-blocking) / 记录技能调用日志
        try:
            await self._log_skill_call(
                definition=definition,
                result=result,
            )
        except Exception as log_exc:
            logger.warning("Failed to log skill call: {}", str(log_exc))

        return result

    async def execute_batch(
        self,
        tool_calls: list[dict[str, Any]],
        definitions: list[ToolDefinition] | None = None,
    ) -> list[ToolResult]:
        """
        Batch execute tool calls (serial) / 批量执行工具调用（串行）

        Args:
            tool_calls: Tool call list, each containing id/name/arguments / 工具调用列表
            definitions: Tool definition list / 工具定义列表

        Returns:
            ToolResult list / 结果列表
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

    async def _log_skill_call(
        self,
        definition: ToolDefinition,
        result: ToolResult,
    ) -> None:
        """Log skill call to skill_call_logs table / 记录技能调用日志到 skill_call_logs 表"""
        if not self._db:
            return

        from app.models.ai.skill_call_log import SkillCallLog

        log = SkillCallLog(
            tenant_id=self.tenant_id,
            skill_id=definition.source_skill_id,
            agent_id=self.agent_id,
            tool_name=definition.name,
            tool_type=definition.tool_type,
            status="success" if result.success else "failed",
            duration_ms=result.duration_ms or 0,
            error_message=result.error if not result.success else None,
        )
        self._db.add(log)
        # flush without commit — committed by outer transaction / flush 但不 commit
        await self._db.flush()

    def _find_definition(
        self,
        name: str,
        definitions: list[ToolDefinition] | None = None,
    ) -> ToolDefinition | None:
        """
        Find tool definition / 查找工具定义

        Searches from the definitions list passed by SkillResolver.
        从 SkillResolver 传入的 definitions 列表中查找。
        """
        if definitions:
            for d in definitions:
                if d.name == name:
                    return d

        return None


__all__ = [
    "SandboxConfig",
    "ToolSandbox",
]
