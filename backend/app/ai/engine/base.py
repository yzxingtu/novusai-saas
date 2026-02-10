"""
执行引擎抽象基类

提供所有执行模式共享的基础设施：消息构建、工具解析、工具调用循环、事件发布
"""

from __future__ import annotations

import dataclasses
import json
from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING, Any

from jinja2 import BaseLoader, Environment, TemplateSyntaxError, UndefinedError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.events.bus import get_event_bus
from app.ai.events.types import (
    ExecutionCompleted,
    ExecutionFailed,
    ExecutionStarted,
    MessageAdded,
)

if TYPE_CHECKING:
    from app.ai.gateway import AIGateway
from app.ai.tools.registry import ToolRegistry, get_tool_registry
from app.ai.tools.sandbox import ToolSandbox
from app.ai.tools.types import ToolDefinition, ToolResult
from app.ai.types import ChatMessage, ChatResponse
from app.core.i18n import _
from app.core.logging import LogManager
from app.models.ai.agent import Agent

from .types import ExecutionRequest, ExecutionResult

logger = LogManager.get_logger("ai.engine")

# 工具调用最大循环次数（防止无限循环）
MAX_TOOL_CALL_ROUNDS = 10

# Jinja2 环境（共享实例，undefined 渲染为空字符串而非报错）
_jinja_env = Environment(loader=BaseLoader(), keep_trailing_newline=True)


