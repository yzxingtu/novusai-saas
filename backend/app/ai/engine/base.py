"""
Execution Engine Abstract Base Class / 执行引擎抽象基类

Provides shared infrastructure for all execution modes:
message building, tool parsing, tool call loop, event publishing.
提供所有执行模式共享的基础设施：消息构建、工具解析、工具调用循环、事件发布。
"""

from __future__ import annotations

import dataclasses
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from jinja2 import BaseLoader, ChainableUndefined, Environment, TemplateSyntaxError, UndefinedError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.events.bus import get_event_bus
from app.ai.events.types import (
    ExecutionCompleted,
    ExecutionFailed,
    ExecutionStarted,
)

if TYPE_CHECKING:
    from app.ai.gateway import AIGateway
from app.ai.skills.resolver import SkillResolveResult
from app.ai.tools.sandbox import ToolSandbox
from app.ai.tools.types import ToolDefinition, ToolResult, to_openai_tools
from app.ai.types import ChatMessage, ChatResponse
from app.core.base_model import utc_now
from app.core.i18n import _
from app.core.logging import LogManager
from app.models.ai.agent import Agent

from .types import ExecutionRequest, ExecutionResult, PreparedExecution

logger = LogManager.get_logger("ai.engine")

# Max tool call rounds (prevents infinite loop) / 工具调用最大循环次数（防止无限循环）
MAX_TOOL_CALL_ROUNDS = 10

# Jinja2 environment (shared instance, undefined renders as empty string instead of error) / Jinja2 环境（共享实例，undefined 渲染为空字符串而非报错）
_jinja_env = Environment(loader=BaseLoader(), keep_trailing_newline=True, undefined=ChainableUndefined)


