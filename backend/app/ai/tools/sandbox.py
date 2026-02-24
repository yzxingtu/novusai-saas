"""
工具执行安全沙箱

提供工具执行的安全外壳：超时控制、输出截断、域名过滤、
EventBus 事件发布和 Hook 触发
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

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
from app.ai.tools.executors.text_to_sql_executor import TextToSQLExecutor
from app.ai.tools.executors.crud_executor import (
    CreateRecordExecutor,
    DeleteRecordExecutor,
    UpdateRecordExecutor,
)
from app.ai.tools.executors.toolkit_executor import ToolkitExecutor
from app.ai.tools.types import ExecutionContext, ToolDefinition, ToolResult
from app.core.i18n import _
from app.core.logging import LogManager
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
        user_id: int | None = None,
        user_role: str = UserRoleEnum.TENANT_ADMIN.value,
        permissions: set[str] | None = None,
        gateway: AIGateway | None = None,
        db: AsyncSession | None = None,
        agent: Agent | None = None,
        toolkit_security_level: str = "normal",
        toolkit_memory_limit_mb: int = 256,
    ):
        """
        Args:
            tenant_id: 租户 ID
            agent_id: 智能体 ID
            config: 沙箱配置
            user_id: 当前操作用户 ID（可选，传递给 ExecutionContext）
            user_role: 用户角色（platform_admin / tenant_admin / tenant_user）
            permissions: 用户 RBAC 权限码集合
            gateway: AI 网关（可选，供 TextToSQLExecutor 使用）
            db: 数据库会话（可选，供 TextToSQLExecutor 使用）
            agent: 智能体模型实例（可选，供 TextToSQLExecutor 使用）
            toolkit_security_level: Toolkit 安全等级 (strict/normal/permissive)
            toolkit_memory_limit_mb: Toolkit 子进程内存限制 (MB)
        """
        self.tenant_id = tenant_id
        self.agent_id = agent_id
        self.user_id = user_id
        self.user_role = user_role
        self.permissions = permissions or set()
        self.consented_actions: set[str] = set()
        self.config = config or SandboxConfig()
        self._gateway = gateway
        self._db = db
        self._agent = agent
        self._toolkit_security_level = toolkit_security_level
        self._toolkit_memory_limit_mb = toolkit_memory_limit_mb

        # 初始化执行器
        self._executors: dict[str, BaseToolExecutor] = {}
        self._init_executors()

    def _init_executors(self) -> None:
        """初始化各类型执行器"""
        # Toolkit 执行器（新架构核心）
        self._executors[ToolTypeEnum.TOOLKIT.value] = ToolkitExecutor(
            timeout=self.config.timeout_seconds,
            max_output_size=self.config.max_output_size,
            security_level=self._toolkit_security_level,
            memory_limit_mb=self._toolkit_memory_limit_mb,
        )
        self._executors[ToolTypeEnum.BUILTIN.value] = BuiltinToolExecutor()
        # Text-to-SQL 执行器（需要 AIGateway 注入）
        if self._gateway and self._db:
            self._executors[ToolTypeEnum.TEXT_TO_SQL.value] = TextToSQLExecutor(
                gateway=self._gateway,
                db=self._db,
                agent=self._agent,
            )
        # 通用 CRUD 执行器
        self._executors[ToolTypeEnum.DATA_CREATE.value] = CreateRecordExecutor()
        self._executors[ToolTypeEnum.DATA_UPDATE.value] = UpdateRecordExecutor()
        self._executors[ToolTypeEnum.DATA_DELETE.value] = DeleteRecordExecutor()
        # HTTP/Webhook 执行器
        from app.ai.tools.executors.http_executor import HttpToolExecutor
        self._executors[ToolTypeEnum.HTTP.value] = HttpToolExecutor()
        # 邮件执行器
        from app.ai.tools.executors.email_executor import EmailToolExecutor
        self._executors[ToolTypeEnum.EMAIL.value] = EmailToolExecutor()
        # 代码执行器
        from app.ai.tools.executors.code_execution_executor import CodeExecutionExecutor
        self._executors[ToolTypeEnum.CODE_EXECUTION.value] = CodeExecutionExecutor()

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

        # 4. 获取执行器（内置 → 插件 fallback）
        executor = self._executors.get(definition.tool_type)
        if not executor and definition.source_plugin:
            # 按插件名查询插件注册的执行器
            try:
                from app.plugins.registry import ExtensionRegistry
                plugin_executor_factory = ExtensionRegistry.get_instance().get_plugin_executor(definition.source_plugin)
                if plugin_executor_factory:
                    executor = plugin_executor_factory() if callable(plugin_executor_factory) else plugin_executor_factory
            except Exception as pe:
                logger.warning("Plugin executor lookup failed for %s: %s", definition.source_plugin, pe)
        if not executor:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=name,
                success=False,
                error=_("tool.error.no_executor", tool_type=definition.tool_type),
            )

        # 5. 构建 ExecutionContext（含 RBAC 权限信息 + 会话授权）
        context = ExecutionContext(
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            user_id=self.user_id,
            user_role=self.user_role,
            permissions=self.permissions,
            db=self._db,
            consented_actions=self.consented_actions,
            skill_id=definition.source_skill_id,
        )

        # 5.5 执行器级参数校验
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
                "Executor validate() error for %s: %s",
                name, str(val_exc),
            )
            return ToolResult(
                tool_call_id=tool_call_id,
                name=name,
                success=False,
                error=str(val_exc),
            )

        # 6. 超时控制下执行（优先使用工具独立超时，否则回退到全局配置）
        tool_timeout = definition.timeout or self.config.timeout_seconds
        try:
            result = await asyncio.wait_for(
                executor.execute(definition, tool_call_id, arguments, context=context),
                timeout=tool_timeout,
            )
            # Ensure result.name is always set (some executors omit it in error paths)
            if not result.name:
                result.name = name
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

        # 7. 输出脱敏 + 截断
        if result.success:
            result.output, _ = OutputSanitizer.sanitize(
                result.output,
                max_size=self.config.max_output_size,
            )

        # 9. AFTER_TOOL_CALL 钩子
        await hook_registry.trigger(
            HookPoint.AFTER_TOOL_CALL,
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            tool_name=name,
            result=result,
        )

        # 10. 发布结果事件
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

        # 11. 记录技能调用日志（fire-and-forget，不阻塞返回）
        try:
            await self._log_skill_call(
                definition=definition,
                result=result,
            )
        except Exception as log_exc:
            logger.warning("Failed to log skill call: %s", str(log_exc))

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

    async def _log_skill_call(
        self,
        definition: ToolDefinition,
        result: ToolResult,
    ) -> None:
        """记录技能调用日志到 skill_call_logs 表"""
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
        # flush 但不 commit — 由外层事务统一提交
        await self._db.flush()

    def _find_definition(
        self,
        name: str,
        definitions: list[ToolDefinition] | None = None,
    ) -> ToolDefinition | None:
        """
        查找工具定义

        从 SkillResolver 传入的 definitions 列表中查找
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
