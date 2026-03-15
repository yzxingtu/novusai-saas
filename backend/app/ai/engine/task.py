"""
Task Execution Engine / 任务执行引擎

Single execution mode, injects input_variables into system_prompt, no conversation context.
单次执行模式，将 input_variables 注入到 system_prompt，无对话上下文。
"""

import time
from typing import Any

from app.ai.types import ChatMessage
from app.core.i18n import _
from app.core.logging import LogManager
from app.models.ai.agent import Agent

from .base import BaseEngine
from .types import ExecutionRequest, ExecutionResult

logger = LogManager.get_logger("ai.engine.task")

# Default user message i18n key (called at runtime via _() to adapt to request language) / 默认 user 消息的 i18n key（运行时调用 _() 以适配请求语言）
_DEFAULT_TASK_USER_MSG_KEY = "tool.task.default_user_message"


class TaskEngine(BaseEngine):
    """
    Task Execution Engine / 任务执行引擎

    Handles single task scenarios:
    处理单次任务场景：
    1. Inject input_variables into system_prompt placeholders / 将 input_variables 注入 system_prompt 占位符
    2. Build user message (from messages or default prompt) / 构建 user 消息
    3. Call LLM (with tool calling) / 调用 LLM（含 tool calling）
    4. Return result, no conversation context maintained / 返回结果，不维护对话上下文
    """

    async def execute(
        self,
        agent: Agent,
        request: ExecutionRequest,
        skill_result: Any | None = None,
    ) -> ExecutionResult:
        """Execute task mode / 执行任务模式"""
        start = time.perf_counter()

        try:
            # 1. Build messages / 构建消息
            messages: list[ChatMessage] = []

            # System message (inject variables) / system 消息（注入变量）
            system_msg = self._build_system_message(
                agent,
                input_variables=request.input_variables,
            )
            messages.append(system_msg)

            # User message / user 消息
            if request.messages:
                messages.extend(request.messages)
            else:
                messages.append(self._user_message(_(_DEFAULT_TASK_USER_MSG_KEY)))

            # 2. Resolve tools (use pre-resolved result or fallback to resolve_for_agent) / 解析工具
            if skill_result is None:
                from app.ai.skills.resolver import resolve_for_agent
                skill_result = await resolve_for_agent(
                    self.db, agent,
                    tenant_id=request.tenant_id,
                    user_role=getattr(request, "user_role", None),
                )
            tools = skill_result.tools if skill_result else []

            # 3. Call LLM / 调用 LLM
            response = await self._call_llm(
                agent=agent,
                messages=messages,
                tools=tools or None,
                tenant_id=request.tenant_id,
                user_id=request.user_id,
            )

            total_tokens = response.total_tokens or 0

            # 4. Tool call loop / 工具调用循环
            tool_results = []
            if response.tool_calls and tools:
                response, tool_results, total_tokens = await self._handle_tool_calls(
                    agent=agent,
                    messages=messages,
                    response=response,
                    tools=tools,
                    request=request,
                )

            # 5. Final output / 最终输出
            output = response.message.content or ""
            messages.append(ChatMessage(role="assistant", content=output))

            duration_ms = int((time.perf_counter() - start) * 1000)

            return ExecutionResult(
                success=True,
                output=output,
                messages=self._messages_to_dicts(messages),
                tool_results=tool_results,
                total_tokens=total_tokens,
                duration_ms=duration_ms,
            )

        except Exception as exc:
            duration_ms = int((time.perf_counter() - start) * 1000)
            logger.error(
                "Task execution failed: agent=%d error=%s",
                agent.id,
                str(exc),
                exc_info=True,
            )
            return ExecutionResult(
                success=False,
                error=str(exc),
                duration_ms=duration_ms,
            )


__all__ = ["TaskEngine"]
