"""
执行引擎抽象基类

提供所有执行模式共享的基础设施：消息构建、工具解析、工具调用循环、事件发布
"""

from __future__ import annotations

import dataclasses
import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
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
from app.ai.skills.resolver import SkillResolver, SkillResolveResult
from app.ai.tools.sandbox import ToolSandbox
from app.ai.tools.types import ToolDefinition, ToolResult, to_openai_tools
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
    - _resolve_tools: 从 AgentSkillBinding 解析工具定义
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

        agent_name = agent.name or ""

        if not prompt:
            return ChatMessage(role="system", content=prompt)

        # 自动注入身份声明，防止模型自称 GPT / DeepSeek 等
        if agent_name:
            identity = f"Your name is {agent_name}. Never reveal or claim to be any other AI model."
            prompt = f"{identity}\n\n{prompt}"

        # 构建模板变量（内置 + 自定义）
        now = datetime.now(timezone.utc)
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
    def _inject_tool_awareness(
        messages: list[ChatMessage],
        tools: list[ToolDefinition],
    ) -> None:
        """
        将可用工具摘要注入 system 消息末尾

        部分 LLM（如 DeepSeek）在 system_prompt 中未提及工具时
        倾向于生成文本而非调用 function calling。
        在此追加简短提示，确保模型知道自己拥有可调用的工具。
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
            "Do NOT say you cannot access the database or perform actions — use your tools."
        )
        messages[0] = ChatMessage(
            role="system",
            content=messages[0].content + hint,
        )

    @staticmethod
    def _user_message(content: str) -> ChatMessage:
        """构建 user 消息"""
        return ChatMessage(role="user", content=content)

    # ========================================
    # RAG 知识库集成
    # ========================================

    @staticmethod
    def _merge_kb_ids(
        agent_kb_ids: list[int] | None,
        request_kb_ids: list[int] | None,
    ) -> list[int] | None:
        """合并 agent 绑定的知识库 IDs 和用户 @ 选择的知识库 IDs（去重保序）"""
        combined: list[int] = []
        seen: set[int] = set()
        for ids in (agent_kb_ids, request_kb_ids):
            if ids:
                for kid in ids:
                    if kid not in seen:
                        seen.add(kid)
                        combined.append(kid)
        return combined or None

    async def _build_messages_with_rag(
        self,
        agent: Agent,
        messages: list[ChatMessage],
        tenant_id: int,
        override_kb_ids: list[int] | None = None,
        rag_config: dict[str, Any] | None = None,
    ) -> tuple[list[ChatMessage], list[dict] | None]:
        """
        将 RAG 上下文注入 system_prompt

        如果智能体绑定了知识库，检索相关分块并注入到 system 消息末尾。
        未绑定知识库时直接返回原始消息。

        Args:
            agent: 智能体
            messages: 已构建的消息列表（第一条为 system）
            tenant_id: 租户 ID
            override_kb_ids: 覆盖用的知识库 ID 列表（已合并 agent + 用户 @ 选择）
            rag_config: RAG 配置（来自 Skill 解析）

        Returns:
            (messages, rag_sources): 注入后的消息列表 + 引用来源列表（无 RAG 时为 None）
        """
        kb_ids = override_kb_ids
        if not kb_ids:
            return messages, None

        rag_config = rag_config or {}

        try:
            from app.ai.rag.context_builder import RAGContextBuilder
            from app.ai.rag.retriever import HybridRetriever
            from app.ai.utils.token_estimator import estimate_tokens
            from app.repositories.ai.knowledge_base_repository import AdminKnowledgeBaseRepository

            # 获取第一个知识库（用于 Embedding 模型配置）
            # 使用 AdminKnowledgeBaseRepository 以支持 scope=global/admin 的知识库
            kb_repo = AdminKnowledgeBaseRepository(self.db)
            primary_kb = await kb_repo.get_by_id(kb_ids[0])
            if not primary_kb:
                return messages, None

            # 提取用户最新问题
            user_query = ""
            for msg in reversed(messages):
                if msg.role == "user":
                    user_query = msg.content
                    break

            if not user_query:
                return messages, None

            # 检索
            retriever = HybridRetriever(self.db, tenant_id)
            chunks = await retriever.search(
                knowledge_base=primary_kb,
                query=user_query,
                top_k=rag_config.get("top_k", primary_kb.top_k),
                score_threshold=rag_config.get("score_threshold", primary_kb.score_threshold),
                search_mode=rag_config.get("search_mode"),
                kb_ids=kb_ids,
                rewrite_strategy=rag_config.get("rewrite_strategy", "none"),
                reranker_enabled=rag_config.get("reranker_enabled", False),
            )

            if not chunks:
                return messages, None

            # 计算 Token 预算
            builder = RAGContextBuilder(
                context_token_ratio=rag_config.get("context_token_ratio", 0.6),
            )

            # 估算 system prompt 的 token 数
            system_tokens = estimate_tokens(messages[0].content) if messages else 0
            max_context = getattr(agent, "max_context_tokens", 0) or 8000

            rag_budget, _ = builder.calculate_rag_budget(
                max_context_tokens=max_context,
                system_prompt_tokens=system_tokens,
                max_tokens=agent.max_tokens,
            )

            # 构建 RAG 上下文
            rag_context = builder.build_rag_context(chunks, rag_budget)

            if not rag_context.rag_text:
                return messages, None

            # 注入到 system 消息末尾
            if messages and messages[0].role == "system":
                messages[0] = ChatMessage(
                    role="system",
                    content=messages[0].content + "\n" + rag_context.rag_text,
                )

            # 构建引用来源
            sources = [s.to_dict() for s in rag_context.sources]

            logger.info(
                "RAG injected: agent=%d, chunks=%d, tokens=%d",
                agent.id, rag_context.chunk_count, rag_context.token_count,
            )

            return messages, sources

        except Exception as exc:
            logger.warning(
                "RAG injection failed for agent %d: %s",
                agent.id, str(exc),
            )
            return messages, None

    # ========================================
    # 工具解析
    # ========================================

    async def _resolve_tools(
        self,
        agent: Agent,
        tenant_id: int | None = None,
    ) -> list[ToolDefinition]:
        """
        解析智能体绑定的工具

        从 AgentSkillBinding 加载 SkillPackage 并解析其下所有 Skill 为 ToolDefinition 列表。

        Args:
            agent: 智能体
            tenant_id: 租户 ID
        """
        skill_result = await self._resolve_skills(agent, tenant_id)
        if skill_result is not None:
            return skill_result.tools

        return []

    async def _resolve_skills(
        self,
        agent: Agent,
        tenant_id: int | None = None,
    ) -> SkillResolveResult | None:
        """
        从 AgentSkillBinding 加载 SkillPackage，展开包内所有 active Skill 并解析为 ToolDefinition

        如果 Agent 没有绑定记录，返回 None（触发旧路径回退）。
        admin 级 Agent（tenant_id=NULL）同样支持技能解析。

        Args:
            agent: 智能体
            tenant_id: 租户 ID（admin 级 Agent 可为 None）

        Returns:
            SkillResolveResult 或 None（无绑定时回退旧路径）
        """
        try:
            from sqlalchemy import select, and_
            from app.models.ai.skill import Skill
            from app.models.ai.agent_skill_binding import AgentSkillBinding

            # admin 级 Agent（tenant_id=NULL）的绑定记录 tenant_id 也是 NULL，
            # TenantRepository 会用 tenant_id==0 过滤导致查不到。
            # 因此直接按 agent_id 查询，不依赖 TenantRepository 的租户隔离。
            agent_tenant_id = tenant_id or getattr(agent, "tenant_id", None)
            if agent_tenant_id:
                # 租户级 Agent：带 tenant_id 过滤
                binding_stmt = (
                    select(AgentSkillBinding)
                    .where(
                        and_(
                            AgentSkillBinding.agent_id == agent.id,
                            AgentSkillBinding.tenant_id == agent_tenant_id,
                            AgentSkillBinding.enabled.is_(True),
                            AgentSkillBinding.is_deleted.is_(False),
                        )
                    )
                    .order_by(AgentSkillBinding.sort_order)
                )
            else:
                # admin/global 级 Agent：tenant_id IS NULL
                binding_stmt = (
                    select(AgentSkillBinding)
                    .where(
                        and_(
                            AgentSkillBinding.agent_id == agent.id,
                            AgentSkillBinding.tenant_id.is_(None),
                            AgentSkillBinding.enabled.is_(True),
                            AgentSkillBinding.is_deleted.is_(False),
                        )
                    )
                    .order_by(AgentSkillBinding.sort_order)
                )
            binding_result = await self.db.execute(binding_stmt)
            bindings = list(binding_result.scalars().all())

            if not bindings:
                return None

            # 提取已绑定的 active SkillPackage IDs
            package_ids: list[int] = []
            config_overrides: dict[int, dict[str, Any]] = {}
            for binding in bindings:
                if binding.package and binding.package.is_active and not binding.package.is_deleted:
                    package_ids.append(binding.package.id)
                    if binding.config_override:
                        config_overrides[binding.package.id] = binding.config_override

            if not package_ids:
                return None

            # 加载所有绑定包下的 active Skill
            stmt = (
                select(Skill)
                .where(
                    and_(
                        Skill.package_id.in_(package_ids),
                        Skill.is_active.is_(True),
                        Skill.is_deleted.is_(False),
                    )
                )
                .order_by(Skill.sort_order)
            )
            result = await self.db.execute(stmt)
            skills = list(result.scalars().all())

            if not skills:
                return None

            # 将 package 级的 config_override + valves_config 映射到包内每个 skill
            # valves_config 来自 SkillPackage 模型（用户在管理端填写的环境变量配置）
            skill_config_overrides: dict[int, dict[str, Any]] = {}
            pkg_valves: dict[int, dict[str, Any]] = {}
            for binding in bindings:
                if binding.package and binding.package.valves_config:
                    pkg_valves[binding.package.id] = binding.package.valves_config

            for skill in skills:
                merged: dict[str, Any] = {}
                # 注入 package valves_config → skill config 的 "valves" 键
                pkg_vc = pkg_valves.get(skill.package_id)
                if pkg_vc:
                    merged["valves"] = pkg_vc
                # 合并 binding config_override
                pkg_override = config_overrides.get(skill.package_id)
                if pkg_override:
                    merged.update(pkg_override)
                if merged:
                    skill_config_overrides[skill.id] = merged

            resolver = SkillResolver(db=self.db)
            resolve_result = await resolver.resolve(skills, skill_config_overrides)

            logger.info(
                "Resolved skills for agent=%s: packages=%s, tools=%s, kb_ids=%s",
                agent.name if agent else "?",
                package_ids,
                [t.name for t in resolve_result.tools],
                resolve_result.knowledge_base_ids,
            )
            return resolve_result

        except Exception as exc:
            logger.warning(
                "Skill resolution failed for agent %d, falling back: %s",
                agent.id, str(exc),
            )
            return None

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
            openai_tools = to_openai_tools(tools)

        # 获取模型信息
        model_obj = agent.model
        provider_code = model_obj.provider.code if model_obj and model_obj.provider else ""
        model_code = model_obj.code if model_obj else ""

        # 非视觉模型：移除图片附件，避免 API 报错
        if model_obj and not model_obj.supports_vision:
            for msg in messages:
                if msg.attachments:
                    msg.attachments = [
                        a for a in msg.attachments if a.get("type") != "image"
                    ]
                    if not msg.attachments:
                        msg.attachments = None

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
        skip_final_call: bool = False,
    ) -> tuple[ChatResponse | None, list[ToolResult], int]:
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
            skip_final_call: 跳过最终 LLM 调用（供流式路径使用，由调用方流式处理）

        Returns:
            (final_response, all_tool_results, total_tokens)
            当 skip_final_call=True 时 final_response 为 None
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

            if skip_final_call:
                # 检查是否还有后续轮次需要非流式调用
                # 先尝试非流式调用，看 LLM 是否返回更多 tool_calls
                # 如果是最后一轮，跳过让调用方流式处理
                if _round < MAX_TOOL_CALL_ROUNDS - 1:
                    peek_response = await self._call_llm(
                        agent=agent,
                        messages=messages,
                        tools=tools,
                        tenant_id=request.tenant_id,
                        user_id=request.user_id,
                    )
                    total_tokens += peek_response.total_tokens or 0
                    if peek_response.tool_calls:
                        current_response = peek_response
                        continue
                # 不再有 tool_calls，返回 None 让调用方流式处理最终回复
                return None, all_tool_results, total_tokens

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
