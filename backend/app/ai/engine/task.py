"""
任务执行引擎

单次执行模式，将 input_variables 注入到 system_prompt，无对话上下文
"""

import time

from app.ai.types import ChatMessage
from app.core.i18n import _
from app.core.logging import LogManager
from app.models.ai.agent import Agent

from .base import BaseEngine
from .types import ExecutionRequest, ExecutionResult

logger = LogManager.get_logger("ai.engine.task")

# 默认 user 消息的 i18n key（运行时调用 _() 以适配请求语言）
_DEFAULT_TASK_USER_MSG_KEY = "tool.task.default_user_message"


class TaskEngine(BaseEngine):
    """
    任务执行引擎

    处理单次任务场景：
    1. 将 input_variables 注入 system_prompt 占位符
    2. 构建 user 消息（来自 messages 或默认提示）
    3. 调用 LLM（含 tool calling）
    4. 返回结果，不维护对话上下文
    """

    async def execute(self, agent: Agent, request: ExecutionRequest) -> ExecutionResult:
        """执行任务模式"""
        start = time.perf_counter()

        try:
            # 1. 构建消息
            messages: list[ChatMessage] = []

            # system 消息（注入变量）
            system_msg = self._build_system_message(
                agent,
                input_variables=request.input_variables,
            )
            messages.append(system_msg)

            # user 消息
            if request.messages:
                messages.extend(request.messages)
            else:
                messages.append(self._user_message(_(_DEFAULT_TASK_USER_MSG_KEY)))

            # 2. 解析工具（按租户隔离）
            tools = self._resolve_tools(agent, tenant_id=request.tenant_id)

            # 3. 调用 LLM
            response = await self._call_llm(
                agent=agent,
                messages=messages,
                tools=tools or None,
                tenant_id=request.tenant_id,
                user_id=request.user_id,
            )

            total_tokens = response.total_tokens or 0

            # 4. 工具调用循环
            tool_results = []
            if response.tool_calls and tools:
                response, tool_results, total_tokens = await self._handle_tool_calls(
                    agent=agent,
                    messages=messages,
                    response=response,
                    tools=tools,
                    request=request,
                )

            # 5. 最终输出
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