class BaseEngine(ABC):
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
        sandbox: ToolSandbox,
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

    # ========================================
    # Message Building / 消息构建
    # ========================================

    def _build_system_message(
        self,
        agent: Agent,
        input_variables: dict[str, Any] | None = None,
    ) -> ChatMessage:
        """
        Build system message.
        构建 system 消息。

        Renders system_prompt with Jinja2, supporting built-in and custom variables.
        Built-in: current_date, current_time, agent_name
        Custom: from input_variables parameter
        使用 Jinja2 渲染 system_prompt，支持内置变量和自定义变量。

        Args:
            agent: Agent / 智能体
            input_variables: Input variables / 输入变量
        """
        prompt = agent.system_prompt or ""

        agent_name = agent.name or ""

        if not prompt:
            return ChatMessage(role="system", content=prompt)

        # Auto-inject identity declaration to prevent model from self-identifying as GPT/DeepSeek etc.
        # 自动注入身份声明，防止模型自称 GPT / DeepSeek 等
        if agent_name:
            identity = _("data_intelligence.identity_declaration").format(agent_name=agent_name)
            prompt = f"{identity}\n\n{prompt}"

        # Build template variables (built-in + custom) / 构建模板变量（内置 + 自定义）
        now = utc_now()
        variables: dict[str, Any] = {
            "current_date": now.strftime("%Y-%m-%d"),
            "current_time": now.strftime("%H:%M:%S"),
            "agent_name": agent_name,
        }
        if input_variables:
            variables.update(input_variables)

        try:
            template = _jinja_env.from_string(prompt)
            prompt = template.render(**variables)
        except TemplateSyntaxError as exc:
            logger.warning(
                "Template syntax error: agent_id=%s error=%s",
                agent.id, str(exc),
            )
        except UndefinedError as exc:
            logger.warning(
                "Template undefined variable: agent_id=%s error=%s",
                agent.id, str(exc),
            )
        except Exception as exc:
            logger.warning(
                "Template render error: agent_id=%s error=%s",
                agent.id, str(exc),
            )

        return ChatMessage(role="system", content=prompt)

    @staticmethod
    def _inject_tool_awareness(
        messages: list[ChatMessage],
        tools: list[ToolDefinition],
        input_variables: dict[str, Any] | None = None,
    ) -> None:
        """
        Inject available tool summary into system message tail. / 将可用工具摘要注入 system 消息末尾。

        Some LLMs (e.g. DeepSeek) tend to generate text rather than call function calling
        when tools are not mentioned in system_prompt.
        Appends a short hint to ensure the model knows it has callable tools.
        部分 LLM（如 DeepSeek）在 system_prompt 中未提及工具时
        倾向于生成文本而非调用 function calling。
        """
        if not tools or not messages or messages[0].role != "system":
            return

        tool_names = [t.name for t in tools]
        hint = (
            "\n\n---\n"
            "[TOOL AWARENESS]\n"
            f"You have {len(tool_names)} tool(s) available: {', '.join(tool_names)}.\n"
            "When the user's request can be fulfilled by calling a tool, "
            "you MUST call the appropriate tool instead of generating text-only responses. "
            "Do NOT say you cannot access the database or perform actions — use your tools.\n"
            "Do NOT show HTML, JSON, tool parameters or raw API output to the user. "
            "Tools are for internal execution; return natural language results only."
        )

        page_hint = BaseEngine._build_page_operations_hint(input_variables, tools)
        if page_hint:
            hint += page_hint

        messages[0] = ChatMessage(
            role="system",
            content=messages[0].content + hint,
        )

    @staticmethod
    def _build_page_operations_hint(
        input_variables: dict[str, Any] | None,
        tools: list[ToolDefinition] | None = None,
    ) -> str:
        """
        Build a PAGE OPERATIONS hint when page context has available operations.
        当页面上下文有可用操作时构建 PAGE OPERATIONS 提示。

        When dedicated pageop_* tools exist, use tool-first language. Otherwise fallback to invoke_page_operation.
        存在专用 pageop_* 工具时用 tool-first 表述，否则回退到 invoke_page_operation。
        """
        if not input_variables:
            return ""
        from app.schemas.ai.agent_chat import PAGE_CONTEXT_KEY

        page_ctx = input_variables.get(PAGE_CONTEXT_KEY)
        if not isinstance(page_ctx, dict):
            return ""

        page_key = (page_ctx.get("page_key") or "").strip()
        page_data = page_ctx.get("page_data")
        if not isinstance(page_data, dict) or not page_key:
            return ""

        raw_ops = page_data.get("available_operations")
        if not isinstance(raw_ops, list) or not raw_ops:
            return ""

        op_names = [o["name"] for o in raw_ops if isinstance(o, dict) and o.get("name")]
        if not op_names:
            return ""

        entity_desc = page_data.get("entity_description", "")
        desc_line = f"\nPage entity: {entity_desc}\n" if entity_desc else "\n"

        tool_names = [t.name for t in (tools or [])]
        has_dedicated_editor_tools = any(n.startswith("pageop_") for n in tool_names)

        if has_dedicated_editor_tools:
            # Preferred: pageop_* for expanded ops; invoke_page_operation for others (17 ops).
            # 优先使用 pageop_* 调用已展开操作；无专用工具的操作用 invoke_page_operation。
            pageop_tool_ops = {
                n.removeprefix("pageop_") for n in tool_names if n.startswith("pageop_")
            }
            other_ops = [name for name in op_names if name not in pageop_tool_ops]
            other_ops_hint = ""
            if other_ops:
                other_ops_hint = (
                    f"\nOther operations (use invoke_page_operation): "
                    f"{', '.join(other_ops)}\n"
                    f'Format: invoke_page_operation(page_key="{page_key}", '
                    f'operation_name="<name>", params={{...}})'
                )
            return (
                f"\n\n[PAGE OPERATIONS]\n"
                f"Current page: {page_key}{desc_line}"
                f"Preferred: use dedicated pageop_* tools directly when available.\n"
                f"Order: 1) pageop_get_editor_html to read; 2) pageop_replace_section for partial edits; "
                f"3) pageop_replace_content only for full rewrite; "
                f"4) pageop_update_title for metadata title (not body H1)."
                f"{other_ops_hint}\n"
                f"Do NOT show HTML, JSON, tool params or call examples to the user. "
                f"Tools are for internal execution; return natural language results only."
            )
        # Fallback: invoke_page_operation format for non-rich-text pages
        has_replace_section = "replace_section" in op_names
        section_example = ""
        if has_replace_section:
            section_example = (
                f'\nPartial edit: invoke_page_operation(page_key="{page_key}", '
                f'operation_name="replace_section", '
                f'params={{"old_html": "<h2>Old heading</h2>", '
                f'"new_html": "<h2>New heading</h2><p>Updated text</p>"}})'
            )

        return (
            f"\n\n[PAGE OPERATIONS]\n"
            f"Current page: {page_key}{desc_line}"
            f"Available operations: {', '.join(op_names)}\n"
            f"Call format: invoke_page_operation("
            f'page_key="{page_key}", '
            f'operation_name="<pick one>", '
            f"params={{...}})\n"
            f'Read: invoke_page_operation(page_key="{page_key}", '
            f'operation_name="get_editor_html", params={{}})'
            f"{section_example}"
        )

    @staticmethod
    def _user_message(content: str) -> ChatMessage:
        """Build user message / 构建 user 消息"""
        return ChatMessage(role="user", content=content)

    # ========================================
    # Shared Pre-logic / 共享前置逻辑
    # ========================================

    async def _prepare_execution(
        self,
        agent: Agent,
        request: ExecutionRequest,
        skill_result: SkillResolveResult | None = None,
    ) -> PreparedExecution:
        """
        Build execution context (shared pre-logic for execute / stream_execute).
        构建执行上下文（execute / stream_execute 共享前置逻辑）。

        Includes / 包含：
        1. Use pre-resolved Skill result (or fallback to internal resolve) / 使用预解析的 Skill 结果
        2. Build message list (system + history) / 构建消息列表
        3. RAG knowledge base injection / RAG 知识库注入
        4. Tool optimization / 工具优化
        5. Tool awareness hint injection / 工具感知提示注入

        Args:
            agent: Agent model instance / 智能体模型实例
            request: Execution request / 执行请求
            skill_result: Pre-resolved Skill result (from Dispatcher layer) / 预解析的 Skill 结果

        Returns:
            PreparedExecution context / PreparedExecution 上下文
        """
        # 1. Use pre-resolved Skill result, or fallback to internal resolve (backward compatible) / 使用预解析的 Skill 结果，或回退到内部解析（兼容旧调用路径）
        if skill_result is None:
            from app.ai.skills.resolver import resolve_for_agent
            skill_result = await resolve_for_agent(
                self.db, agent,
                tenant_id=request.tenant_id,
                user_role=getattr(request, "user_role", None),
            )

        # 2. Build message list / 构建消息列表
        messages: list[ChatMessage] = []
        system_msg = self._build_system_message(agent, request.input_variables)
        messages.append(system_msg)

        if request.messages:
            messages.extend(request.messages)

        # 3. RAG knowledge base injection / RAG 知识库注入
        # Dual-path merge: Agent binding table (primary) + user @ selection (auxiliary)
        # 双路合并：Agent 绑定表（主要）+ 用户 @ 选择（辅助）
        from app.ai.rag_injector import (
            inject_rag_context,
            load_agent_kb_bindings,
            merge_kb_ids,
        )
        rag_sources = None
        agent_kb_ids, agent_kb_weights = await load_agent_kb_bindings(
            self.db, agent.id,
        )
        merged_kb_ids = merge_kb_ids(agent_kb_ids, request.knowledge_base_ids)
        effective_rag_config = agent.rag_config or {}
        if merged_kb_ids:
            messages, rag_sources = await inject_rag_context(
                self.db, agent, messages, request.tenant_id,
                kb_ids=merged_kb_ids,
                rag_config=effective_rag_config or None,
                kb_weights=agent_kb_weights,
            )

        # 4. Get tool list + expand editor tools (before optimize) + optimize
        tools = skill_result.tools if skill_result else []
        if tools:
            from app.ai.tools.page_tool_expander import expand_editor_tools
            tools = expand_editor_tools(tools, request.input_variables)

        optimize_event: dict[str, Any] | None = None
        if tools:
            user_query = ""
            for _m in reversed(messages):
                if _m.role == "user":
                    user_query = _m.content or ""
                    break
            from app.ai.tools.optimizer import optimize_tools
            opt = optimize_tools(tools, user_query)
            tools = opt.tools
            if not opt.skipped:
                optimize_event = {"total": opt.total, "selected": opt.selected}

        # 4.5 Enhance tool schemas with page context (enum/default) / 用页面上下文增强工具 Schema
        if tools:
            from app.ai.tools.enhancer import enhance_tools_with_page_context
            enhance_tools_with_page_context(tools, request.input_variables)

        # 5. Inject tool awareness hint / 注入工具感知提示
        if tools:
            self._inject_tool_awareness(messages, tools, request.input_variables)

        # 6. Extract consent_modes / 提取 consent_modes
        tool_consent_modes = (
            skill_result.tool_consent_modes if skill_result else {}
        )

        # 7. ModelRouter multi-model routing (graceful fallback on failure) / ModelRouter 多模型路由（容错失败时自动向后兼容）
        route_result = None
        try:
            from app.ai.routing.router import ModelRouter
            from app.services.ai.metering_service import TokenCounter

            estimated_tokens = TokenCounter.count_messages_tokens(
                [{"content": m.content or "", "name": m.name or ""} for m in messages]
            )
            router = ModelRouter(self.db)
            route_result = await router.route(agent, request, estimated_tokens, tools=tools)
        except Exception as _routing_exc:
            logger.warning("ModelRouter integration failed: %s", str(_routing_exc))

        return PreparedExecution(
            messages=messages,
            tools=tools,
            rag_sources=rag_sources,
            tool_consent_modes=tool_consent_modes,
            optimize_event=optimize_event,
            route_result=route_result,
        )

    # ========================================
    # LLM Call / LLM 调用
    # ========================================

    async def _call_llm(
        self,
        agent: Agent,
        messages: list[ChatMessage],
        tools: list[ToolDefinition] | None = None,
        tenant_id: int | None = None,
        user_id: int | None = None,
        route_result: Any | None = None,
    ) -> ChatResponse:
        """
        Call LLM.
        调用 LLM。

        Args:
            agent: Agent (with model config) / 智能体（含模型配置）
            messages: Message list / 消息列表
            tools: Tool definition list / 工具定义列表
            tenant_id: Tenant ID / 企业 ID
            user_id: User ID / 用户 ID
            route_result: ModelRouter route result (None uses agent's original model) / ModelRouter 路由结果
        """
        # Build OpenAI tools parameter / 构建 OpenAI tools 参数
        openai_tools = None
        if tools:
            openai_tools = to_openai_tools(tools)

        # Get model info: route override takes priority / 获取模型信息：路由覆写优先
        if route_result is not None and getattr(route_result, "is_overridden", False):
            provider_code = route_result.provider_code or ""
            model_code = route_result.model_code or ""
            # Use routed model's actual capabilities (per spec: 根据模型的 supports_* 决定)
            # 使用路由选中模型的真实能力（规范：根据模型的 supports_* 决定）
            model_id: int = getattr(route_result, "model_id", 0)
            route_model_obj = None
            if model_id:
                from app.repositories.ai.model_repository import AIModelRepository
                model_repo = AIModelRepository(self.db)
                route_model_obj = await model_repo.get_active_with_provider(model_id)
            if route_model_obj is not None:
                is_vision = bool(route_model_obj.supports_vision)
                is_audio = bool(getattr(route_model_obj, "supports_audio", False))
                is_video = bool(getattr(route_model_obj, "supports_video", False))
            else:
                # Fallback: reason-based inference when routed model unavailable
                # 退路：路由模型不可用时按 reason 推断
                reason_str: str = route_result.reason or ""
                is_vision = "vision" in reason_str
                is_audio = "audio" in reason_str
                is_video = "video" in reason_str
        else:
            model_obj = agent.model
            provider_code = model_obj.provider.code if model_obj and model_obj.provider else ""
            model_code = model_obj.code if model_obj else ""
            is_vision = model_obj.supports_vision if model_obj else False
            is_audio = getattr(model_obj, "supports_audio", False) if model_obj else False
            is_video = getattr(model_obj, "supports_video", False) if model_obj else False

        # Non-capability model: remove corresponding attachments to avoid API errors
        # 无对应能力的模型：移除对应附件，避免 API 报错
        for msg in messages:
            if msg.attachments:
                kept = [
                    a
                    for a in msg.attachments
                    if not (
                        (a.get("type") == "image" and not is_vision)
                        or (a.get("type") == "audio" and not is_audio)
                        or (a.get("type") == "video" and not is_video)
                    )
                ]
                msg.attachments = kept if kept else None

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
            supports_vision=bool(is_vision),
            supports_audio=bool(is_audio),
            supports_video=bool(is_video),
        )

        return response

    # ========================================
    # Tool Call Loop / 工具调用循环
    # ========================================

    async def _handle_tool_calls(
        self,
        agent: Agent,
        messages: list[ChatMessage],
        response: ChatResponse,
        tools: list[ToolDefinition],
        request: ExecutionRequest,
        skip_final_call: bool = False,
        route_result: Any | None = None,
    ) -> tuple[ChatResponse | None, list[ToolResult], int]:
        """
        Handle tool call loop.
        处理工具调用循环。

        When LLM returns tool_calls, executes tools and appends results to messages,
        then calls LLM again until no more tool_calls or max rounds reached.
        当 LLM 返回 tool_calls 时，执行工具并将结果追加到消息中，
        然后再次调用 LLM，直到不再返回 tool_calls 或达到最大轮次。

        Args:
            agent: Agent / 智能体
            messages: Current message list (will be modified) / 当前消息列表（会被修改）
            response: LLM response / LLM 响应
            tools: Tool definition list / 工具定义列表
            request: Original request / 原始请求
            skip_final_call: Skip final LLM call (for streaming path, caller handles streaming) / 跳过最终 LLM 调用
            route_result: ModelRouter route result (maintains model consistency within tool call loop) / ModelRouter 路由结果

        Returns:
            (final_response, all_tool_results, total_tokens)
            final_response is None when skip_final_call=True
            当 skip_final_call=True 时 final_response 为 None
        """
        from .tool_processor import ToolCallProcessor

        processor = ToolCallProcessor(
            sandbox=self.sandbox,
            tools=tools,
        )

        all_tool_results: list[ToolResult] = []
        total_tokens = response.total_tokens or 0
        current_response = response

        for _round in range(MAX_TOOL_CALL_ROUNDS):
            tool_calls = current_response.tool_calls
            if not tool_calls:
                break

            # Append assistant message (with tool_calls) / 追加 assistant 消息（含 tool_calls）
            messages.append(processor.build_assistant_tool_call_message(
                content=current_response.message.content or "",
                tool_calls=tool_calls,
            ))

            # Execute each tool call (using ToolCallProcessor shared logic) / 执行每个工具调用（使用 ToolCallProcessor 共享逻辑）
            for tc in tool_calls:
                single = await processor.process_single(
                    tc, conversation_id=request.conversation_id or 0,
                )
                if single.tool_result:
                    all_tool_results.append(single.tool_result)
                if single.tool_message:
                    messages.append(single.tool_message)

            if skip_final_call:
                if _round < MAX_TOOL_CALL_ROUNDS - 1:
                    peek_response = await self._call_llm(
                        agent=agent,
                        messages=messages,
                        tools=tools,
                        tenant_id=request.tenant_id,
                        user_id=request.user_id,
                        route_result=route_result,
                    )
                    total_tokens += peek_response.total_tokens or 0
                    if peek_response.tool_calls:
                        current_response = peek_response
                        continue
                return None, all_tool_results, total_tokens

            # Call LLM again (maintain same routed model as first call) / 再次调用 LLM（保持与第一次调用相同的路由模型）
            current_response = await self._call_llm(
                agent=agent,
                messages=messages,
                tools=tools,
                tenant_id=request.tenant_id,
                user_id=request.user_id,
                route_result=route_result,
            )
            total_tokens += current_response.total_tokens or 0

        return current_response, all_tool_results, total_tokens

    # ========================================
    # Event Publishing / 事件发布
    # ========================================

    @staticmethod
    async def _publish_execution_started(request: ExecutionRequest, agent: Agent) -> None:
        """Publish execution started event / 发布执行开始事件"""
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
        """Publish execution completed event / 发布执行完成事件"""
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
        """Publish execution failed event / 发布执行失败事件"""
        await get_event_bus().publish(ExecutionFailed(
            tenant_id=request.tenant_id,
            agent_id=agent.id,
            error=error,
            error_type=error_type,
        ))

    # ========================================
    # Utility Methods / 工具方法
    # ========================================

    @staticmethod
    def _messages_to_dicts(messages: list[ChatMessage]) -> list[dict[str, Any]]:
        """Convert ChatMessage list to dict list / 将 ChatMessage 列表转为 dict 列表"""
        return [dataclasses.asdict(msg) for msg in messages]


__all__ = ["BaseEngine"]