class BaseEngine(ABC):
    """
    执行引擎抽象基类

    子类只需实现 execute() 方法，基类提供：
    - _build_messages: 构建 system + user 消息
    - _resolve_tools: 从 agent.tool_bindings 解析工具定义
    - _handle_tool_calls: tool calling 循环
    - _call_llm: 调用 AIGateway
    """

    def __init__(
        self,
        db: AsyncSession,
        gateway: AIGateway,
        sandbox: ToolSandbox,
    ):
        """
        Args:
            db: 数据库会话
            gateway: AI 网关
            sandbox: 工具沙箱
        """
        self.db = db
        self.gateway = gateway
        self.sandbox = sandbox

    @abstractmethod
    async def execute(self, agent: Agent, request: ExecutionRequest) -> ExecutionResult:
        """
        执行请求

        Args:
            agent: 智能体模型实例
            request: 执行请求

        Returns:
            ExecutionResult
        """

    # ========================================
    # 消息构建
    # ========================================

    def _build_system_message(
        self,
        agent: Agent,
        input_variables: dict[str, Any] | None = None,
    ) -> ChatMessage:
        """
        构建 system 消息

        使用 Jinja2 渲染 system_prompt，支持内置变量和自定义变量。
        内置变量：current_date, current_time, agent_name
        自定义变量：来自 input_variables 参数

        Args:
            agent: 智能体
            input_variables: 输入变量
        """
        prompt = agent.system_prompt or ""

        if not prompt:
            return ChatMessage(role="system", content=prompt)

        # 构建模板变量（内置 + 自定义）
        now = datetime.now()
        variables: dict[str, Any] = {
            "current_date": now.strftime("%Y-%m-%d"),
            "current_time": now.strftime("%H:%M:%S"),
            "agent_name": agent.name or "",
        }
        if input_variables:
            variables.update(input_variables)

        try:
            template = _jinja_env.from_string(prompt)
            prompt = template.render(**variables)
        except TemplateSyntaxError as exc:
            logger.warning(
                _("agent.log.template_syntax_error"),
                agent_id=agent.id,
                error=str(exc),
            )
        except UndefinedError as exc:
            logger.warning(
                _("agent.log.undefined_variable"),
                agent_id=agent.id,
                error=str(exc),
            )
        except Exception as exc:
            logger.warning(
                _("agent.log.template_render_error"),
                agent_id=agent.id,
                error=str(exc),
            )

        return ChatMessage(role="system", content=prompt)

    @staticmethod
    def _user_message(content: str) -> ChatMessage:
        """构建 user 消息"""
        return ChatMessage(role="user", content=content)

    # ========================================
    # 工具解析
    # ========================================

    def _resolve_tools(
        self,
        agent: Agent,
        tenant_id: int | None = None,
    ) -> list[ToolDefinition]:
        """
        解析智能体绑定的工具

        Args:
            agent: 智能体
            tenant_id: 租户 ID（用于获取租户隔离的 ToolRegistry）
        """
        registry = get_tool_registry(tenant_id)
        return registry.resolve_agent_tools(agent.tool_bindings)

    # ========================================
    # LLM 调用
    # ========================================

    async def _call_llm(
        self,
        agent: Agent,
        messages: list[ChatMessage],
        tools: list[ToolDefinition] | None = None,
        tenant_id: int | None = None,
        user_id: int | None = None,
    ) -> ChatResponse:
        """
        调用 LLM

        Args:
            agent: 智能体（含模型配置）
            messages: 消息列表
            tools: 工具定义列表
            tenant_id: 租户 ID
            user_id: 用户 ID
        """
        # 构建 OpenAI tools 参数
        openai_tools = None
        if tools:
            openai_tools = ToolRegistry.to_openai_tools(tools)

        # 获取模型信息
        model_obj = agent.model
        provider_code = model_obj.provider.code if model_obj and model_obj.provider else ""
        model_code = model_obj.code if model_obj else ""

        response = await self.gateway.chat(
            provider_code=provider_code,
            messages=messages,
            model=model_code,
            temperature=agent.temperature,
            max_tokens=agent.max_tokens,
            top_p=agent.top_p or 1.0,
            tools=openai_tools,
            tenant_id=tenant_id,
            user_id=user_id,
        )

        return response

    # ========================================
    # 工具调用循环
    # ========================================

    async def _handle_tool_calls(
        self,
        agent: Agent,
        messages: list[ChatMessage],
        response: ChatResponse,
        tools: list[ToolDefinition],
        request: ExecutionRequest,
    ) -> tuple[ChatResponse, list[ToolResult], int]:
        """
        处理工具调用循环

        当 LLM 返回 tool_calls 时，执行工具并将结果追加到消息中，
        然后再次调用 LLM，直到 LLM 不再返回 tool_calls 或达到最大轮次。

        Args:
            agent: 智能体
            messages: 当前消息列表（会被修改）
            response: LLM 响应
            tools: 工具定义列表
            request: 原始请求

        Returns:
            (final_response, all_tool_results, total_tokens)
        """
        all_tool_results: list[ToolResult] = []
        total_tokens = response.total_tokens or 0
        current_response = response

        for _round in range(MAX_TOOL_CALL_ROUNDS):
            tool_calls = current_response.tool_calls
            if not tool_calls:
                break

            # 追加 assistant 消息（含 tool_calls）
            assistant_msg = ChatMessage(
                role="assistant",
                content=current_response.message.content or "",
                tool_calls=tool_calls,
            )
            messages.append(assistant_msg)

            # 执行每个工具调用
            for tc in tool_calls:
                tc_id = tc.get("id", "")
                func = tc.get("function", {})
                func_name = func.get("name", "")
                raw_args = func.get("arguments", "{}")

                # 解析参数
                try:
                    arguments = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except json.JSONDecodeError:
                    arguments = {}

                # 通过沙箱执行
                result = await self.sandbox.execute(
                    tool_call_id=tc_id,
                    name=func_name,
                    arguments=arguments,
                    definitions=tools,
                    conversation_id=request.conversation_id or 0,
                )
                all_tool_results.append(result)

                # 追加 tool 消息
                messages.append(ChatMessage(
                    role="tool",
                    content=result.output if result.success else _("tool.error.prefix", error=result.error),
                    tool_call_id=tc_id,
                ))

            # 再次调用 LLM
            current_response = await self._call_llm(
                agent=agent,
                messages=messages,
                tools=tools,
                tenant_id=request.tenant_id,
                user_id=request.user_id,
            )
            total_tokens += current_response.total_tokens or 0

        return current_response, all_tool_results, total_tokens

    # ========================================
    # 事件发布
    # ========================================

    @staticmethod
    async def _publish_execution_started(request: ExecutionRequest, agent: Agent) -> None:
        """发布执行开始事件"""
        await get_event_bus().publish(ExecutionStarted(
            tenant_id=request.tenant_id,
            agent_id=agent.id,
            execution_mode=request.execution_mode,
        ))

    @staticmethod
    async def _publish_execution_completed(
        request: ExecutionRequest,
        agent: Agent,
        result: ExecutionResult,
    ) -> None:
        """发布执行完成事件"""
        await get_event_bus().publish(ExecutionCompleted(
            tenant_id=request.tenant_id,
            agent_id=agent.id,
            total_tokens=result.total_tokens,
            duration_ms=result.duration_ms,
        ))

    @staticmethod
    async def _publish_execution_failed(
        request: ExecutionRequest,
        agent: Agent,
        error: str,
        error_type: str = "",
    ) -> None:
        """发布执行失败事件"""
        await get_event_bus().publish(ExecutionFailed(
            tenant_id=request.tenant_id,
            agent_id=agent.id,
            error=error,
            error_type=error_type,
        ))

    # ========================================
    # 工具方法
    # ========================================

    @staticmethod
    def _messages_to_dicts(messages: list[ChatMessage]) -> list[dict[str, Any]]:
        """将 ChatMessage 列表转为 dict 列表"""
        return [dataclasses.asdict(msg) for msg in messages]


__all__ = ["BaseEngine"]
