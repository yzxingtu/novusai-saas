"""
Execution Engine Abstract Base Class / 执行引擎抽象基类

Provides shared infrastructure for all execution modes:
message building, tool parsing, tool call loop, event publishing.
提供所有执行模式共享的基础设施：消息构建、工具解析、工具调用循环、事件发布。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from app.ai.gateway import AIGateway
from app.ai.tools.sandbox import ToolSandbox
from app.models.ai.agent import Agent

from .base_event_support import BaseEventSupportMixin
from .base_execution_support import BaseEngineExecutionSupport
from .base_identity_support import log_user_type_for_call_log
from .base_prompt_support import BaseEnginePromptSupport
from .base_tool_loop_support import BaseToolLoopSupport
from .types import (
    ExecutionRequest,
    ExecutionResult,
)


class BaseEngine(
    BaseEnginePromptSupport,
    BaseEngineExecutionSupport,
    BaseToolLoopSupport,
    BaseEventSupportMixin,
    ABC,
):
    """
    Execution Engine Abstract Base Class / 执行引擎抽象基类

    Subclasses only need to implement execute(); base class provides:
    子类只需实现 execute() 方法，基类提供：
    - _build_messages: Build system + user messages / 构建 system + user 消息
    - _prepare_execution: Shared pre-logic (Skill resolve + RAG + tool optimization) / 共享前置逻辑
    - _handle_tool_calls: Tool calling loop / tool calling 循环
    - _call_llm: Call AIGateway / 调用 AIGateway
    """

    def __init__(
        self,
        db: AsyncSession,
        gateway: AIGateway,
        sandbox: ToolSandbox | None,
    ):
        """
        Args:
            db: Database session / 数据库会话
            gateway: AI Gateway / AI 网关
            sandbox: Tool sandbox / 工具沙箱
        """
        self.db = db
        self.gateway = gateway
        self.sandbox = sandbox

    @abstractmethod
    async def execute(self, agent: Agent, request: ExecutionRequest) -> ExecutionResult:
        """
        Execute request.
        执行请求。

        Args:
            agent: Agent model instance / 智能体模型实例
            request: Execution request / 执行请求

        Returns:
            ExecutionResult
        """


__all__ = ["BaseEngine", "log_user_type_for_call_log"]
