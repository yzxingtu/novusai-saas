"""
Execution Engine Abstract Base Class / 执行引擎抽象基类

Provides shared infrastructure for all execution modes:
message building, tool parsing, tool call loop, event publishing.
提供所有执行模式共享的基础设施：消息构建、工具解析、工具调用循环、事件发布。
"""

from __future__ import annotations

import asyncio
import dataclasses
import hashlib
import json
from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING, Any

from jinja2 import (
    BaseLoader,
    ChainableUndefined,
    Environment,
    TemplateSyntaxError,
    UndefinedError,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.context import get_context_engine
from app.ai.events.bus import get_event_bus
from app.ai.events.types import (
    ExecutionCompleted,
    ExecutionFailed,
    ExecutionStarted,
)
from app.ai.runtime.types import TurnRecord
from app.services.ai.execution_trust_policy_service import (
    ExecutionTrustPolicyService,
)

if TYPE_CHECKING:
    from app.ai.gateway import AIGateway
from app.ai.prompt_contracts import render_prompt_contract
from app.ai.skills.resolver import SkillResolveResult
from app.ai.text_semantics import (
    extract_textual_tool_call_names as extract_textual_tool_call_names_from_text,
)
from app.ai.text_semantics import (
    has_capability_denial_phrase,
    has_question_indicator,
    has_tool_planning_leak_phrase,
    mentions_page_detail_operation,
    mentions_page_summary,
    mentions_rail_ticket,
    mentions_weather,
)
from app.ai.tools.sandbox import ToolSandbox
from app.ai.tools.semantic_defaults import (
    FAMILY_HINT_TAGS as _SEMANTIC_FAMILY_HINT_TAGS,
)
from app.ai.tools.semantic_defaults import (
    tool_family_from_name as _tool_family_from_name_unified,
)
from app.ai.tools.semantic_defaults import (
    tool_semantic_family as _tool_semantic_family_unified,
)
from app.ai.tools.semantic_defaults import (
    tool_semantic_tags as _tool_semantic_tags_unified,
)
from app.ai.tools.types import ToolDefinition, ToolResult, to_openai_tools
from app.ai.types import ChatMessage, ChatResponse
from app.ai.utils.token_estimator import estimate_tokens
from app.core.config import settings
from app.core.i18n import _
from app.core.logging import LogManager
from app.core.runtime_identity import get_runtime_identity_tag
from app.enums.common import UserRoleEnum
from app.enums.log import UserTypeEnum as LogUserTypeEnum
from app.exceptions import BusinessException
from app.models.ai.agent import Agent

from .budget_guard import BudgetGuard
from .intent_planner import IntentPlanner
from .path_selector import PathSelector
from .tool_router import ToolRouter
from .types import (
    ExecutionBudget,
    ExecutionRequest,
    ExecutionResult,
    IntentPlan,
    PreparedExecution,
    ResearchContinuationContext,
    ToolUsePolicy,
)

logger = LogManager.get_logger("ai.engine")
_PAGE_NAVIGATION_OPERATION_NAMES = {
    "navigate_back",
    "navigate_menu",
    "navigate_to_detail",
    "open_current",
    "open_page",
}
_CAPABILITY_REPORTING_QUERY_TERMS = (
    "这轮有哪些能力",
    "当前能力",
    "本轮能力",
    "你有哪些能力",
    "你能做什么",
    "可以做什么",
    "能力有哪些",
    "available capabilities",
    "current capabilities",
    "capabilities this turn",
    "what can you do this turn",
    "what can you do",
)


def log_user_type_for_call_log(user_role: str) -> str:
    """Map ExecutionRequest.user_role → call_log.user_type / 执行请求角色 → 调用日志用户类型."""
    if user_role == UserRoleEnum.PLATFORM_ADMIN.value:
        return LogUserTypeEnum.ADMIN.value
    if user_role == UserRoleEnum.TENANT_USER.value:
        return LogUserTypeEnum.TENANT_USER.value
    return LogUserTypeEnum.TENANT_ADMIN.value


# Jinja2 environment (shared instance, undefined renders as empty string instead of error) / Jinja2 环境（共享实例，undefined 渲染为空字符串而非报错）
_jinja_env = Environment(
    loader=BaseLoader(), keep_trailing_newline=True, undefined=ChainableUndefined
)


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
        Built-in: current_date, current_time, current_timezone, agent_name
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
            identity = _("agent.identity_declaration").format(
                agent_name=agent_name
            )
            prompt = f"{identity}\n\n{prompt}"

        # Build template variables (built-in + custom) / 构建模板变量（内置 + 自定义）
        now = datetime.now(settings.tz)
        variables: dict[str, Any] = {
            "current_date": now.strftime("%Y-%m-%d"),
            "current_time": now.strftime("%H:%M:%S"),
            "current_timezone": settings.TIMEZONE,
            "agent_name": agent_name,
        }
        if input_variables:
            variables.update(input_variables)

        try:
            template = _jinja_env.from_string(prompt)
            prompt = template.render(**variables)
        except TemplateSyntaxError as exc:
            logger.warning(
                "Template syntax error: agent_id={} error={}",
                agent.id,
                str(exc),
            )
        except UndefinedError as exc:
            logger.warning(
                "Template undefined variable: agent_id={} error={}",
                agent.id,
                str(exc),
            )
        except Exception as exc:
            logger.warning(
                "Template render error: agent_id={} error={}",
                agent.id,
                str(exc),
            )

        return ChatMessage(role="system", content=prompt)

    @staticmethod
    def _inject_runtime_summary(
        messages: list[ChatMessage],
        tools: list[ToolDefinition],
        _input_variables: dict[str, Any] | None = None,
        continuation_context: ResearchContinuationContext | None = None,
        runtime_capability_summary: dict[str, Any] | None = None,
        ordered_requested_families: list[str] | None = None,
        skip_capability_summary: bool = False,
        intent_plan: list[IntentPlan] | None = None,
        execution_path: str | None = None,
        execution_budget: ExecutionBudget | None = None,
        include_knowledge_base_hint: bool = True,
        include_page_context_hint: bool = True,
        include_memory_hint: bool = True,
    ) -> bool:
        """Inject a one-shot runtime summary into the system prompt."""
        if (
            not messages
            or messages[0].role != "system"
            or (not tools and not runtime_capability_summary)
        ):
            return False

        allowed_tool_names = [t.name for t in tools]
        summarized_intents = intent_plan or []
        capability_summary_injected = False
        intent_summary = (
            ", ".join(intent.user_visible_label for intent in summarized_intents[:4])
            or ", ".join(ordered_requested_families or [])
            or "direct_reply"
        )
        hint = "\n\n" + render_prompt_contract(
            "tool_runtime_summary",
            execution_path=execution_path or "fast",
            intent_summary=intent_summary,
            allowed_tools=", ".join(allowed_tool_names) or "none",
            prompt_budget=(
                execution_budget.max_prompt_tokens
                if execution_budget is not None
                else 0
            ),
            tool_round_budget=(
                execution_budget.max_tool_rounds if execution_budget is not None else 0
            ),
            elapsed_budget_ms=(
                execution_budget.max_elapsed_ms if execution_budget is not None else 0
            ),
        )
        hint += "\n\n" + render_prompt_contract("tool_usage_rules")
        continuation_hint = BaseEngine._build_research_continuation_hint(
            continuation_context,
        )
        if continuation_hint:
            hint += continuation_hint
        if not skip_capability_summary:
            runtime_capability_hint = BaseEngine._build_runtime_capability_hint(
                runtime_capability_summary,
                include_knowledge_base_hint=include_knowledge_base_hint,
                include_page_context_hint=include_page_context_hint,
                include_memory_hint=include_memory_hint,
            )
            if runtime_capability_hint:
                hint += runtime_capability_hint
                capability_summary_injected = True

        signature = hashlib.sha1(
            json.dumps(
                {
                    "tools": allowed_tool_names,
                    "intent_summary": intent_summary,
                    "execution_path": execution_path or "fast",
                    "budget": (
                        execution_budget.snapshot()
                        if execution_budget is not None
                        else None
                    ),
                    "runtime_capability_summary": dict(
                        runtime_capability_summary or {}
                    ),
                    "skip_capability_summary": bool(skip_capability_summary),
                    "include_knowledge_base_hint": bool(include_knowledge_base_hint),
                    "include_page_context_hint": bool(include_page_context_hint),
                    "include_memory_hint": bool(include_memory_hint),
                },
                ensure_ascii=False,
                sort_keys=True,
                default=str,
            ).encode("utf-8")
        ).hexdigest()
        metadata = dict(messages[0].metadata or {})
        if metadata.get("runtime_summary_signature") == signature:
            return capability_summary_injected
        metadata["runtime_summary_signature"] = signature
        messages[0] = ChatMessage(
            role="system",
            content=messages[0].content + hint,
            metadata=metadata,
        )
        return capability_summary_injected

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
        tool_names = [t.name for t in (tools or [])]
        has_dedicated_page_tools = any(n.startswith("pageop_") for n in tool_names)
        has_data_tools = any(n.startswith("data_") for n in tool_names)
        data_distinction_note = ""
        if has_data_tools:
            data_distinction_note = "\n" + render_prompt_contract(
                "page_operations_data_distinction"
            )

        if has_dedicated_page_tools:
            # Preferred: pageop_* for expanded ops; invoke_page_operation for others.
            # 优先使用 pageop_* 调用已展开操作；无专用工具的操作用 invoke_page_operation。
            pageop_tool_ops = {
                n.removeprefix("pageop_") for n in tool_names if n.startswith("pageop_")
            }
            dedicated_ops = [name for name in op_names if name in pageop_tool_ops]
            other_ops = [name for name in op_names if name not in pageop_tool_ops]
            screenshot_hint = ""
            if "capture_screenshot" in op_names:
                screenshot_hint = "\n" + render_prompt_contract(
                    "page_operations_screenshot_dedicated"
                )
            dedicated_hint = (
                f"\nDedicated pageop_* tools available for: {', '.join(dedicated_ops)}"
                if dedicated_ops
                else ""
            )
            other_ops_hint = ""
            if other_ops:
                other_ops_hint = "\n" + render_prompt_contract(
                    "page_operations_other_ops",
                    other_ops=", ".join(other_ops),
                    page_key=page_key,
                )
            mutation_ops = [
                str(o.get("name", ""))
                for o in raw_ops
                if isinstance(o, dict)
                and o.get("name")
                and not bool(o.get("readonly", False))
            ]
            mutation_hint = ""
            if mutation_ops:
                mutation_hint = "\n" + render_prompt_contract(
                    "page_operations_mutation",
                    mutation_ops=", ".join(mutation_ops),
                )
            editor_flow_hint = ""
            if "get_editor_html" in pageop_tool_ops:
                editor_flow_hint = "\n" + render_prompt_contract(
                    "page_operations_editor_flow"
                )
            return "\n\n" + render_prompt_contract(
                "page_operations_dedicated",
                page_key=page_key,
                entity_desc=entity_desc,
                dedicated_hint=dedicated_hint,
                mutation_hint=mutation_hint,
                editor_flow_hint=editor_flow_hint,
                other_ops_hint=other_ops_hint,
                screenshot_hint=screenshot_hint,
                data_distinction_note=data_distinction_note,
            )
        # Fallback: invoke_page_operation for non-rich-text pages / 非富文本页回退为 invoke_page_operation
        read_example = ""
        if "read_visible_rows" in op_names:
            read_example = (
                f'\nRead rows: invoke_page_operation(page_key="{page_key}", '
                f'operation_name="read_visible_rows", params={{}})'
            )
        elif "get_form_state" in op_names:
            read_example = (
                f'\nRead form: invoke_page_operation(page_key="{page_key}", '
                f'operation_name="get_form_state", params={{}})'
            )
        elif "get_editor_html" in op_names:
            read_example = (
                f'\nRead editor: invoke_page_operation(page_key="{page_key}", '
                f'operation_name="get_editor_html", params={{}})'
            )

        search_example = ""
        if "search" in op_names:
            search_example = (
                f'\nSearch example: invoke_page_operation(page_key="{page_key}", '
                f'operation_name="search", params={{"keyword": "<query>"}})'
            )

        has_replace_section = "replace_section" in op_names
        section_example = ""
        if has_replace_section:
            section_example = (
                f'\nPartial edit: invoke_page_operation(page_key="{page_key}", '
                f'operation_name="replace_section", '
                f'params={{"old_html": "<h2>Old heading</h2>", '
                f'"new_html": "<h2>New heading</h2><p>Updated text</p>"}})'
            )

        screenshot_guidance = ""
        if "capture_screenshot" in op_names:
            screenshot_guidance = "\n" + render_prompt_contract(
                "page_operations_screenshot_fallback"
            )
        mutation_ops = [
            str(o.get("name", ""))
            for o in raw_ops
            if isinstance(o, dict)
            and o.get("name")
            and not bool(o.get("readonly", False))
        ]
        mutation_guidance = ""
        if mutation_ops:
            mutation_guidance = "\n" + render_prompt_contract(
                "page_operations_mutation",
                mutation_ops=", ".join(mutation_ops),
            )

        return "\n\n" + render_prompt_contract(
            "page_operations_fallback",
            page_key=page_key,
            entity_desc=entity_desc,
            op_names=", ".join(op_names),
            read_example=read_example,
            search_example=search_example,
            section_example=section_example,
            screenshot_guidance=screenshot_guidance,
            mutation_guidance=mutation_guidance,
            data_distinction_note=data_distinction_note,
        )

    @staticmethod
    def _deserialize_intent_plan(raw_intent_plan: Any) -> list[IntentPlan]:
        if not isinstance(raw_intent_plan, list):
            return []
        intent_plan: list[IntentPlan] = []
        for raw_intent in raw_intent_plan:
            if isinstance(raw_intent, IntentPlan):
                intent_plan.append(raw_intent)
                continue
            if not isinstance(raw_intent, dict):
                continue
            try:
                intent_plan.append(IntentPlan(**raw_intent))
            except TypeError:
                continue
        return intent_plan

    @staticmethod
    def _intent_plan_gating_flags(intent_plan: list[IntentPlan]) -> dict[str, bool]:
        normalized_plan = list(intent_plan or [])
        intent_kinds = {
            str(intent.kind or "").strip()
            for intent in normalized_plan
        }
        all_shortcircuit = bool(normalized_plan) and all(
            bool(intent.shortcircuit) for intent in normalized_plan
        )
        has_page_intent = any(kind.startswith("page_") for kind in intent_kinds)
        has_knowledge_intent = "knowledge_query" in intent_kinds
        has_memory_intent = any(not bool(intent.shortcircuit) for intent in normalized_plan)
        return {
            "all_shortcircuit": all_shortcircuit,
            "has_page_intent": has_page_intent,
            "has_knowledge_intent": has_knowledge_intent,
            "has_memory_intent": has_memory_intent,
        }

    @staticmethod
    def _is_capability_reporting_query(user_text: str | None) -> bool:
        normalized = " ".join(str(user_text or "").strip().lower().split())
        if not normalized:
            return False
        return any(term in normalized for term in _CAPABILITY_REPORTING_QUERY_TERMS)

    @staticmethod
    def _intent_completion_signals(
        family: str,
        *,
        allowed_tool_names: list[str],
        preferred_tool_names: list[str],
    ) -> list[str]:
        if family == "web_research":
            if "fetch_url" in allowed_tool_names:
                return ["fetch_url"]
            if "web_search" in allowed_tool_names:
                return ["web_search"]
        return list(allowed_tool_names or preferred_tool_names)

    @staticmethod
    def _build_web_research_hint(tools: list[ToolDefinition]) -> str:
        """
        Build a WEB RESEARCH hint when web_search/fetch_url are available.
        当存在 web_search/fetch_url 时构建 WEB RESEARCH 提示。
        """
        tool_names = {t.name for t in tools}
        has_search = "web_search" in tool_names
        has_fetch = "fetch_url" in tool_names
        if not (has_search or has_fetch):
            return ""

        workflow = []
        if has_search:
            workflow.append("1) use web_search to find candidate sources")
        if has_fetch:
            next_step = "2" if has_search else "1"
            workflow.append(
                f"{next_step}) use fetch_url to read the most relevant page content"
            )

        compare_step = "3" if has_search and has_fetch else "2"
        workflow.append(
            f"{compare_step}) prefer official or primary sources, and compare more than one source when the user asks for current, recent, or high-stakes information"
        )

        return "\n\n" + render_prompt_contract(
            "web_research",
            workflow="; ".join(workflow),
        )

    @staticmethod
    def _build_weather_tools_hint(tools: list[ToolDefinition]) -> str:
        """Build a WEATHER TOOLS hint when weather tools are available. / 存在天气工具时构建提示。"""
        tool_names = {t.name for t in tools}
        has_current = "get_current_weather" in tool_names
        has_forecast = "get_weather_forecast" in tool_names
        if not (has_current or has_forecast):
            return ""

        workflow: list[str] = []
        if has_current:
            workflow.append("use get_current_weather for current conditions")
        if has_forecast:
            workflow.append(
                "use get_weather_forecast for tomorrow, future days, or 7-day forecasts"
            )

        return "\n\n" + render_prompt_contract(
            "weather_tools",
            workflow="; ".join(workflow),
        )

    @staticmethod
    def _build_time_tools_hint(tools: list[ToolDefinition]) -> str:
        tool_names = {t.name for t in tools}
        if "get_current_time" not in tool_names:
            return ""
        return "\n\n" + render_prompt_contract("time_tools")

    @staticmethod
    def _build_capability_reporting_hint(
        tools: list[ToolDefinition],
        input_variables: dict[str, Any] | None = None,
    ) -> str:
        """Build a capability-reporting hint for \"what can you do\" questions. / 构建能力口径约束提示。"""
        tool_names = [t.name for t in tools]
        page_ops: list[str] = []
        if input_variables:
            from app.schemas.ai.agent_chat import PAGE_CONTEXT_KEY

            page_ctx = input_variables.get(PAGE_CONTEXT_KEY)
            if isinstance(page_ctx, dict):
                page_data = page_ctx.get("page_data")
                raw_ops = (
                    page_data.get("available_operations")
                    if isinstance(page_data, dict)
                    else None
                )
                if isinstance(raw_ops, list):
                    page_ops = [
                        str(op.get("name", ""))
                        for op in raw_ops
                        if isinstance(op, dict) and op.get("name")
                    ]

        tool_line = ", ".join(tool_names) if tool_names else "none"
        page_line = ", ".join(page_ops) if page_ops else "none"
        return "\n\n" + render_prompt_contract(
            "capability_reporting",
            tool_line=tool_line,
            page_line=page_line,
        )

    @staticmethod
    def _build_runtime_capability_hint(
        runtime_capability_summary: dict[str, Any] | None,
        *,
        include_knowledge_base_hint: bool = True,
        include_page_context_hint: bool = True,
        include_memory_hint: bool = True,
    ) -> str:
        summary = (
            dict(runtime_capability_summary)
            if isinstance(runtime_capability_summary, dict)
            else {}
        )
        normalized_skill_names: list[str] = []
        for name in summary.get("selected_skill_names") or []:
            text = str(name or "").strip()
            if text and text not in normalized_skill_names:
                normalized_skill_names.append(text)

        context_line = str(summary.get("context_line") or "").strip()
        if not normalized_skill_names and not context_line:
            return ""
        return "\n\n" + render_prompt_contract(
            "turn_capabilities",
            selected_skill_names=", ".join(normalized_skill_names),
            context_line=context_line,
            knowledge_base_hint=(
                include_knowledge_base_hint
                and bool(summary.get("knowledge_base_hint", False))
            ),
            page_context_hint=(
                include_page_context_hint
                and bool(summary.get("page_context_hint", False))
            ),
            memory_hint=(
                include_memory_hint and bool(summary.get("memory_hint", False))
            ),
        )

    @classmethod
    def _build_ordered_capability_hint(
        cls,
        ordered_requested_families: list[str] | None,
        tools: list[ToolDefinition],
        input_variables: dict[str, Any] | None = None,
    ) -> str:
        ordered: list[str] = []
        for family in ordered_requested_families or []:
            normalized = str(family or "").strip()
            if not normalized or normalized == "none" or normalized in ordered:
                continue
            ordered.append(normalized)

        if len(ordered) <= 1:
            return ""

        label_map = {
            "page_ops": "page operations",
            "weather": "weather tools",
            "time_ops": "time tools",
            "web_research": "web research tools",
        }
        sequence_lines: list[str] = []
        for idx, family in enumerate(ordered, start=1):
            label = label_map.get(family, family.replace("_", " "))
            family_tools = cls._allowed_tool_names_for_family(
                family,
                tools,
                input_variables,
            )
            shown_tools = ", ".join(family_tools[:4]) if family_tools else "none"
            suffix = "..." if len(family_tools) > 4 else ""
            sequence_lines.append(f"{idx}. {label} (tools: {shown_tools}{suffix})")

        return "\n\n" + render_prompt_contract(
            "ordered_capability_intent",
            sequence_lines="\n".join(sequence_lines),
        )

    @staticmethod
    def _build_research_continuation_hint(
        continuation: ResearchContinuationContext | None,
    ) -> str:
        if not continuation or not continuation.active:
            return ""
        if continuation.family != "web_research":
            return ""

        target = continuation.research_target_text
        intro = (
            "This turn continues the previous external web research task."
            if continuation.origin == "continuation"
            else "This turn is an external web research task."
        )
        instruction_lines = (
            "\n".join(f"- {text}" for text in continuation.research_instruction_texts)
            if continuation.research_instruction_texts
            else "- (no recent research instructions captured)"
        )
        extra_guidance = (
            "Search-result tool messages in the conversation history are candidate URL lists. "
            "If fetched detail pages is 0 and fetch_url is available, pick candidate URLs from those lists and fetch them before analysis.\n"
            if continuation.fetched_url_count == 0
            else ""
        )
        return "\n\n" + render_prompt_contract(
            "research_state",
            intro=intro,
            target=target or "(same target as previous turn)",
            instruction_lines=instruction_lines,
            recent_queries=(
                ", ".join(continuation.recent_web_queries)
                if continuation.recent_web_queries
                else "(none)"
            ),
            search_query_count=continuation.search_query_count,
            fetched_url_count=continuation.fetched_url_count,
            extra_guidance=extra_guidance.strip(),
        )

    @staticmethod
    def _user_message(content: str) -> ChatMessage:
        """Build user message / 构建 user 消息"""
        return ChatMessage(role="user", content=content)

    @staticmethod
    def _parse_tool_arguments(raw_arguments: Any) -> dict[str, Any]:
        if isinstance(raw_arguments, dict):
            return raw_arguments
        if not isinstance(raw_arguments, str) or not raw_arguments.strip():
            return {}
        try:
            parsed = json.loads(raw_arguments)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @classmethod
    def _tool_call_operation_name(
        cls,
        tool_call: dict[str, Any],
    ) -> str:
        func = tool_call.get("function") or {}
        func_name = str(func.get("name") or tool_call.get("name") or "").strip()
        if func_name.startswith("pageop_"):
            return func_name[len("pageop_") :].strip()
        if func_name == "invoke_page_operation":
            arguments = cls._parse_tool_arguments(func.get("arguments"))
            return str(arguments.get("operation_name") or "").strip()
        return ""

    @classmethod
    def _tool_call_name(cls, tool_call: dict[str, Any]) -> str:
        func = tool_call.get("function") or {}
        return str(func.get("name") or tool_call.get("name") or "").strip()

    @classmethod
    def _truncate_tool_calls_after_navigation(
        cls,
        tool_calls: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], bool]:
        for index, tool_call in enumerate(tool_calls):
            operation_name = cls._tool_call_operation_name(tool_call)
            if operation_name in _PAGE_NAVIGATION_OPERATION_NAMES:
                if index < len(tool_calls) - 1:
                    return tool_calls[: index + 1], True
                return tool_calls, False
        return tool_calls, False

    @classmethod
    def _restrict_tools_to_names(
        cls,
        tools: list[ToolDefinition],
        allowed_names: list[str] | None,
    ) -> list[ToolDefinition]:
        if not allowed_names:
            return tools
        allowed = {str(name).strip() for name in allowed_names if str(name).strip()}
        restricted = [tool for tool in tools if tool.name in allowed]
        return restricted or tools

    @classmethod
    def _build_page_no_progress_recovery(
        cls,
        *,
        messages: list[ChatMessage],
        tool_calls: list[dict[str, Any]],
        tool_results: list[ToolResult],
        tools: list[ToolDefinition],
        input_variables: dict[str, Any] | None,
    ) -> tuple[str | None, list[str], dict[str, Any]]:
        if not tool_calls or not tools or not isinstance(input_variables, dict):
            return None, [], {}

        from app.schemas.ai.agent_chat import PAGE_CONTEXT_KEY

        page_context = input_variables.get(PAGE_CONTEXT_KEY)
        if not isinstance(page_context, dict):
            return None, [], {}

        page_data = page_context.get("page_data")
        if not isinstance(page_data, dict):
            return None, [], {}

        available_operations = page_data.get("available_operations")
        if not isinstance(available_operations, list):
            return None, [], {}

        user_text = cls._extract_last_user_text(messages)
        page_intent_kind = cls._first_page_intent_kind(
            user_text=user_text,
            tools=tools,
            input_variables=input_variables,
        )
        if page_intent_kind in {None, "page_summary"}:
            return None, [], {}

        round_tool_names = [
            cls._tool_call_name(tool_call)
            for tool_call in tool_calls
            if cls._tool_call_name(tool_call)
        ]
        if not round_tool_names:
            return None, [], {}

        repeated_page_context = any(
            result.name == "get_page_context"
            and "Page context was already returned earlier in this turn."
            in str(result.output or "")
            for result in tool_results
        )
        only_page_context_round = set(round_tool_names) == {"get_page_context"}
        if not repeated_page_context and not only_page_context_round:
            return None, [], {}

        recovery_preferences = {
            "page_navigation": [
                "pageop_list_available_menus",
                "pageop_navigate_menu",
                "invoke_page_operation",
            ],
            "page_search": [
                "pageop_search",
                "pageop_clear_search",
                "pageop_refresh_list",
            ],
            "page_pagination": [
                "pageop_go_to_page",
                "pageop_prev_page",
                "pageop_next_page",
                "pageop_set_page_size",
            ],
            "page_row_detail": [
                "pageop_read_row_detail",
                "pageop_read_visible_rows",
            ],
            "page_form_read": [
                "pageop_get_form_state",
                "pageop_get_form_options",
            ],
            "page_form_write": [
                "pageop_create_record",
                "pageop_edit_record",
                "pageop_fill_form",
                "pageop_validate_form",
                "pageop_submit_form",
            ],
            "page_screenshot": [
                "pageop_capture_screenshot",
                "invoke_page_operation",
            ],
            "page_editor_read": [
                "pageop_get_editor_html",
                "pageop_get_editor_text",
            ],
            "page_editor_write": [
                "pageop_replace_content",
                "pageop_replace_section",
                "pageop_append_content",
                "pageop_insert_content",
                "pageop_update_title",
            ],
        }
        preferred_tool_names = [
            name
            for name in recovery_preferences.get(page_intent_kind, [])
            if any(tool.name == name for tool in tools)
        ]
        if not preferred_tool_names:
            return None, [], {}

        page_key = str(page_context.get("page_key") or "").strip()
        recovery_reason = (
            "repeated_get_page_context"
            if repeated_page_context
            else "page_context_only_round"
        )
        hint = render_prompt_contract("page_flow_recovery")
        return (
            hint,
            preferred_tool_names,
            {
                "reason": recovery_reason,
                "intent_kind": page_intent_kind,
                "current_page_key": page_key,
                "preferred_tool_names": preferred_tool_names,
                "round_tool_names": round_tool_names,
            },
        )

    @classmethod
    def _extract_recent_successful_tool_names(
        cls,
        messages: list[ChatMessage],
        *,
        limit: int = 12,
    ) -> list[str]:
        names: list[str] = []
        seen: set[str] = set()

        for msg in reversed(messages):
            if msg.role != "assistant" or not msg.tool_calls:
                continue

            for tc in reversed(msg.tool_calls):
                if tc.get("success") is not True:
                    continue
                func = tc.get("function") or {}
                tool_name = str(func.get("name") or tc.get("name") or "").strip()
                if not tool_name or tool_name in seen:
                    continue
                names.append(tool_name)
                seen.add(tool_name)
                if len(names) >= limit:
                    return names

        return names

    @classmethod
    def _extract_recent_web_queries(
        cls,
        messages: list[ChatMessage],
        *,
        limit: int = 5,
    ) -> list[str]:
        queries: list[str] = []
        seen: set[str] = set()

        for msg in reversed(messages):
            if msg.role != "assistant" or not msg.tool_calls:
                continue

            for tc in reversed(msg.tool_calls):
                if tc.get("success") is not True:
                    continue
                func = tc.get("function") or {}
                tool_name = str(func.get("name") or tc.get("name") or "").strip()
                if tool_name != "web_search":
                    continue
                arguments = cls._parse_tool_arguments(func.get("arguments"))
                query = str(arguments.get("query") or "").strip()
                if not query or query in seen:
                    continue
                queries.append(query)
                seen.add(query)
                if len(queries) >= limit:
                    return queries

        return queries

    @classmethod
    def _collect_web_research_evidence(
        cls,
        messages: list[ChatMessage],
    ) -> tuple[list[str], list[str]]:
        search_queries: list[str] = []
        fetched_urls: list[str] = []
        seen_queries: set[str] = set()
        seen_urls: set[str] = set()

        for msg in messages:
            if msg.role != "assistant" or not msg.tool_calls:
                continue

            for tc in msg.tool_calls:
                if tc.get("success") is not True:
                    continue
                func = tc.get("function") or {}
                tool_name = str(func.get("name") or tc.get("name") or "").strip()
                arguments = cls._parse_tool_arguments(func.get("arguments"))
                if tool_name == "web_search":
                    query = str(arguments.get("query") or "").strip()
                    if query and query not in seen_queries:
                        search_queries.append(query)
                        seen_queries.add(query)
                elif tool_name == "fetch_url":
                    url = str(arguments.get("url") or "").strip()
                    if url and url not in seen_urls:
                        fetched_urls.append(url)
                        seen_urls.add(url)

        return search_queries, fetched_urls

    @classmethod
    def _needs_fetch_url_before_summary(cls, messages: list[ChatMessage]) -> bool:
        """
        True when web_search succeeded but fetch_url has not been attempted yet.
        已成功 web_search 且尚未尝试 fetch_url（无论成功与否）时为 True。
        """
        has_success_search_with_candidates = False
        fetch_attempted = False
        for msg in messages:
            if msg.role != "assistant" or not msg.tool_calls:
                continue
            for tc in msg.tool_calls:
                func = tc.get("function") or {}
                name = str(func.get("name") or tc.get("name") or "").strip()
                if name == "web_search" and tc.get("success") is True:
                    payload = tc.get("summary_payload")
                    payload = payload if isinstance(payload, dict) else {}
                    items = payload.get("items")
                    candidate_urls = [
                        str(item.get("url") or "").strip()
                        for item in items
                        if isinstance(item, dict) and str(item.get("url") or "").strip()
                    ] if isinstance(items, list) else []
                    raw_count = payload.get("result_count")
                    try:
                        result_count = int(raw_count) if raw_count is not None else None
                    except (TypeError, ValueError):
                        result_count = None
                    if result_count is None:
                        result_count = len(candidate_urls)
                    if result_count > 0 and candidate_urls:
                        has_success_search_with_candidates = True
                if name == "fetch_url":
                    fetch_attempted = True
        return bool(has_success_search_with_candidates and not fetch_attempted)

    @classmethod
    def _apply_fetch_url_only_gate(
        cls,
        messages: list[ChatMessage],
        tools: list[ToolDefinition],
        all_tools: list[ToolDefinition] | None,
    ) -> list[ToolDefinition]:
        """Narrow tool list to fetch_url only until a fetch attempt is made."""
        if not cls._needs_fetch_url_before_summary(messages):
            return tools
        fetch_defs = [t for t in (all_tools or tools) if t.name == "fetch_url"]
        return fetch_defs if fetch_defs else tools

    @classmethod
    def _extract_last_user_text(
        cls,
        messages: list[ChatMessage],
    ) -> str:
        for msg in reversed(messages):
            if msg.role != "user":
                continue
            text = (msg.content or "").strip()
            if not text:
                continue
            return text
        return ""

    @classmethod
    def _extract_recent_research_instruction_texts(
        cls,
        prior_messages: list[ChatMessage],
        current_user_text: str,
        *,
        limit: int = 3,
    ) -> list[str]:
        texts: list[str] = []
        if current_user_text:
            texts.append(current_user_text)

        for msg in reversed(prior_messages):
            if msg.role != "user":
                continue
            text = (msg.content or "").strip()
            if not text or text in texts:
                continue
            texts.append(text)
            if len(texts) >= limit:
                break

        return list(reversed(texts))

    @staticmethod
    def _truncate_preview(text: str, *, max_chars: int = 280) -> str:
        value = " ".join((text or "").split())
        if len(value) <= max_chars:
            return value
        return f"{value[: max_chars - 3]}..."

    @staticmethod
    def _has_page_context(input_variables: dict[str, Any] | None) -> bool:
        from app.ai.tools.semantic_defaults import _has_page_context

        return _has_page_context(input_variables)

    @staticmethod
    def _page_operation_names_from_input_variables(
        input_variables: dict[str, Any] | None,
    ) -> list[str]:
        if not isinstance(input_variables, dict):
            return []
        from app.schemas.ai.agent_chat import PAGE_CONTEXT_KEY

        page_context = input_variables.get(PAGE_CONTEXT_KEY)
        if not isinstance(page_context, dict):
            return []
        page_data = page_context.get("page_data")
        raw_operations = (
            page_data.get("available_operations")
            if isinstance(page_data, dict)
            else page_context.get("available_operations")
        )
        if not isinstance(raw_operations, list):
            return []
        operation_names: list[str] = []
        for item in raw_operations:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if name and name not in operation_names:
                operation_names.append(name)
        return operation_names

    @staticmethod
    def _stable_unique_text_list(values: list[Any]) -> list[str]:
        normalized: list[str] = []
        for value in values:
            text = str(value or "").strip()
            if text and text not in normalized:
                normalized.append(text)
        return normalized

    @classmethod
    def _extract_latest_turn_runtime_facts(
        cls,
        messages: list[ChatMessage],
    ) -> dict[str, Any]:
        facts: dict[str, Any] = {
            "last_tool_name": "",
            "last_page_key": "",
            "last_page_op": "",
            "active_intent_kind": None,
        }

        def _candidate_dicts(message: ChatMessage) -> list[dict[str, Any]]:
            metadata = dict(message.metadata or {}) if isinstance(message.metadata, dict) else {}
            candidates = [metadata]
            for key in ("turn_record", "context_diagnostics", "last_run_summary"):
                value = metadata.get(key)
                if isinstance(value, dict):
                    candidates.append(dict(value))
            turn_record = metadata.get("turn_record")
            if isinstance(turn_record, dict):
                turn_record_metadata = turn_record.get("metadata")
                if isinstance(turn_record_metadata, dict):
                    candidates.append(dict(turn_record_metadata))
                    diagnostics = turn_record_metadata.get("turn_diagnostics")
                    if isinstance(diagnostics, dict):
                        candidates.append(dict(diagnostics))
            return candidates

        for message in reversed(messages):
            if message.role != "assistant":
                continue

            if not facts["active_intent_kind"]:
                for candidate in _candidate_dicts(message):
                    tool_planner = candidate.get("tool_planner")
                    if isinstance(tool_planner, dict):
                        intent_kind = str(tool_planner.get("intent") or "").strip()
                        if intent_kind:
                            facts["active_intent_kind"] = intent_kind
                            break
                    intent_kind = str(candidate.get("active_intent_kind") or "").strip()
                    if intent_kind:
                        facts["active_intent_kind"] = intent_kind
                        break

            for tool_call in reversed(message.tool_calls or []):
                if tool_call.get("success") is not True:
                    continue
                if not facts["last_tool_name"]:
                    facts["last_tool_name"] = cls._tool_call_name(tool_call)
                if not facts["last_page_op"]:
                    facts["last_page_op"] = cls._tool_call_operation_name(tool_call)
                if not facts["last_page_key"]:
                    arguments = cls._parse_tool_arguments(
                        (tool_call.get("function") or {}).get("arguments")
                    )
                    facts["last_page_key"] = str(
                        arguments.get("page_key") or ""
                    ).strip()
                if (
                    facts["last_tool_name"]
                    and facts["last_page_op"]
                    and facts["last_page_key"]
                    and facts["active_intent_kind"]
                ):
                    return facts
            if facts["last_tool_name"] and facts["active_intent_kind"]:
                return facts

        return facts

    @classmethod
    def _tool_family_for_name(
        cls,
        tool_name: str,
        input_variables: dict[str, Any] | None = None,
    ) -> str:
        return _tool_family_from_name_unified(tool_name, input_variables)

    @classmethod
    def _messages_have_blocking_pending_interaction(
        cls,
        messages: list[ChatMessage],
    ) -> bool:
        """pending consent/confirmation must not be overridden by multi-family narrowing."""
        tail = messages[-8:] if len(messages) > 8 else messages
        for message in reversed(tail):
            meta = message.metadata or {}
            pc = meta.get("pending_consent")
            if isinstance(pc, dict) and not pc.get("resolved"):
                return True
            pconf = meta.get("pending_confirmation")
            if isinstance(pconf, dict) and not pconf.get("resolved"):
                return True
            for tc in message.tool_calls or []:
                if isinstance(tc.get("pending_consent"), dict) and not tc[
                    "pending_consent"
                ].get("resolved"):
                    return True
                if isinstance(tc.get("pending_confirmation"), dict) and not tc[
                    "pending_confirmation"
                ].get("resolved"):
                    return True
        return False

    @classmethod
    def _first_incomplete_requested_family(
        cls,
        ordered_requested_families: list[str],
        completed_families: set[str],
    ) -> str | None:
        for fam in ordered_requested_families:
            if fam not in completed_families:
                return fam
        return None

    @classmethod
    def _mark_multi_family_progress(
        cls,
        *,
        func_name: str,
        success: bool,
        ordered_requested_families: list[str],
        completed_families: set[str],
        has_fetch_url_in_toolset: bool,
        input_variables: dict[str, Any] | None,
    ) -> None:
        if not success:
            return
        fam = cls._tool_family_for_name(func_name, input_variables)
        if fam == "web_research":
            if func_name == "fetch_url" or (
                func_name == "web_search" and not has_fetch_url_in_toolset
            ):
                completed_families.add("web_research")
            return
        if fam in ordered_requested_families:
            completed_families.add(fam)

    @classmethod
    def _tool_semantic_family(
        cls,
        tool: ToolDefinition,
        input_variables: dict[str, Any] | None = None,
    ) -> str:
        return _tool_semantic_family_unified(tool, input_variables)

    @classmethod
    def _tool_semantic_tags(cls, tool: ToolDefinition) -> list[str]:
        return _tool_semantic_tags_unified(tool)

    @classmethod
    def _family_capability_terms(
        cls,
        family: str,
        tools: list[ToolDefinition],
        input_variables: dict[str, Any] | None = None,
    ) -> set[str]:
        from app.ai.tools.optimizer import _tokenize

        terms: set[str] = set()
        for hint in _SEMANTIC_FAMILY_HINT_TAGS.get(family, ()):
            normalized_hint = hint.strip().lower()
            if len(normalized_hint) >= 2:
                terms.add(normalized_hint)
            terms |= {token for token in _tokenize(hint) if len(token) >= 2}

        for tool in tools:
            if cls._tool_semantic_family(tool, input_variables) != family:
                continue
            for value in [
                tool.name,
                tool.description or "",
                *cls._tool_semantic_tags(tool),
            ]:
                text = str(value or "").strip().lower()
                if len(text) >= 2:
                    terms.add(text)
                terms |= {token for token in _tokenize(text) if len(token) >= 2}
        return terms

    @classmethod
    def _response_denies_family_capability(
        cls,
        *,
        normalized_text: str,
        family: str,
        tools: list[ToolDefinition],
        input_variables: dict[str, Any] | None,
    ) -> bool:
        if not has_capability_denial_phrase(normalized_text):
            return False

        capability_terms = cls._family_capability_terms(
            family,
            tools,
            input_variables,
        )
        return any(term in normalized_text for term in capability_terms)

    @classmethod
    def _extract_textual_tool_call_names(
        cls,
        response_text: str,
        tools: list[ToolDefinition],
    ) -> list[str]:
        """
        Detect leaked textual tool-call markers like ``to=functions.get_page_context``.
        / 识别被模型当文本吐出的伪工具调用标记，例如 ``to=functions.get_page_context``。
        """
        text = " ".join((response_text or "").strip().split())
        if not text:
            return []

        known_tool_names = {tool.name for tool in tools} if tools else None
        tool_aliases: dict[str, str] = {}
        for tool in tools or []:
            tool_aliases[tool.name] = tool.name
            underlying_operation = str(
                (tool.config or {}).get("underlying_operation") or ""
            ).strip()
            if underlying_operation:
                tool_aliases[underlying_operation] = tool.name
        return extract_textual_tool_call_names_from_text(
            text,
            alias_to_tool_name=tool_aliases,
            known_tool_names=known_tool_names,
        )

    @classmethod
    def _looks_like_tool_planning_leak(
        cls,
        response_text: str,
        tools: list[ToolDefinition],
    ) -> bool:
        text = " ".join((response_text or "").strip().split())
        if not text:
            return False
        if not has_tool_planning_leak_phrase(text):
            return False
        return bool(cls._extract_textual_tool_call_names(text, tools))

    @staticmethod
    def _detect_requested_turn_intents(
        user_text: str,
        *,
        tools: list[ToolDefinition],
        input_variables: dict[str, Any] | None,
    ) -> list[str]:
        intents: list[str] = []
        normalized = (user_text or "").strip()
        if not normalized:
            return intents

        tool_names = {tool.name for tool in tools}
        has_web_tools = {"web_search", "fetch_url"} <= tool_names
        has_weather_tools = any(
            _tool_semantic_family_unified(tool, input_variables) == "weather"
            for tool in tools
        )
        has_page_tools = bool(
            BaseEngine._has_page_context(input_variables)
            or {"get_page_context", "invoke_page_operation"} & tool_names
        )

        if mentions_weather(normalized) and (has_weather_tools or has_web_tools):
            intents.append("weather")
        if mentions_rail_ticket(normalized) and has_web_tools:
            intents.append("rail_ticket_research")
        if mentions_page_summary(normalized) and has_page_tools:
            intents.append("page_summary")
        return intents

    @classmethod
    def _collect_completed_turn_intents(
        cls,
        messages: list[ChatMessage],
        *,
        tools: list[ToolDefinition],
        input_variables: dict[str, Any] | None,
    ) -> set[str]:
        completed: set[str] = set()
        successful_tool_names = set(
            cls._extract_recent_successful_tool_names(messages, limit=50)
        )
        successful_queries, fetched_urls = cls._collect_web_research_evidence(messages)
        weather_tool_names = {
            tool.name
            for tool in tools
            if cls._tool_semantic_family(tool, input_variables) == "weather"
        }

        if successful_tool_names & (
            weather_tool_names | {"get_current_weather", "get_weather_forecast"}
        ):
            completed.add("weather")
        if any(
            any(
                token in url.lower()
                for token in ("weather", "cma.cn", "qweather", "weather.com")
            )
            for url in fetched_urls
        ):
            completed.add("weather")

        if "get_page_context" in successful_tool_names or any(
            name.startswith("pageop_") for name in successful_tool_names
        ):
            completed.add("page_summary")

        rail_search_seen = any(
            mentions_rail_ticket(query) for query in successful_queries
        )
        rail_fetch_seen = any(
            any(
                token in url.lower()
                for token in ("12306", "gaotie", "huoche", "trains")
            )
            for url in fetched_urls
        )
        if rail_fetch_seen or (rail_search_seen and rail_fetch_seen):
            completed.add("rail_ticket_research")

        return completed

    @classmethod
    def _build_post_tool_retry_policy(
        cls,
        *,
        breach_type: str,
        tools: list[ToolDefinition],
        input_variables: dict[str, Any] | None,
        current_policy: ToolUsePolicy,
        leaked_tool_names: list[str] | None = None,
        unfinished_intents: list[str] | None = None,
    ) -> ToolUsePolicy | None:
        families: list[str] = []

        for tool_name in leaked_tool_names or []:
            family = cls._tool_family_for_name(tool_name, input_variables)
            if family != "none" and family not in families:
                families.append(family)

        for intent in unfinished_intents or []:
            if intent == "page_summary":
                family = "page_ops"
            elif intent in {"weather", "rail_ticket_research"}:
                if (
                    any(
                        cls._tool_semantic_family(tool, input_variables) == "weather"
                        for tool in tools
                    )
                    and intent == "weather"
                ):
                    family = "weather"
                else:
                    family = "web_research"
            else:
                family = "none"
            if family != "none" and family not in families:
                families.append(family)

        if not families and current_policy.family != "none":
            families.append(current_policy.family)
        if not families:
            return None

        allowed_names = cls._allowed_tool_names_for_families(
            families,
            tools,
            input_variables,
        )
        if not allowed_names:
            return None

        reason_suffix_parts = [
            *(unfinished_intents or []),
            *(leaked_tool_names or []),
        ]
        return ToolUsePolicy(
            family=families[0],
            mode="required",
            allowed_tool_names=allowed_names,
            retry_on_contract_breach=False,
            reason=f"{breach_type}:{','.join(reason_suffix_parts)}",
        )

    @classmethod
    def _analyze_post_tool_contract_breach(
        cls,
        *,
        messages: list[ChatMessage],
        response: ChatResponse,
        current_policy: ToolUsePolicy,
        tools: list[ToolDefinition],
        input_variables: dict[str, Any] | None,
    ) -> tuple[str | None, ToolUsePolicy | None, dict[str, Any]]:
        if response.tool_calls:
            return None, None, {}

        response_text = (response.message.content or "").strip()
        if not response_text:
            return None, None, {}

        leaked_tool_names = cls._extract_textual_tool_call_names(response_text, tools)
        planning_leak = cls._looks_like_tool_planning_leak(response_text, tools)
        user_text = cls._extract_last_user_text(messages)
        requested_intents = cls._detect_requested_turn_intents(
            user_text,
            tools=tools,
            input_variables=input_variables,
        )
        completed_intents = cls._collect_completed_turn_intents(
            messages,
            tools=tools,
            input_variables=input_variables,
        )
        unfinished_intents = [
            intent for intent in requested_intents if intent not in completed_intents
        ]

        if leaked_tool_names or planning_leak:
            return (
                "assistant_claimed_tool_call_without_tool_event",
                cls._build_post_tool_retry_policy(
                    breach_type="assistant_claimed_tool_call_without_tool_event",
                    tools=tools,
                    input_variables=input_variables,
                    current_policy=current_policy,
                    leaked_tool_names=leaked_tool_names,
                    unfinished_intents=unfinished_intents,
                ),
                {
                    "tool_leak_detected": True,
                    "assistant_claimed_tool_call_without_tool_event": True,
                    "leaked_tool_names": leaked_tool_names,
                    "requested_intents": requested_intents,
                    "completed_intents": sorted(completed_intents),
                    "unfinished_intents": unfinished_intents,
                },
            )

        if unfinished_intents:
            return (
                "unfinished_multi_intent_reply",
                cls._build_post_tool_retry_policy(
                    breach_type="unfinished_multi_intent_reply",
                    tools=tools,
                    input_variables=input_variables,
                    current_policy=current_policy,
                    unfinished_intents=unfinished_intents,
                ),
                {
                    "tool_leak_detected": False,
                    "leaked_tool_names": [],
                    "requested_intents": requested_intents,
                    "completed_intents": sorted(completed_intents),
                    "unfinished_intents": unfinished_intents,
                },
            )

        return (
            None,
            None,
            {
                "tool_leak_detected": False,
                "assistant_claimed_tool_call_without_tool_event": False,
                "leaked_tool_names": [],
                "requested_intents": requested_intents,
                "completed_intents": sorted(completed_intents),
                "unfinished_intents": [],
            },
        )

    @staticmethod
    def _build_contract_recovery_system_message(
        *,
        breach_type: str,
        diagnostics: dict[str, Any],
    ) -> ChatMessage:
        leaked_tool_names = diagnostics.get("leaked_tool_names") or []
        unfinished_intents = diagnostics.get("unfinished_intents") or []
        completed_intents = diagnostics.get("completed_intents") or []
        breach_guidance = ""
        if breach_type in {
            "leaked_textual_tool_call",
            "assistant_claimed_tool_call_without_tool_event",
        }:
            breach_guidance = (
                render_prompt_contract("contract_recovery_leak_guidance") + "\n"
            )
        unfinished_line = ""
        if unfinished_intents:
            unfinished_line = f"Unfinished requested intents: {', '.join(str(item) for item in unfinished_intents)}.\n"
        completed_line = ""
        if completed_intents:
            completed_line = (
                "Already completed intents with real tool evidence: "
                f"{', '.join(str(item) for item in completed_intents)}.\n"
            )
        leaked_line = ""
        if leaked_tool_names:
            leaked_line = (
                "Leaked tool names or tool-output markers detected: "
                f"{', '.join(str(item) for item in leaked_tool_names)}.\n"
            )
        return ChatMessage(
            role="system",
            content=render_prompt_contract(
                "contract_recovery",
                breach_guidance=breach_guidance,
                unfinished_line=unfinished_line,
                completed_line=completed_line,
                leaked_line=leaked_line,
            ),
        )

    @staticmethod
    def _merge_contract_diagnostics_into_turn_record(
        turn_record: TurnRecord | dict[str, Any] | None,
        *,
        breach_type: str | None,
        diagnostics: dict[str, Any],
        recovered_via_retry: bool,
    ) -> TurnRecord | dict[str, Any] | None:
        if not breach_type and not diagnostics:
            return turn_record

        if turn_record is None:
            turn_record = TurnRecord()

        if isinstance(turn_record, dict):
            metadata = (
                dict(turn_record.get("metadata") or {})
                if isinstance(turn_record.get("metadata"), dict)
                else {}
            )
            turn_record["metadata"] = metadata
        else:
            metadata = (
                dict(getattr(turn_record, "metadata", {}) or {})
                if isinstance(getattr(turn_record, "metadata", {}), dict)
                else {}
            )
            turn_record.metadata = metadata

        if breach_type:
            metadata["contract_breach_type"] = breach_type
        metadata["tool_leak_detected"] = bool(diagnostics.get("tool_leak_detected"))
        metadata["assistant_claimed_tool_call_without_tool_event"] = bool(
            diagnostics.get("assistant_claimed_tool_call_without_tool_event")
        )
        metadata["unfinished_intents"] = list(
            diagnostics.get("unfinished_intents") or []
        )
        metadata["recovered_via_retry"] = bool(recovered_via_retry)
        leaked_tool_names = list(diagnostics.get("leaked_tool_names") or [])
        if leaked_tool_names:
            metadata["leaked_tool_names"] = leaked_tool_names
        return turn_record

    @staticmethod
    def _looks_like_generic_follow_up(user_text: str) -> bool:
        """Short continuation turns without a new detailed question."""
        raw = (user_text or "").strip()
        if not raw:
            return False
        if "?" in raw or "？" in raw:
            return False
        if has_question_indicator(raw):
            return False
        normalized = " ".join(raw.lower().split())
        if len(normalized) <= 24:
            return True
        return len(normalized) <= 44 and len(normalized.split()) <= 6

    @classmethod
    def _allowed_tool_names_for_family(
        cls,
        family: str,
        tools: list[ToolDefinition],
        input_variables: dict[str, Any] | None = None,
    ) -> list[str]:
        if family == "none":
            return [tool.name for tool in tools]

        allowed: list[str] = []
        for tool in tools:
            name = tool.name
            semantic_family = cls._tool_semantic_family(tool, input_variables)
            if semantic_family == family:
                allowed.append(name)
                continue

            if family == "web_research" and name in {
                "get_page_context",
                "invoke_page_operation",
            }:
                allowed.append(name)

        return allowed or [tool.name for tool in tools]

    @classmethod
    def _allowed_tool_names_for_families(
        cls,
        families: list[str],
        tools: list[ToolDefinition],
        input_variables: dict[str, Any] | None = None,
    ) -> list[str]:
        ordered: list[str] = []
        for family in families:
            normalized = str(family or "").strip()
            if not normalized or normalized == "none":
                continue
            for name in cls._allowed_tool_names_for_family(
                normalized,
                tools,
                input_variables,
            ):
                if name not in ordered:
                    ordered.append(name)
        return ordered

    @staticmethod
    def _filter_tools_for_policy(
        tools: list[ToolDefinition],
        policy: ToolUsePolicy,
    ) -> list[ToolDefinition]:
        if not tools or not policy.allowed_tool_names:
            return tools
        allowed = set(policy.allowed_tool_names)
        filtered = [tool for tool in tools if tool.name in allowed]
        return filtered or tools

    @staticmethod
    def _restore_explicit_family_tools(
        *,
        selected_tools: list[ToolDefinition],
        all_tools: list[ToolDefinition],
        policy: ToolUsePolicy,
    ) -> tuple[list[ToolDefinition], bool]:
        if policy.family == "none" or not policy.allowed_tool_names or not all_tools:
            return selected_tools, False

        allowed = set(policy.allowed_tool_names)
        if any(tool.name in allowed for tool in selected_tools):
            return selected_tools, False

        restored = [tool for tool in all_tools if tool.name in allowed]
        if restored:
            return restored, True
        return selected_tools, False

    @classmethod
    def _ensure_explicit_family_coverage(
        cls,
        *,
        selected_tools: list[ToolDefinition],
        all_tools: list[ToolDefinition],
        explicit_requested_families: list[str],
        input_variables: dict[str, Any] | None = None,
    ) -> tuple[list[ToolDefinition], list[str]]:
        ordered_families: list[str] = []
        for family in explicit_requested_families:
            normalized = str(family or "").strip()
            if not normalized or normalized == "none" or normalized in ordered_families:
                continue
            ordered_families.append(normalized)
        if len(ordered_families) <= 1:
            return selected_tools, []

        selected_names = {tool.name for tool in selected_tools}
        selected_by_family: set[str] = set()
        for tool in selected_tools:
            family = cls._tool_semantic_family(tool, input_variables)
            if family:
                selected_by_family.add(family)

        missing_families = [
            family for family in ordered_families if family not in selected_by_family
        ]
        if not missing_families:
            return selected_tools, []

        restored = list(selected_tools)
        restored_families: list[str] = []
        for family in missing_families:
            candidates = cls._allowed_tool_names_for_family(
                family,
                all_tools,
                input_variables,
            )
            restored_any = False
            for name in candidates:
                if name in selected_names:
                    continue
                candidate = next(
                    (tool for tool in all_tools if tool.name == name), None
                )
                if candidate is None:
                    continue
                restored.append(candidate)
                selected_names.add(name)
                restored_any = True
                break
            if restored_any:
                restored_families.append(family)

        return restored, restored_families

    @staticmethod
    def _ensure_web_research_tool_pair(
        *,
        selected_tools: list[ToolDefinition],
        all_tools: list[ToolDefinition],
        explicit_requested_families: list[str],
        policy: ToolUsePolicy,
    ) -> tuple[list[ToolDefinition], bool]:
        """
        Keep ``web_search`` and ``fetch_url`` together when web research is in play.
        当本轮涉及联网检索时，保证 ``web_search`` 与 ``fetch_url`` 成对保留。
        """
        if not selected_tools or not all_tools:
            return selected_tools, False

        explicit_families = {
            str(family or "").strip() for family in explicit_requested_families
        }
        selected_names = {tool.name for tool in selected_tools}
        all_by_name = {tool.name: tool for tool in all_tools}
        has_web_pair_available = {"web_search", "fetch_url"} <= set(all_by_name)
        if not has_web_pair_available:
            return selected_tools, False

        web_research_active = (
            policy.family == "web_research"
            or "web_research" in explicit_families
            or bool({"web_search", "fetch_url"} & selected_names)
        )
        if not web_research_active:
            return selected_tools, False

        restored = list(selected_tools)
        restored_any = False
        for tool_name in ("web_search", "fetch_url"):
            if tool_name in selected_names:
                continue
            candidate = all_by_name.get(tool_name)
            if candidate is None:
                continue
            restored.append(candidate)
            selected_names.add(tool_name)
            restored_any = True

        return restored, restored_any

    @classmethod
    def _looks_like_explicit_web_research_request(
        cls,
        user_text: str,
        tools: list[ToolDefinition],
    ) -> bool:
        if not user_text or not tools:
            return False
        web_tools = [
            tool
            for tool in tools
            if cls._tool_semantic_family(tool) == "web_research"
            or tool.name in {"web_search", "fetch_url"}
        ]
        if not web_tools:
            return False

        from app.ai.tools.optimizer import (
            _tokenize,
        )

        query_text = user_text.lower()
        query_tokens = _tokenize(user_text)
        semantic_tokens: set[str] = set()
        for tool in web_tools:
            semantic_source = " ".join(
                [
                    tool.name,
                    tool.description or "",
                    *cls._tool_semantic_tags(tool),
                ]
            )
            semantic_tokens |= _tokenize(semantic_source)

        if query_tokens & semantic_tokens:
            return True

        return any(
            tool.name.lower() in query_text
            or tool.name.lower().replace("_", " ") in query_text
            for tool in web_tools
        )

    @classmethod
    def _first_page_intent_kind(
        cls,
        *,
        user_text: str,
        tools: list[ToolDefinition],
        input_variables: dict[str, Any] | None = None,
    ) -> str | None:
        intents = IntentPlanner.plan_turn(
            messages=[ChatMessage(role="user", content=user_text)],
            tools=tools,
            input_variables=input_variables,
            continuation_context=None,
            capability_bundle=None,
        )
        for intent in intents:
            if intent.family == "page_ops":
                return intent.kind
        return None

    @classmethod
    def _looks_like_generic_page_summary_request(
        cls,
        user_text: str,
        tools: list[ToolDefinition],
        input_variables: dict[str, Any] | None = None,
    ) -> bool:
        """
        Detect lightweight page-summary requests that do not need extra page operations.
        识别“概括当前页面内容”的轻量请求，此类请求通常不需要额外 page operation。
        """
        normalized = (user_text or "").strip()
        if not normalized:
            return False
        page_intent_kind = cls._first_page_intent_kind(
            user_text=normalized,
            tools=tools,
            input_variables=input_variables,
        )
        if page_intent_kind != "page_summary":
            return False
        if mentions_page_detail_operation(normalized):
            return False
        return bool(
            cls._has_page_context(input_variables)
            or any(tool.name == "get_page_context" for tool in tools)
        )

    @classmethod
    def _restrict_page_tools_for_generic_summary(
        cls,
        *,
        selected_tools: list[ToolDefinition],
        all_tools: list[ToolDefinition],
        user_text: str,
        input_variables: dict[str, Any] | None = None,
    ) -> tuple[list[ToolDefinition], bool]:
        """
        Keep generic page-summary turns on ``get_page_context`` instead of heavy page ops.
        对泛化页面总结请求，优先使用 ``get_page_context``，避免触发较重的页面操作工具。
        """
        if not cls._looks_like_generic_page_summary_request(
            user_text,
            all_tools,
            input_variables,
        ):
            return selected_tools, False

        page_context_tool = next(
            (tool for tool in all_tools if tool.name == "get_page_context"),
            None,
        )
        if page_context_tool is None:
            return selected_tools, False

        restricted: list[ToolDefinition] = []
        seen_names: set[str] = set()
        for tool in selected_tools:
            if tool.name == "get_page_context":
                if tool.name not in seen_names:
                    restricted.append(tool)
                    seen_names.add(tool.name)
                continue

            semantic_family = cls._tool_semantic_family(tool, input_variables)
            if semantic_family == "page_ops" or tool.name.startswith("pageop_"):
                continue

            if tool.name not in seen_names:
                restricted.append(tool)
                seen_names.add(tool.name)

        if "get_page_context" not in seen_names:
            restricted.append(page_context_tool)

        restricted_names = [tool.name for tool in restricted]
        selected_names = [tool.name for tool in selected_tools]
        return restricted, restricted_names != selected_names

    @classmethod
    def _looks_like_explicit_time_request(
        cls,
        user_text: str,
        tools: list[ToolDefinition],
    ) -> bool:
        if not user_text or not tools:
            return False
        time_tools = [
            tool
            for tool in tools
            if cls._tool_semantic_family(tool) == "time_ops"
            or tool.name == "get_current_time"
        ]
        if not time_tools:
            return False
        from app.ai.tools.optimizer import _tokenize

        query_tokens = _tokenize(user_text)
        semantic_tokens: set[str] = set()
        for tool in time_tools:
            semantic_source = " ".join(
                [
                    tool.name,
                    tool.description or "",
                    *cls._tool_semantic_tags(tool),
                ]
            )
            semantic_tokens |= _tokenize(semantic_source)
        return bool(query_tokens & semantic_tokens)

    def _log_tool_selection_status(
        self,
        *,
        status: str,
        agent: Agent,
        conversation_id: int | None,
        current_user_text: str,
        family: str,
        all_tool_names: list[str],
        selected_tool_names: list[str],
        page_context_present: bool,
        optimizer_total: int,
        optimizer_selected: int,
    ) -> None:
        logger.warning(
            "Tool selection status: status={} runtime={} agent_id={} conversation_id={} family={} current_user_text={} all_tool_names={} selected_tool_names={} page_context_present={} optimizer_total={} optimizer_selected={}",
            status,
            get_runtime_identity_tag(),
            getattr(agent, "id", None),
            conversation_id,
            family,
            self._truncate_preview(current_user_text),
            all_tool_names,
            selected_tool_names,
            page_context_present,
            optimizer_total,
            optimizer_selected,
        )

    @classmethod
    def _ordered_requested_families_from_intents(
        cls,
        *,
        intents: list[IntentPlan],
    ) -> list[str]:
        ordered: list[str] = []
        for intent in intents:
            family = str(intent.family or "").strip()
            if not family or family == "none" or family in ordered:
                continue
            ordered.append(family)
        return ordered

    @classmethod
    def _build_required_policy_for_family(
        cls,
        family: str,
        tools: list[ToolDefinition],
        input_variables: dict[str, Any] | None,
        reason: str,
    ) -> ToolUsePolicy:
        return ToolUsePolicy(
            family=family,
            mode="required",
            allowed_tool_names=cls._allowed_tool_names_for_family(
                family,
                tools,
                input_variables,
            ),
            retry_on_contract_breach=False,
            reason=reason,
        )

    @classmethod
    def _resolve_breach_retry_policy(
        cls,
        *,
        response_text: str,
        tools: list[ToolDefinition],
        current_policy: ToolUsePolicy,
        input_variables: dict[str, Any] | None,
    ) -> ToolUsePolicy | None:
        if not tools:
            return None

        normalized = " ".join((response_text or "").strip().lower().split())
        if not normalized:
            return None

        leaked_tool_names = cls._extract_textual_tool_call_names(
            response_text,
            tools,
        )
        for tool_name in leaked_tool_names:
            family = cls._tool_family_for_name(tool_name, input_variables)
            if family == "none" and current_policy.family != "none":
                family = current_policy.family
            allowed_names = cls._allowed_tool_names_for_family(
                family,
                tools,
                input_variables,
            )
            if allowed_names:
                return cls._build_required_policy_for_family(
                    family,
                    tools,
                    input_variables,
                    reason=f"textual_tool_call_leak:{tool_name}",
                )

        if current_policy.mode == "required" and current_policy.family != "none":
            return cls._build_required_policy_for_family(
                current_policy.family,
                tools,
                input_variables,
                reason=f"required_retry:{current_policy.reason or current_policy.family}",
            )

        if current_policy.family != "none" and current_policy.allowed_tool_names:
            return cls._build_required_policy_for_family(
                current_policy.family,
                tools,
                input_variables,
                reason=f"capability_denial:{current_policy.family}",
            )

        for family in ("web_research", "weather", "time_ops", "page_ops"):
            if not cls._response_denies_family_capability(
                normalized_text=normalized,
                family=family,
                tools=tools,
                input_variables=input_variables,
            ):
                continue
            allowed_names = cls._allowed_tool_names_for_family(
                family,
                tools,
                input_variables,
            )
            if allowed_names:
                return cls._build_required_policy_for_family(
                    family,
                    tools,
                    input_variables,
                    reason=f"capability_denial:{family}",
                )
        return None

    @classmethod
    def _should_retry_tool_contract_breach(
        cls,
        *,
        response: ChatResponse,
        current_policy: ToolUsePolicy,
        tools: list[ToolDefinition],
        input_variables: dict[str, Any] | None,
    ) -> tuple[bool, ToolUsePolicy | None, str]:
        if response.tool_calls:
            return False, None, ""

        response_text = (response.message.content or "").strip()
        if not response_text:
            return False, None, ""

        retry_policy = cls._resolve_breach_retry_policy(
            response_text=response_text,
            tools=tools,
            current_policy=current_policy,
            input_variables=input_variables,
        )
        if retry_policy is None:
            return False, None, ""
        return True, retry_policy, response_text

    @classmethod
    def _should_retry_web_research_contract_breach(
        cls,
        *,
        messages: list[ChatMessage],
        response: ChatResponse,
        current_policy: ToolUsePolicy,
        tools: list[ToolDefinition],
        input_variables: dict[str, Any] | None,
        continuation: ResearchContinuationContext | None,
    ) -> tuple[bool, ToolUsePolicy | None, str]:
        if response.tool_calls:
            return False, None, ""

        response_text = (response.message.content or "").strip()
        if not response_text:
            return False, None, ""

        tool_names = {tool.name for tool in tools}
        if not {"web_search", "fetch_url"} <= tool_names:
            return False, None, ""

        search_queries, fetched_urls = cls._collect_web_research_evidence(messages)
        if not search_queries or fetched_urls:
            return False, None, ""

        current_user_text = cls._extract_last_user_text(messages)
        requested_intents = cls._detect_requested_turn_intents(
            current_user_text,
            tools=tools,
            input_variables=input_variables,
        )
        explicit_web_request = cls._looks_like_explicit_web_research_request(
            current_user_text,
            tools,
        )
        web_research_requested = (
            current_policy.family == "web_research"
            or bool(continuation and continuation.active)
            or explicit_web_request
            or any(
                intent in {"weather", "rail_ticket_research"}
                for intent in requested_intents
            )
        )
        if not web_research_requested:
            return False, None, ""

        retry_policy = cls._build_required_policy_for_family(
            "web_research",
            tools,
            input_variables,
            reason="web_research_summary_without_fetch",
        )
        if current_policy.reason.startswith("web_research_summary_without_fetch"):
            retry_policy.retry_on_contract_breach = False
        return True, retry_policy, response_text

    @classmethod
    def _collect_tool_family_evidence(
        cls,
        messages: list[ChatMessage],
    ) -> dict[str, int]:
        counts = {
            "web_research": 0,
            "weather": 0,
            "page_ops": 0,
        }
        for msg in messages:
            if msg.role != "assistant" or not msg.tool_calls:
                continue
            for tc in msg.tool_calls:
                if tc.get("success") is not True:
                    continue
                func = tc.get("function") or {}
                name = str(func.get("name") or tc.get("name") or "").strip()
                family = cls._tool_family_for_name(name)
                if family in counts:
                    counts[family] += 1
        return counts

    def _log_tool_contract_diagnostics(
        self,
        *,
        agent: Agent,
        messages: list[ChatMessage],
        response: ChatResponse | None,
        tools: list[ToolDefinition],
        policy: ToolUsePolicy,
        conversation_id: int | None,
        breach_type: str,
        retry_result: str,
        continuation: ResearchContinuationContext | None = None,
    ) -> None:
        if not tools:
            return

        response_text = (
            (response.message.content or "").strip() if response is not None else ""
        )
        current_user_text = self._extract_last_user_text(messages)
        target_text = (
            continuation.research_target_text
            if continuation and continuation.research_target_text
            else ""
        )
        trace_id = ""
        try:
            from app.middleware.trace import trace_id_var

            trace_id = trace_id_var.get() or ""
        except Exception:
            trace_id = ""

        family_evidence = self._collect_tool_family_evidence(messages)
        search_queries, fetched_urls = self._collect_web_research_evidence(messages)
        status = {
            "retrying": "policy_retry_started",
            "succeeded": "policy_retry_succeeded",
            "failed": "policy_retry_failed",
            "logged": "policy_logged_only",
            "no_retry": "policy_loaded_but_no_retry",
        }.get(retry_result, retry_result or "policy_unknown")
        logger.warning(
            "Tool contract breach: status={} type={} retry_result={} agent_id={} conversation_id={} trace_id={} family={} tool_choice={} allowed_tool_names={} current_user_text={} response_preview={} research_target={} family_evidence={} search_query_count={} fetched_url_count={}",
            status,
            breach_type,
            retry_result,
            getattr(agent, "id", None),
            conversation_id,
            trace_id,
            policy.family,
            policy.mode,
            policy.allowed_tool_names,
            self._truncate_preview(current_user_text),
            self._truncate_preview(response_text),
            self._truncate_preview(target_text),
            family_evidence,
            len(search_queries),
            len(fetched_urls),
        )

    def _log_web_research_contract_diagnostics(
        self,
        *,
        agent: Agent,
        messages: list[ChatMessage],
        response: ChatResponse,
        tools: list[ToolDefinition],
        continuation: ResearchContinuationContext | None,
        conversation_id: int | None,
    ) -> None:
        if not tools:
            return

        tool_names = [tool.name for tool in tools]
        if "web_search" not in tool_names:
            return

        response_text = (response.message.content or "").strip()
        search_queries, fetched_urls = self._collect_web_research_evidence(messages)
        search_count = len(search_queries)
        fetch_count = len(fetched_urls)

        def _emit(breach_type: str) -> None:
            self._log_tool_contract_diagnostics(
                agent=agent,
                messages=messages,
                response=response,
                tools=tools,
                policy=self._build_required_policy_for_family(
                    "web_research",
                    tools,
                    None,
                    reason=breach_type,
                ),
                conversation_id=conversation_id,
                breach_type=breach_type,
                retry_result="logged",
                continuation=continuation,
            )

        if not continuation or not continuation.active:
            return
        if response.tool_calls or not response_text:
            return

        if search_count == 0:
            _emit("web_research_capability_denial_or_no_tool_use")
            return

        if "fetch_url" in tool_names and search_count > 0 and fetch_count == 0:
            _emit("web_research_summary_without_fetch")

    @classmethod
    def _build_web_research_continuation_context(
        cls,
        messages: list[ChatMessage],
        all_tools: list[ToolDefinition],
        input_variables: dict[str, Any] | None = None,
    ) -> ResearchContinuationContext:
        tool_names = {tool.name for tool in all_tools}
        tool_families = [
            family
            for family in cls._stable_unique_text_list(
                [
                    cls._tool_semantic_family(tool, input_variables)
                    for tool in all_tools
                ]
            )
            if family != "none"
        ]
        page_operation_names = cls._page_operation_names_from_input_variables(
            input_variables,
        )
        page_context_attached = cls._has_page_context(input_variables)
        web_research_pair_complete = {"web_search", "fetch_url"} <= tool_names
        continuation_capable_families: list[str] = []
        if page_context_attached and "page_ops" in tool_families:
            continuation_capable_families.append("page_ops")
        if web_research_pair_complete and "web_research" in tool_families:
            continuation_capable_families.append("web_research")

        current_user_text = ""
        prior_messages: list[ChatMessage] = []
        for idx in range(len(messages) - 1, -1, -1):
            msg = messages[idx]
            if msg.role == "user":
                current_user_text = (msg.content or "").strip()
                prior_messages = messages[:idx]
                break

        if not current_user_text:
            return ResearchContinuationContext(
                tool_families=tool_families,
                page_operation_names=page_operation_names,
                page_context_attached=page_context_attached,
                web_research_pair_complete=web_research_pair_complete,
                continuation_capable_families=continuation_capable_families,
            )

        recent_successful_tool_names = cls._extract_recent_successful_tool_names(
            prior_messages,
        )
        recent_web_queries = cls._extract_recent_web_queries(prior_messages)
        search_queries, fetched_urls = cls._collect_web_research_evidence(
            prior_messages,
        )
        research_instruction_texts = cls._extract_recent_research_instruction_texts(
            prior_messages,
            current_user_text,
        )
        last_turn_facts = cls._extract_latest_turn_runtime_facts(prior_messages)
        latest_successful_tool = (
            recent_successful_tool_names[0] if recent_successful_tool_names else ""
        )
        last_tool_name = str(last_turn_facts.get("last_tool_name") or "").strip()
        last_page_key = str(last_turn_facts.get("last_page_key") or "").strip()
        last_page_op = str(last_turn_facts.get("last_page_op") or "").strip()
        active_intent_kind = (
            str(last_turn_facts.get("active_intent_kind") or "").strip() or None
        )
        last_tool_family = cls._tool_family_for_name(last_tool_name, input_variables)

        active = False
        family: str | None = None
        if (
            "page_ops" in continuation_capable_families
            and (
                last_tool_family == "page_ops"
                or str(active_intent_kind or "").startswith("page_")
            )
        ):
            active = True
            family = "page_ops"
        elif latest_successful_tool in {"web_search", "fetch_url"} and "web_search" in tool_names:
            active = True
            family = "web_research"

        origin = "continuation" if active else "none"

        research_target_text = (
            recent_web_queries[0]
            if recent_web_queries
            else (
                last_page_key
                if family == "page_ops" and last_page_key
                else cls._extract_last_user_text(prior_messages) or current_user_text
            )
        )

        return ResearchContinuationContext(
            active=active,
            family=family,
            origin=origin,
            current_user_text=current_user_text,
            research_target_text=research_target_text,
            recent_successful_tool_names=recent_successful_tool_names,
            recent_web_queries=recent_web_queries,
            search_query_count=len(search_queries),
            fetched_url_count=len(fetched_urls),
            research_instruction_texts=research_instruction_texts,
            tool_families=tool_families,
            page_operation_names=page_operation_names,
            page_context_attached=page_context_attached,
            web_research_pair_complete=web_research_pair_complete,
            continuation_capable_families=continuation_capable_families,
            last_tool_name=last_tool_name,
            last_page_key=last_page_key,
            last_page_op=last_page_op,
            active_intent_kind=active_intent_kind,
        )

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
                self.db,
                agent,
                tenant_id=request.tenant_id,
                user_role=getattr(request, "user_role", None),
            )

        # 2. Build model context via ContextEngine / 通过 ContextEngine 组装上下文
        context_engine = get_context_engine(
            db=self.db,
            base_engine=self,
        )
        await context_engine.ingest(agent, request)
        context_assembly = await context_engine.assemble(
            agent,
            request,
            skill_result=skill_result,
        )
        # Explicit session compaction phase (persist sidecar snapshot when over threshold).
        # 显式 compact 阶段（超阈值时持久化侧车摘要快照）。
        await context_engine.compact(agent, request)
        messages = context_assembly.messages
        rag_sources = context_assembly.rag_sources

        # 4. Tool list + expand page tools, then optimize / 4. 获取工具列表、展开页面工具后再优化
        tools = skill_result.tools if skill_result else []
        if tools:
            from app.ai.tools.page_tool_expander import expand_page_tools

            tools = expand_page_tools(tools, request.input_variables)
        if tools and self.sandbox is None:
            logger.info(
                "Skip tool exposure because sandbox is unavailable: agent_id={} tool_count={}",
                agent.id,
                len(tools),
            )
            tools = []

        all_tools = list(tools) if tools else []
        continuation_context = self._build_web_research_continuation_context(
            messages,
            all_tools,
            request.input_variables,
        )

        # 4.5 Enhance tool schemas with page context (enum/default) / 用页面上下文增强工具 Schema
        if all_tools:
            from app.ai.tools.enhancer import enhance_tools_with_page_context

            enhance_tools_with_page_context(all_tools, request.input_variables)

        optimize_event: dict[str, Any] | None = None
        tool_planner: dict[str, Any] | None = None
        tool_use_policy = ToolUsePolicy()
        raw_intent_plan = context_assembly.diagnostics.get("intent_plan")
        intent_plan = self._deserialize_intent_plan(raw_intent_plan)
        intent_flags = self._intent_plan_gating_flags(intent_plan)
        explicit_requested_families = self._ordered_requested_families_from_intents(
            intents=intent_plan,
        )
        execution_path = PathSelector.select(intent_plan)
        execution_budget = BudgetGuard.build_default(
            execution_path,
            intent_count=len(intent_plan),
        )
        active_intent_id: str | None = None
        candidate_tool_names = [tool.name for tool in tools]
        if all_tools and intent_plan:
            user_query = self._extract_last_user_text(messages)
            routing = ToolRouter.route(
                intents=intent_plan,
                tools=all_tools,
                budget=execution_budget,
                input_variables=request.input_variables,
                user_text=user_query,
            )
            tools = list(routing.candidate_tools)
            tools, _ = self._ensure_explicit_family_coverage(
                selected_tools=tools,
                all_tools=all_tools,
                explicit_requested_families=explicit_requested_families,
                input_variables=request.input_variables,
            )
            tools, _ = self._ensure_web_research_tool_pair(
                selected_tools=tools,
                all_tools=all_tools,
                explicit_requested_families=explicit_requested_families,
                policy=ToolUsePolicy(
                    family=(
                        "web_research"
                        if "web_research" in explicit_requested_families
                        else "none"
                    ),
                    allowed_tool_names=self._allowed_tool_names_for_family(
                        "web_research",
                        all_tools,
                        request.input_variables,
                    )
                    if "web_research" in explicit_requested_families
                    else [],
                ),
            )
            candidate_tool_names = [tool.name for tool in tools]
            actionable_intents = [
                intent
                for intent in intent_plan
                if intent.family != "none" and intent.requires_tools
            ]
            for intent in intent_plan:
                allowed = list(routing.intent_allowed_tools.get(intent.intent_id, []))
                preferred = list(
                    routing.intent_preferred_tools.get(intent.intent_id, allowed)
                )
                intent.allowed_tool_names = allowed
                intent.preferred_tool_names = preferred
                intent.completion_signals = self._intent_completion_signals(
                    intent.family,
                    allowed_tool_names=allowed,
                    preferred_tool_names=preferred,
                )
                if intent.family == "none" or not intent.requires_tools:
                    intent.status = "completed"
            if not tools and actionable_intents:
                fallback_allowed_names = self._allowed_tool_names_for_families(
                    explicit_requested_families,
                    all_tools,
                    request.input_variables,
                ) or self._allowed_tool_names_for_family(
                    actionable_intents[0].family,
                    all_tools,
                    request.input_variables,
                )
                if execution_budget.max_candidate_tools > 0:
                    fallback_allowed_names = fallback_allowed_names[
                        : execution_budget.max_candidate_tools
                    ]
                tools = self._restrict_tools_to_names(all_tools, fallback_allowed_names)
                candidate_tool_names = [tool.name for tool in tools]
                first_actionable = actionable_intents[0]
                first_actionable.allowed_tool_names = list(candidate_tool_names)
                first_actionable.preferred_tool_names = list(candidate_tool_names)
                first_actionable.completion_signals = self._intent_completion_signals(
                    first_actionable.family,
                    allowed_tool_names=list(candidate_tool_names),
                    preferred_tool_names=list(candidate_tool_names),
                )
            active_intent = next(
                (
                    intent
                    for intent in intent_plan
                    if intent.status != "completed" and intent.allowed_tool_names
                ),
                None,
            )
            active_intent_id = (
                active_intent.intent_id if active_intent is not None else None
            )
            if active_intent is not None:
                allowed_tool_names = (
                    candidate_tool_names
                    if len(actionable_intents) > 1
                    else list(active_intent.allowed_tool_names)
                )
                tool_use_policy = ToolUsePolicy(
                    family=active_intent.family,
                    mode="required",
                    allowed_tool_names=allowed_tool_names,
                    retry_on_contract_breach=True,
                    reason=f"intent:{active_intent.kind}",
                )
                tools, restored_explicit_family = self._restore_explicit_family_tools(
                    selected_tools=tools,
                    all_tools=all_tools,
                    policy=tool_use_policy,
                )
                if restored_explicit_family:
                    candidate_tool_names = [tool.name for tool in tools]
                    tool_use_policy.allowed_tool_names = (
                        candidate_tool_names
                        if len(actionable_intents) > 1
                        else [
                            name
                            for name in tool_use_policy.allowed_tool_names
                            if name in candidate_tool_names
                        ]
                    )
            tool_planner = {
                "intent": (
                    active_intent.kind
                    if active_intent is not None
                    else "direct_reply"
                ),
                "family": (
                    active_intent.family if active_intent is not None else "none"
                ),
                "allow_no_tool": not bool(tools),
                "allow_family_continuation": bool(len(actionable_intents) > 1),
                "reason": "structured_intent_plan",
                "confidence_band": "high",
                "execution_path": execution_path,
                "intent_plan": [intent.to_dict() for intent in intent_plan],
            }
            optimize_event = {
                "total": len(all_tools),
                "selected": len(tools),
                "execution_path": execution_path,
            }
            logger.info(
                "Prepare execution intent plan: runtime={} agent_id={} conversation_id={} execution_path={} intent_plan={} candidate_tool_names={} active_intent_id={}",
                get_runtime_identity_tag(),
                getattr(agent, "id", None),
                request.conversation_id,
                execution_path,
                [intent.to_dict() for intent in intent_plan],
                candidate_tool_names,
                active_intent_id,
            )
            logger.info(
                "Prepare execution tool policy: runtime={} agent_id={} conversation_id={} family={} mode={} allowed_tool_names={} all_tool_count={} selected_tool_count={}",
                get_runtime_identity_tag(),
                getattr(agent, "id", None),
                request.conversation_id,
                tool_use_policy.family,
                tool_use_policy.mode,
                tool_use_policy.allowed_tool_names,
                len(all_tools),
                len(tools),
            )
        elif intent_plan:
            tool_planner = {
                "intent": (
                    intent_plan[0].kind if intent_plan else "direct_reply"
                ),
                "family": intent_plan[0].family if intent_plan else "none",
                "allow_no_tool": not bool(tools),
                "allow_family_continuation": bool(
                    len(
                        [
                            intent
                            for intent in intent_plan
                            if intent.family != "none" and intent.requires_tools
                        ]
                    )
                    > 1
                ),
                "reason": "structured_intent_plan",
                "confidence_band": "high",
                "execution_path": execution_path,
                "intent_plan": [intent.to_dict() for intent in intent_plan],
            }
        if execution_budget is not None:
            BudgetGuard.register_preparation(
                execution_budget,
                prompt_tokens=(
                    int(context_assembly.estimated_tokens)
                    if context_assembly.estimated_tokens
                    else sum(
                        estimate_tokens(message.content or "") for message in messages
                    )
                ),
                candidate_tools_count=len(candidate_tool_names),
            )

        # 5. Inject runtime capability awareness / 注入运行时能力感知提示
        context_sources = (
            context_assembly.capability_bundle.context_sources
            if context_assembly.capability_bundle is not None
            else None
        )
        runtime_capability_summary = (
            dict(context_assembly.diagnostics.get("runtime_capability_summary") or {})
            if isinstance(
                context_assembly.diagnostics.get("runtime_capability_summary"),
                dict,
            )
            else None
        )
        capability_injection_decision = dict(
            context_assembly.diagnostics.get("capability_injection_decision") or {}
        )
        capability_injection_decision.setdefault(
            "all_shortcircuit",
            intent_flags["all_shortcircuit"],
        )
        capability_injection_decision.setdefault("skills_injected", False)
        capability_injection_decision.setdefault("kb_injected", False)
        capability_injection_decision.setdefault("memory_injected", False)
        capability_injection_decision.setdefault("page_injected", False)
        capability_injection_decision.setdefault(
            "bypass_reason",
            "all_shortcircuit" if intent_flags["all_shortcircuit"] else None,
        )
        force_capability_summary = self._is_capability_reporting_query(
            self._extract_last_user_text(messages),
        )
        skip_capability_summary = bool(
            context_assembly.diagnostics.get("dynamic_capability_awareness_enabled")
        ) or (
            intent_flags["all_shortcircuit"] and not force_capability_summary
        )
        context_assembly.diagnostics["capability_reporting_query"] = (
            force_capability_summary
        )
        capability_summary_injected = self._inject_runtime_summary(
            messages,
            tools,
            request.input_variables,
            continuation_context=continuation_context,
            runtime_capability_summary=runtime_capability_summary,
            ordered_requested_families=explicit_requested_families,
            skip_capability_summary=skip_capability_summary,
            intent_plan=intent_plan,
            execution_path=execution_path,
            execution_budget=execution_budget,
            include_knowledge_base_hint=intent_flags["has_knowledge_intent"],
            include_page_context_hint=intent_flags["has_page_intent"],
            include_memory_hint=intent_flags["has_memory_intent"],
        )
        active_context_source_kinds = {
            str(source.kind or "").strip()
            for source in (context_sources or [])
            if bool(getattr(source, "active", True))
        }
        capability_injection_decision["skills_injected"] = bool(
            capability_summary_injected and "skill" in active_context_source_kinds
        )
        capability_injection_decision["kb_injected"] = bool(
            capability_injection_decision["kb_injected"]
            or (
                capability_summary_injected
                and "knowledge_base" in active_context_source_kinds
                and intent_flags["has_knowledge_intent"]
            )
        )
        capability_injection_decision["memory_injected"] = bool(
            capability_injection_decision["memory_injected"]
            or (
                capability_summary_injected
                and (
                    "session_memory" in active_context_source_kinds
                    or "long_term_memory" in active_context_source_kinds
                )
                and intent_flags["has_memory_intent"]
            )
        )
        capability_injection_decision["page_injected"] = bool(
            capability_injection_decision["page_injected"]
            or (
                capability_summary_injected
                and "page_context" in active_context_source_kinds
                and intent_flags["has_page_intent"]
            )
        )
        context_assembly.diagnostics["capability_injection_decision"] = (
            capability_injection_decision
        )

        # 6. Extract consent_modes / 提取 consent_modes
        tool_consent_modes = skill_result.tool_consent_modes if skill_result else {}
        selected_tool_names = {tool.name for tool in tools}
        if selected_tool_names:
            tool_consent_modes = {
                name: mode
                for name, mode in (tool_consent_modes or {}).items()
                if name in selected_tool_names
            }
        tool_consent_modes = self._apply_execution_trust_policy(
            tools=tools,
            input_variables=request.input_variables,
            tool_consent_modes=tool_consent_modes,
            trust_policy_ref=request.trust_policy_ref,
            interaction_mode=request.interaction_mode,
        )

        # 7. ModelRouter multi-model routing (graceful fallback on failure) / ModelRouter 多模型路由（容错失败时自动向后兼容）
        route_result = None
        try:
            from app.ai.routing.router import ModelRouter
            from app.services.ai.usage_metrics import TokenCounter

            estimated_tokens = TokenCounter.count_messages_tokens(
                [{"content": m.content or "", "name": m.name or ""} for m in messages]
            )
            router = ModelRouter(self.db)
            route_result = await router.route(
                agent, request, estimated_tokens, tools=tools
            )
        except BusinessException:
            raise
        except Exception as _routing_exc:
            logger.warning("ModelRouter integration failed: {}", str(_routing_exc))

        runtime_model_capabilities: dict[str, bool] | None = None
        try:
            if route_result is not None and getattr(
                route_result, "is_overridden", False
            ):
                model_id = int(getattr(route_result, "model_id", 0) or 0)
                route_model_obj = None
                if model_id:
                    from app.repositories.ai.model_repository import AIModelRepository

                    model_repo = AIModelRepository(self.db)
                    route_model_obj = await model_repo.get_active_with_provider(
                        model_id
                    )
                if route_model_obj is not None:
                    runtime_model_capabilities = {
                        "supports_audio": bool(
                            getattr(route_model_obj, "supports_audio", False)
                        ),
                        "supports_video": bool(
                            getattr(route_model_obj, "supports_video", False)
                        ),
                        "supports_vision": bool(
                            getattr(route_model_obj, "supports_vision", False)
                        ),
                    }
            elif agent.model is not None:
                runtime_model_capabilities = {
                    "supports_audio": bool(
                        getattr(agent.model, "supports_audio", False)
                    ),
                    "supports_video": bool(
                        getattr(agent.model, "supports_video", False)
                    ),
                    "supports_vision": bool(
                        getattr(agent.model, "supports_vision", False)
                    ),
                }
        except Exception as capability_exc:
            logger.warning(
                "Resolve runtime model capabilities failed: {}", str(capability_exc)
            )

        if runtime_model_capabilities:
            request.input_variables = {
                **(request.input_variables or {}),
                "runtime_model_capabilities": runtime_model_capabilities,
            }
            if self.sandbox is not None:
                self.sandbox.input_variables = {
                    **(self.sandbox.input_variables or {}),
                    "runtime_model_capabilities": runtime_model_capabilities,
                }

        request.tool_use_policy = dataclasses.replace(tool_use_policy)
        if tool_planner is not None:
            context_assembly.diagnostics["tool_planner"] = dict(tool_planner)
        context_assembly.diagnostics["candidate_tool_names"] = list(candidate_tool_names)
        context_assembly.diagnostics["active_intent_id"] = active_intent_id
        context_assembly.diagnostics["continuation_source"] = (
            continuation_context.family if continuation_context and continuation_context.active else None
        )
        if intent_plan:
            context_assembly.diagnostics["intent_plan"] = [
                intent.to_dict() for intent in intent_plan
            ]
            context_assembly.diagnostics["execution_path"] = execution_path
        if execution_budget is not None:
            context_assembly.diagnostics["execution_budget"] = (
                execution_budget.snapshot()
            )

        return PreparedExecution(
            messages=messages,
            tools=tools,
            all_tools=all_tools,
            continuation_context=continuation_context,
            tool_use_policy=tool_use_policy,
            rag_sources=rag_sources,
            rag_source_kinds=context_assembly.rag_source_kinds,
            context_engine=context_engine,
            compact_summary=context_assembly.compact_summary,
            prune_stats=context_assembly.prune_stats,
            memory_recall_slice=context_assembly.memory_recall_slice,
            context_compacted=context_assembly.context_compacted,
            memory_flush_triggered=context_assembly.memory_flush_triggered,
            memory_recalled=context_assembly.memory_recalled,
            system_prompt_additions=context_assembly.system_prompt_additions,
            diagnostics=context_assembly.diagnostics,
            tool_planner=dict(tool_planner) if tool_planner is not None else None,
            tool_consent_modes=tool_consent_modes,
            capability_bundle=context_assembly.capability_bundle,
            optimize_event=optimize_event,
            route_result=route_result,
            intent_plan=intent_plan,
            execution_path=execution_path,
            execution_budget=execution_budget,
            active_intent_id=active_intent_id,
        )

    # ========================================
    # LLM Call / LLM 调用
    # ========================================

    async def _call_llm(
        self,
        agent: Agent,
        messages: list[ChatMessage],
        tools: list[ToolDefinition] | None = None,
        all_tool_names: list[str] | None = None,
        tool_use_policy: ToolUsePolicy | None = None,
        breach_retry_result: str | None = None,
        tenant_id: int | None = None,
        user_id: int | None = None,
        conversation_id: int | None = None,
        billing_context: dict[str, Any] | None = None,
        route_result: Any | None = None,
        log_user_type: str | None = None,
        selected_skill_names: list[str] | None = None,
        context_sources: list[Any] | None = None,
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
        del selected_skill_names, context_sources
        # Build OpenAI tools parameter / 构建 OpenAI tools 参数
        openai_tools = None
        if tools:
            openai_tools = to_openai_tools(tools)
        effective_policy = tool_use_policy or ToolUsePolicy(
            family="none",
            mode="auto" if tools else "none",
            allowed_tool_names=[tool.name for tool in (tools or [])],
            retry_on_contract_breach=False,
            reason="implicit_auto",
        )

        routed_model_id: int | None = None
        route_reason: str | None = None

        # Get model info: route override takes priority / 获取模型信息：路由覆写优先
        if route_result is not None and getattr(route_result, "is_overridden", False):
            provider_code = route_result.provider_code or ""
            model_code = route_result.model_code or ""
            routed_model_id = int(getattr(route_result, "model_id", 0) or 0) or None
            route_reason = route_result.reason or None
            # Use routed model's actual capabilities (per spec: 根据模型的 supports_* 决定)
            # 使用路由选中模型的真实能力（规范：根据模型的 supports_* 决定）
            model_id: int = int(getattr(route_result, "model_id", 0) or 0)
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
            provider_code = (
                model_obj.provider.code if model_obj and model_obj.provider else ""
            )
            model_code = model_obj.code if model_obj else ""
            is_vision = model_obj.supports_vision if model_obj else False
            is_audio = (
                getattr(model_obj, "supports_audio", False) if model_obj else False
            )
            is_video = (
                getattr(model_obj, "supports_video", False) if model_obj else False
            )

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

        logger.info(
            "LLM call entry: runtime={} agent_id={} conversation_id={} provider={} model={} family={} mode={} allowed_tool_names={} tool_count={}",
            get_runtime_identity_tag(),
            getattr(agent, "id", None),
            conversation_id,
            provider_code,
            model_code,
            effective_policy.family,
            effective_policy.mode,
            effective_policy.allowed_tool_names,
            len(tools or []),
        )
        response = await self.gateway.chat(
            provider_code=provider_code,
            messages=messages,
            model=model_code,
            temperature=agent.temperature,
            max_tokens=agent.max_tokens,
            top_p=agent.top_p or 1.0,
            tools=openai_tools,
            tool_choice=(
                effective_policy.mode
                if openai_tools and effective_policy.mode in {"auto", "required"}
                else None
            ),
            all_tool_names=all_tool_names or [tool.name for tool in (tools or [])],
            tool_use_policy_family=effective_policy.family,
            tool_use_policy_mode=effective_policy.mode,
            allowed_tool_names=effective_policy.allowed_tool_names,
            breach_retry_result=breach_retry_result,
            tenant_id=tenant_id,
            user_id=user_id,
            user_type=log_user_type,
            agent_id=getattr(agent, "id", None),
            conversation_id=conversation_id,
            billing_context=billing_context,
            routed_model_id=routed_model_id,
            route_reason=route_reason,
            supports_vision=bool(is_vision),
            supports_audio=bool(is_audio),
            supports_video=bool(is_video),
        )

        metadata = dict(getattr(response, "metadata", {}) or {})
        if routed_model_id is not None:
            metadata["routed_model_id"] = routed_model_id
        if route_reason:
            metadata["route_reason"] = route_reason
        response.metadata = metadata

        return response

    @staticmethod
    def _budget_exit_response(total_tokens: int) -> ChatResponse:
        return ChatResponse(
            message=ChatMessage(role="assistant", content=""),
            total_tokens=total_tokens,
        )

    # ========================================
    # Tool Call Loop / 工具调用循环
    # ========================================

    async def _handle_tool_calls(
        self,
        agent: Agent,
        messages: list[ChatMessage],
        response: ChatResponse,
        tools: list[ToolDefinition],
        all_tools: list[ToolDefinition] | None,
        request: ExecutionRequest,
        skip_final_call: bool = False,
        route_result: Any | None = None,
        tool_consent_modes: dict[str, str] | None = None,
        continuation_context: ResearchContinuationContext | None = None,
        selected_skill_names: list[str] | None = None,
        context_sources: list[Any] | None = None,
        tool_use_policy: ToolUsePolicy | None = None,
        execution_budget: ExecutionBudget | None = None,
        starting_total_tokens: int | None = None,
        starting_completion_tokens: int | None = None,
    ) -> tuple[ChatResponse | None, list[ToolResult], int, int]:
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
            (final_response, all_tool_results, total_tokens, completion_tokens)
            final_response is None when skip_final_call=True
            当 skip_final_call=True 时 final_response 为 None
        """
        _ = continuation_context
        from .tool_processor import ToolCallProcessor

        tools_full = list(tools)
        processor = ToolCallProcessor(
            sandbox=self.sandbox,
            tools=tools,
            all_tools=all_tools,
            consent_modes=tool_consent_modes or {},
            approved_pending_consent_tools=ToolCallProcessor.approved_pending_consent_tool_names(
                request.interaction_updates,
            ),
            interaction_mode=request.interaction_mode,
        )

        def _sync_sandbox_runtime_model_info(resp: ChatResponse | None) -> None:
            if self.sandbox is None or not hasattr(
                self.sandbox, "set_runtime_model_info"
            ):
                return
            metadata = getattr(resp, "metadata", None)
            runtime_model_info = (
                metadata.get("runtime_model_info") if isinstance(metadata, dict) else None
            )
            self.sandbox.set_runtime_model_info(runtime_model_info)

        _sync_sandbox_runtime_model_info(response)

        all_tool_results: list[ToolResult] = []
        total_tokens = (
            int(starting_total_tokens)
            if starting_total_tokens is not None
            else int(response.total_tokens or 0)
        )
        completion_tokens_used = (
            int(starting_completion_tokens)
            if starting_completion_tokens is not None
            else int(
                response.output_tokens
                if response.output_tokens is not None
                else (response.total_tokens or 0)
            )
        )
        current_response = response
        effective_policy = tool_use_policy or request.tool_use_policy or ToolUsePolicy()
        fetch_gate_message_sent = False
        ordered_requested_families = self._ordered_requested_families_from_intents(
            intents=IntentPlanner.plan_turn(
                messages=messages,
                tools=all_tools or tools_full,
                input_variables=request.input_variables,
                continuation_context=continuation_context,
            ),
        )
        completed_families: set[str] = set()
        has_fetch_url_in_toolset = any(
            t.name == "fetch_url" for t in (all_tools or tools_full)
        )
        issued_progress_hint_keys: set[str] = set()
        forced_tool_names: list[str] | None = None
        tracked_tool_rounds = int(
            execution_budget.tool_rounds_used if execution_budget is not None else 0
        )
        tracked_tool_result_bytes = int(
            execution_budget.tool_result_bytes_used
            if execution_budget is not None
            else 0
        )

        def _has_successful_tool_results() -> bool:
            return any(result.success for result in all_tool_results)

        def _round_tools_for_followup() -> list[ToolDefinition]:
            """Match streaming path: narrow to fetch_url until a fetch attempt exists."""
            nonlocal fetch_gate_message_sent
            if (
                self._needs_fetch_url_before_summary(messages)
                and not fetch_gate_message_sent
            ):
                messages.append(
                    ChatMessage(
                        role="system",
                        content=render_prompt_contract("fetch_url_gate"),
                    )
                )
                fetch_gate_message_sent = True
            round_tools = self._apply_fetch_url_only_gate(
                messages,
                tools_full,
                all_tools or tools_full,
            )
            round_tools = self._restrict_tools_to_names(round_tools, forced_tool_names)
            processor.tools = round_tools
            return round_tools

        def _round_policy(round_tools: list[ToolDefinition]) -> ToolUsePolicy:
            round_tool_names = [tool.name for tool in round_tools]
            if not round_tool_names:
                return effective_policy
            if round_tool_names == list(effective_policy.allowed_tool_names or []):
                return effective_policy
            reason_suffix = (
                "forced_tool_names" if forced_tool_names else "round_tool_subset"
            )
            return ToolUsePolicy(
                family=effective_policy.family,
                mode=effective_policy.mode,
                allowed_tool_names=round_tool_names,
                retry_on_contract_breach=effective_policy.retry_on_contract_breach,
                reason=(
                    f"{effective_policy.reason}|{reason_suffix}"
                    if effective_policy.reason
                    else reason_suffix
                ),
            )

        def _finalization_only_policy() -> ToolUsePolicy:
            return ToolUsePolicy(
                family="none",
                mode="none",
                allowed_tool_names=[],
                retry_on_contract_breach=False,
                reason="partial_exit_final_response",
            )

        def _sanitize_finalization_only_response(
            response: ChatResponse,
        ) -> ChatResponse:
            unexpected_tool_calls = list(
                response.tool_calls or response.message.tool_calls or []
            )
            if not unexpected_tool_calls:
                return response
            logger.warning(
                "Finalization-only response returned unexpected tool calls; suppressing execution: conversation_id={} tool_names={}",
                request.conversation_id,
                [
                    str(
                        (tool_call.get("function") or {}).get("name")
                        or tool_call.get("name")
                        or ""
                    )
                    for tool_call in unexpected_tool_calls
                    if isinstance(tool_call, dict)
                ],
            )
            metadata = dict(getattr(response, "metadata", {}) or {})
            metadata["finalization_tool_call_suppressed"] = True
            return dataclasses.replace(
                response,
                message=dataclasses.replace(response.message, tool_calls=None),
                tool_calls=None,
                metadata=metadata,
            )

        async def _call_finalization_only_response() -> ChatResponse:
            response = await self._call_llm(
                agent=agent,
                messages=messages,
                tools=None,
                all_tool_names=[],
                tool_use_policy=_finalization_only_policy(),
                tenant_id=request.tenant_id,
                user_id=request.user_id,
                conversation_id=request.conversation_id,
                billing_context=request.billing_context,
                route_result=route_result,
                log_user_type=log_user_type_for_call_log(request.user_role),
                selected_skill_names=selected_skill_names,
                context_sources=context_sources,
            )
            return _sanitize_finalization_only_response(response)

        def _append_ordered_progress_hint() -> None:
            if len(ordered_requested_families) <= 1:
                return
            if not completed_families:
                return
            remaining_families = [
                family
                for family in ordered_requested_families
                if family not in completed_families
            ]
            if not remaining_families:
                return
            done_names = [
                family
                for family in ordered_requested_families
                if family in completed_families
            ]
            hint_key = f"{'->'.join(done_names)}|{'->'.join(remaining_families)}"
            if hint_key in issued_progress_hint_keys:
                return
            issued_progress_hint_keys.add(hint_key)
            hint = self._build_ordered_capability_hint(
                ordered_requested_families,
                all_tools or tools_full,
                request.input_variables,
            )
            if not hint:
                return
            messages.append(
                ChatMessage(
                    role="system",
                    content=(
                        f"{hint}\n"
                        f"Completed families: {', '.join(done_names)}.\n"
                        f"Next family to prioritize: {remaining_families[0]}."
                    ),
                )
            )

        round_limit = (
            int(execution_budget.max_tool_rounds)
            if execution_budget is not None and execution_budget.max_tool_rounds > 0
            else 1
        )

        for _round in range(round_limit):
            _sync_sandbox_runtime_model_info(current_response)
            tool_calls = current_response.tool_calls
            if not tool_calls:
                break
            if BudgetGuard.pre_model_reason(execution_budget):
                return (
                    self._budget_exit_response(total_tokens),
                    all_tool_results,
                    total_tokens,
                    completion_tokens_used,
                )
            tracked_tool_rounds += 1
            if BudgetGuard.tool_round_reason(
                execution_budget,
                next_rounds_used=tracked_tool_rounds,
            ):
                return (
                    self._budget_exit_response(total_tokens),
                    all_tool_results,
                    total_tokens,
                    completion_tokens_used,
                )
            tool_calls, truncated_after_navigation = (
                self._truncate_tool_calls_after_navigation(tool_calls)
            )
            if truncated_after_navigation:
                current_response.tool_calls = tool_calls
                logger.info(
                    "Truncated assistant tool call batch after navigation op to avoid stale page follow-up calls: {}",
                    [
                        str(
                            (tc.get("function") or {}).get("name")
                            or tc.get("name")
                            or ""
                        )
                        for tc in tool_calls
                    ],
                )

            # Append assistant message (with tool_calls) / 追加 assistant 消息（含 tool_calls）
            messages.append(
                processor.build_assistant_tool_call_message(
                    content=current_response.message.content or "",
                    tool_calls=tool_calls,
                    reasoning_content=(current_response.message.content or "").strip()
                    or None,
                )
            )
            follow_up_messages: list[ChatMessage] = []
            round_tool_results: list[ToolResult] = []
            graceful_finalization_pending = False

            def _prepare_parallel_readonly_batch() -> list[
                tuple[dict[str, Any], str, dict[str, str | None]]
            ] | None:
                if len(tool_calls) <= 1:
                    return None
                prepared: list[tuple[dict[str, Any], str, dict[str, str | None]]] = []
                for tc in tool_calls:
                    func = tc.get("function", {})
                    func_name = str(func.get("name") or "").strip()
                    raw_args = func.get("arguments", "{}")
                    arguments, parse_error = processor.parse_arguments(raw_args)
                    if parse_error or arguments is None:
                        return None
                    if not processor.is_parallel_safe_tool_call(func_name, arguments):
                        return None
                    if processor.check_consent(func_name, arguments) in {"reject", "ask"}:
                        return None
                    prepared.append((tc, func_name, processor.get_skill_info(func_name)))
                return prepared

            def _apply_single_result(
                tc: dict[str, Any],
                *,
                func_name: str,
                skill_info: dict[str, str | None],
                single: Any,
            ) -> tuple[ChatResponse | None, list[ToolResult], int, int] | None:
                nonlocal tracked_tool_result_bytes

                if single.tool_result and single.tool_result.success:
                    self._mark_multi_family_progress(
                        func_name=func_name,
                        success=True,
                        ordered_requested_families=ordered_requested_families,
                        completed_families=completed_families,
                        has_fetch_url_in_toolset=has_fetch_url_in_toolset,
                        input_variables=request.input_variables,
                    )
                if single.tool_result:
                    all_tool_results.append(single.tool_result)
                    round_tool_results.append(single.tool_result)
                    processor.annotate_tool_call(
                        tc,
                        duration_ms=single.duration_ms,
                        result=single.tool_result,
                        skill_info=skill_info,
                    )
                    _conf_data = processor.check_confirmation_output(single.tool_result)
                    if _conf_data:
                        processor.annotate_tool_call(
                            tc,
                            pending_confirmation=processor.build_pending_confirmation_payload(
                                _conf_data,
                            ),
                        )
                    tool_result_budget_reason = BudgetGuard.tool_result_reason(
                        execution_budget,
                        current_bytes_used=tracked_tool_result_bytes,
                        additional_results=[single.tool_result],
                    )
                    tracked_tool_result_bytes += len(
                        (
                            single.tool_result.output or single.tool_result.error or ""
                        ).encode("utf-8")
                    )
                    if tool_result_budget_reason:
                        return (
                            self._budget_exit_response(total_tokens),
                            all_tool_results,
                            total_tokens,
                            completion_tokens_used,
                        )
                if single.tool_message:
                    messages.append(single.tool_message)
                if single.follow_up_message:
                    follow_up_messages.append(single.follow_up_message)
                return None

            # Execute each tool call (using ToolCallProcessor shared logic) / 执行每个工具调用（使用 ToolCallProcessor 共享逻辑）
            # consent_mode pre-check: same semantic as stream path / consent_mode 前置检查：与流式路径语义一致
            parallel_batch = _prepare_parallel_readonly_batch()
            if parallel_batch is not None:
                for tc, _func_name, skill_info in parallel_batch:
                    processor.annotate_tool_call(tc, skill_info=skill_info)
                singles = await asyncio.gather(
                    *[
                        processor.process_single(
                            tc,
                            conversation_id=request.conversation_id or 0,
                        )
                        for tc, _func_name, _skill_info in parallel_batch
                    ]
                )
                for (tc, func_name, skill_info), single in zip(
                    parallel_batch,
                    singles,
                    strict=False,
                ):
                    budget_exit = _apply_single_result(
                        tc,
                        func_name=func_name,
                        skill_info=skill_info,
                        single=single,
                    )
                    if budget_exit is not None:
                        return budget_exit
            else:
                for tc in tool_calls:
                    tc_id = tc.get("id", "")
                    func = tc.get("function", {})
                    func_name = func.get("name", "")
                    raw_args = func.get("arguments", "{}")
                    arguments, parse_error = processor.parse_arguments(raw_args)

                    # consent_mode only after args parse ok (else process_single handles errors) / 仅参数解析成功后检查 consent_mode
                    if not parse_error:
                        _skill_info = processor.get_skill_info(func_name)
                        processor.annotate_tool_call(tc, skill_info=_skill_info)
                        _consent = processor.check_consent(func_name, arguments)
                        if _consent == "reject":
                            messages.append(processor.build_consent_reject_message(tc_id))
                            continue
                        if _consent == "ask":
                            processor.annotate_tool_call(
                                tc,
                                pending_consent=processor.build_pending_consent_payload(
                                    func_name,
                                    arguments,
                                    _skill_info,
                                ),
                            )
                            messages.append(
                                processor.build_consent_ask_message(
                                    tc_id,
                                    func_name,
                                    arguments,
                                )
                            )
                            return (
                                ChatResponse(
                                    message=ChatMessage(
                                        role="assistant",
                                        content=current_response.message.content or "",
                                        tool_calls=tool_calls,
                                        metadata={
                                            "pending_consent": processor.build_pending_consent_payload(
                                                func_name,
                                                arguments,
                                                _skill_info,
                                            ),
                                        },
                                    ),
                                    metadata={
                                        **dict(
                                            getattr(current_response, "metadata", {}) or {}
                                        ),
                                        "skip_final_assistant": True,
                                    },
                                ),
                                all_tool_results,
                                total_tokens,
                                completion_tokens_used,
                            )

                    single = await processor.process_single(
                        tc,
                        conversation_id=request.conversation_id or 0,
                    )
                    budget_exit = _apply_single_result(
                        tc,
                        func_name=str(func_name or ""),
                        skill_info=processor.get_skill_info(func_name),
                        single=single,
                    )
                    if budget_exit is not None:
                        return budget_exit

            if follow_up_messages:
                messages.extend(follow_up_messages)

            recovery_hint = None
            recovery_tool_names: list[str] = []
            recovery_diagnostics: dict[str, Any] = {}
            if not graceful_finalization_pending:
                recovery_hint, recovery_tool_names, recovery_diagnostics = (
                    self._build_page_no_progress_recovery(
                        messages=messages,
                        tool_calls=tool_calls,
                        tool_results=round_tool_results,
                        tools=all_tools or tools_full,
                        input_variables=request.input_variables,
                    )
                )
            if recovery_hint:
                forced_tool_names = recovery_tool_names
                messages.append(ChatMessage(role="system", content=recovery_hint))
                logger.info(
                    "Injected page-flow recovery hint after no-progress page round: conversation_id={} diagnostics={}",
                    request.conversation_id,
                    recovery_diagnostics,
                )
            elif len(ordered_requested_families) > 1:
                if not self._messages_have_blocking_pending_interaction(messages):
                    focus = self._first_incomplete_requested_family(
                        ordered_requested_families,
                        completed_families,
                    )
                    forced_tool_names = (
                        None
                        if focus is None
                        else self._allowed_tool_names_for_family(
                            focus,
                            all_tools or tools_full,
                            request.input_variables,
                        )
                    )
            elif forced_tool_names:
                forced_tool_names = None

            if skip_final_call:
                if _round < round_limit - 1:
                    if BudgetGuard.pre_model_reason(execution_budget):
                        return (
                            None,
                            all_tool_results,
                            total_tokens,
                            completion_tokens_used,
                        )
                    _append_ordered_progress_hint()
                    round_tools = _round_tools_for_followup()
                    round_policy = _round_policy(round_tools)
                    peek_response = await self._call_llm(
                        agent=agent,
                        messages=messages,
                        tools=round_tools,
                        all_tool_names=[
                            tool.name for tool in (all_tools or tools or [])
                        ],
                        tool_use_policy=round_policy,
                        tenant_id=request.tenant_id,
                        user_id=request.user_id,
                        conversation_id=request.conversation_id,
                        billing_context=request.billing_context,
                        route_result=route_result,
                        log_user_type=log_user_type_for_call_log(request.user_role),
                        selected_skill_names=selected_skill_names,
                        context_sources=context_sources,
                    )
                    total_tokens += peek_response.total_tokens or 0
                    completion_tokens_used += int(
                        peek_response.output_tokens
                        if peek_response.output_tokens is not None
                        else (peek_response.total_tokens or 0)
                    )
                    if BudgetGuard.completion_reason(
                        execution_budget,
                        completion_tokens=completion_tokens_used,
                        total_tokens=total_tokens,
                    ):
                        return (
                            None,
                            all_tool_results,
                            total_tokens,
                            completion_tokens_used,
                        )
                    if peek_response.tool_calls:
                        current_response = peek_response
                        continue
                return None, all_tool_results, total_tokens, completion_tokens_used

            # Call LLM again (maintain same routed model as first call) / 再次调用 LLM（保持与第一次调用相同的路由模型）
            if BudgetGuard.pre_model_reason(execution_budget):
                return (
                    self._budget_exit_response(total_tokens),
                    all_tool_results,
                    total_tokens,
                    completion_tokens_used,
                )
            _append_ordered_progress_hint()
            round_tools = _round_tools_for_followup()
            round_policy = _round_policy(round_tools)
            current_response = await self._call_llm(
                agent=agent,
                messages=messages,
                tools=round_tools,
                all_tool_names=[tool.name for tool in (all_tools or tools or [])],
                tool_use_policy=round_policy,
                tenant_id=request.tenant_id,
                user_id=request.user_id,
                conversation_id=request.conversation_id,
                billing_context=request.billing_context,
                route_result=route_result,
                log_user_type=log_user_type_for_call_log(request.user_role),
                selected_skill_names=selected_skill_names,
                context_sources=context_sources,
            )
            total_tokens += current_response.total_tokens or 0
            completion_tokens_used += int(
                current_response.output_tokens
                if current_response.output_tokens is not None
                else (current_response.total_tokens or 0)
            )
            completion_reason = BudgetGuard.completion_reason(
                execution_budget,
                completion_tokens=completion_tokens_used,
                total_tokens=total_tokens,
            )
            if completion_reason:
                if (
                    completion_reason == "elapsed_budget_exceeded"
                    and not current_response.tool_calls
                    and str(current_response.message.content or "").strip()
                ):
                    break
                return (
                    self._budget_exit_response(total_tokens),
                    all_tool_results,
                    total_tokens,
                    completion_tokens_used,
                )
            if not current_response.tool_calls:
                break
        else:
            if BudgetGuard.pre_model_reason(execution_budget):
                return (
                    self._budget_exit_response(total_tokens),
                    all_tool_results,
                    total_tokens,
                    completion_tokens_used,
                )
            return (
                self._budget_exit_response(total_tokens),
                all_tool_results,
                total_tokens,
                completion_tokens_used,
            )

        return current_response, all_tool_results, total_tokens, completion_tokens_used

    # ========================================
    # Event Publishing / 事件发布
    # ========================================

    @staticmethod
    async def _publish_execution_started(
        request: ExecutionRequest, agent: Agent
    ) -> None:
        """Publish execution started event / 发布执行开始事件"""
        await get_event_bus().publish(
            ExecutionStarted(
                tenant_id=request.tenant_id,
                agent_id=agent.id,
                execution_mode=request.execution_mode,
            )
        )

    @staticmethod
    async def _publish_execution_completed(
        request: ExecutionRequest,
        agent: Agent,
        result: ExecutionResult,
    ) -> None:
        """Publish execution completed event / 发布执行完成事件"""
        await get_event_bus().publish(
            ExecutionCompleted(
                tenant_id=request.tenant_id,
                agent_id=agent.id,
                total_tokens=result.total_tokens,
                duration_ms=result.duration_ms,
            )
        )

    @staticmethod
    async def _publish_execution_failed(
        request: ExecutionRequest,
        agent: Agent,
        error: str,
        error_type: str = "",
    ) -> None:
        """Publish execution failed event / 发布执行失败事件"""
        await get_event_bus().publish(
            ExecutionFailed(
                tenant_id=request.tenant_id,
                agent_id=agent.id,
                error=error,
                error_type=error_type,
            )
        )

    # ========================================
    # Utility Methods / 工具方法
    # ========================================

    @staticmethod
    def _messages_to_dicts(messages: list[ChatMessage]) -> list[dict[str, Any]]:
        """Convert ChatMessage list to dict list / 将 ChatMessage 列表转为 dict 列表"""
        return [dataclasses.asdict(msg) for msg in messages]

    @classmethod
    def _apply_execution_trust_policy(
        cls,
        *,
        tools: list[ToolDefinition],
        input_variables: dict[str, Any] | None,
        tool_consent_modes: dict[str, str],
        trust_policy_ref: dict[str, Any] | None,
        interaction_mode: str = "confirm",
    ) -> dict[str, str]:
        is_trusted_auto = (
            str(interaction_mode or "confirm").strip() == "trusted_auto"
        )
        has_policy = isinstance(trust_policy_ref, dict)

        if not is_trusted_auto:
            # Non-trusted_auto: only apply explicit trust policy
            if not tools or not has_policy:
                return tool_consent_modes
            updated = dict(tool_consent_modes)
            for tool in tools:
                current_mode = updated.get(tool.name, "auto")
                if current_mode != "ask":
                    continue
                tool_family = cls._tool_semantic_family(tool, input_variables)
                if ExecutionTrustPolicyService.allows_tool(
                    tool_name=tool.name,
                    tool_family=tool_family,
                    policy_ref=trust_policy_ref,
                ):
                    updated[tool.name] = "auto"
            return updated

        # trusted_auto: apply trust policy (if present) + readonly whitelist
        if not tools:
            return tool_consent_modes

        from .tool_processor import is_trusted_auto_read_only_tool_call

        updated = dict(tool_consent_modes)
        for tool in tools:
            current_mode = updated.get(tool.name, "auto")
            if current_mode != "ask":
                continue
            if has_policy:
                tool_family = cls._tool_semantic_family(tool, input_variables)
                if ExecutionTrustPolicyService.allows_tool(
                    tool_name=tool.name,
                    tool_family=tool_family,
                    policy_ref=trust_policy_ref,
                ):
                    updated[tool.name] = "auto"
                    continue
            if is_trusted_auto_read_only_tool_call(tool.name):
                updated[tool.name] = "auto"
        return updated


__all__ = ["BaseEngine", "log_user_type_for_call_log"]
