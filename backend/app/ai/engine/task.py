"""
Task Execution Engine / 任务执行引擎

Task-mode turns now reuse the same prepared execution and turn loop contract as
conversation sync turns; the task entrypoint only normalizes the one-shot user
payload before delegating to the canonical runtime path.
单次任务 turn 现在复用与 conversation sync 相同的 prepared execution /
turn loop contract；task 入口只负责归一化一次性用户输入，再委托给
canonical runtime 主路径。
"""

from dataclasses import replace
from typing import Any

from app.ai.types import ChatMessage
from app.core.i18n import _
from app.models.ai.agent import Agent

from .conversation import ConversationEngine
from .types import ExecutionRequest, ExecutionResult

# Default user message i18n key (called at runtime via _() to adapt to request language) / 默认 user 消息的 i18n key（运行时调用 _() 以适配请求语言）
_DEFAULT_TASK_USER_MSG_KEY = "tool.task.default_user_message"


class TaskEngine(ConversationEngine):
    """
    Task Execution Engine / 任务执行引擎

    Keeps the task entrypoint thin:
    保持 task 入口足够薄：
    1. Normalize one-shot request messages / 归一化单次请求消息
    2. Delegate to the canonical sync turn contract / 委托给 canonical sync turn contract
    """

    @staticmethod
    def _normalize_task_request(request: ExecutionRequest) -> ExecutionRequest:
        messages = list(request.messages or [])
        if not messages:
            messages = [ChatMessage(role="user", content=_(_DEFAULT_TASK_USER_MSG_KEY))]
        return replace(
            request,
            messages=messages,
        )

    async def execute(
        self,
        agent: Agent,
        request: ExecutionRequest,
        skill_result: Any | None = None,
    ) -> ExecutionResult:
        """Execute task mode via the shared sync turn contract / 通过统一 sync turn contract 执行 task 模式"""
        normalized_request = self._normalize_task_request(request)
        return await super().execute(
            agent=agent,
            request=normalized_request,
            skill_result=skill_result,
        )


__all__ = ["TaskEngine"]
