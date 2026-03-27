"""
Execution Engine Abstract Base Class / 执行引擎抽象基类

Provides shared infrastructure for all execution modes:
message building, tool parsing, tool call loop, event publishing.
提供所有执行模式共享的基础设施：消息构建、工具解析、工具调用循环、事件发布。
"""

from __future__ import annotations

import dataclasses
import json
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from jinja2 import (
    BaseLoader,
    ChainableUndefined,
    Environment,
    TemplateSyntaxError,
    UndefinedError,
)
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
from app.enums.common import UserRoleEnum
from app.enums.log import UserTypeEnum as LogUserTypeEnum
from app.exceptions import BusinessException
from app.models.ai.agent import Agent

from .types import (
    ExecutionRequest,
    ExecutionResult,
    PreparedExecution,
    ResearchContinuationContext,
)

logger = LogManager.get_logger("ai.engine")


def log_user_type_for_call_log(user_role: str) -> str:
    """Map ExecutionRequest.user_role → call_log.user_type / 执行请求角色 → 调用日志用户类型."""
    if user_role == UserRoleEnum.PLATFORM_ADMIN.value:
        return LogUserTypeEnum.ADMIN.value
    if user_role == UserRoleEnum.TENANT_USER.value:
        return LogUserTypeEnum.TENANT_USER.value
    return LogUserTypeEnum.TENANT_ADMIN.value


# Max tool call rounds (prevents infinite loop) / 工具调用最大循环次数（防止无限循环）
MAX_TOOL_CALL_ROUNDS = 10

# Jinja2 environment (shared instance, undefined renders as empty string instead of error) / Jinja2 环境（共享实例，undefined 渲染为空字符串而非报错）
_jinja_env = Environment(
    loader=BaseLoader(), keep_trailing_newline=True, undefined=ChainableUndefined
)

_WEB_RESEARCH_CONTINUATION_HINTS = (
    "继续",
    "继续查",
    "再查",
    "请开始",
    "开始吧",
    "开始",
    "多看几篇",
    "多方面结合搜索",
    "多方面搜索",
    "多联网查",
    "联网查一下",
    "再搜",
    "继续搜",
    "接着查",
    "你不试试你怎么知道",
    "而不是仅一篇文章",
    "而不是一篇文章",
    "多结合几篇文章",
    "多看几个文章",
    "多查看几个文章",
    "多查看几篇文章",
)
_WEB_RESEARCH_REQUEST_HINTS = (
    "联网",
    "联网搜索",
    "上网搜索",
    "搜索网页",
    "网页搜索",
    "搜索引擎",
    "互联网",
    "官网",
    "网页",
    "网址",
    "新闻",
    "最新",
    "web_search",
)
_WEB_RESEARCH_ENTITY_REFERENCE_HINTS = (
    "这家公司",
    "这个公司",
    "这家企业",
    "这个企业",
    "这家公司",
    "它",
    "这个人",
    "他",
    "她",
    "这件事",
    "这个事件",
    "这个新闻",
)
_WEB_RESEARCH_MULTI_SOURCE_HINTS = (
    "多看几篇",
    "多看几个文章",
    "多查看几个文章",
    "多查看几篇文章",
    "多方面结合搜索",
    "多方面搜索",
    "多联网查",
    "交叉验证",
    "多篇文章",
    "更多来源",
    "而不是仅一篇文章",
    "而不是一篇文章",
)
_WEB_RESEARCH_DENIAL_HINTS = (
    "没有联网搜索工具",
    "没有可用的联网搜索工具",
    "没有真正可用的联网搜索工具",
    "不能继续联网",
    "不能直接联网搜索网页",
    "不能联网搜索网页",
    "不能直接进行联网搜索",
    "无法联网搜索",
)
_WEB_RESEARCH_MULTI_SOURCE_MIN_FETCHES = 2
_WEATHER_REQUEST_HINTS = (
    "天气",
    "预报",
    "气温",
    "温度",
    "降雨",
    "风力",
    "湿度",
    "weather",
    "forecast",
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
            identity = _("data_intelligence.identity_declaration").format(
                agent_name=agent_name
            )
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
    def _inject_tool_awareness(
        messages: list[ChatMessage],
        tools: list[ToolDefinition],
        input_variables: dict[str, Any] | None = None,
        continuation_context: ResearchContinuationContext | None = None,
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
            "When a newer user turn conflicts with an older temporary execution constraint "
            '(for example: "read-only", "do not write", "do not submit"), follow the latest user turn '
            "unless the user explicitly says the earlier constraint still applies.\n"
            "If the user asks for multiple operations or gives an ordered checklist, execute the requested operations "
            "in that order and only summarize after you have attempted each requested step.\n"
            "Do NOT show HTML, JSON, tool parameters or raw API output to the user. "
            "Tools are for internal execution; return natural language results only."
        )

        page_hint = BaseEngine._build_page_operations_hint(input_variables, tools)
        if page_hint:
            hint += page_hint
        data_hint = BaseEngine._build_data_operations_hint(tools)
        if data_hint:
            hint += data_hint
        web_hint = BaseEngine._build_web_research_hint(tools)
        if web_hint:
            hint += web_hint
        weather_hint = BaseEngine._build_weather_tools_hint(tools)
        if weather_hint:
            hint += weather_hint
        capability_hint = BaseEngine._build_capability_reporting_hint(
            tools,
            input_variables,
        )
        if capability_hint:
            hint += capability_hint
        continuation_hint = BaseEngine._build_research_continuation_hint(
            continuation_context,
        )
        if continuation_hint:
            hint += continuation_hint

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
        has_dedicated_page_tools = any(n.startswith("pageop_") for n in tool_names)
        has_data_tools = any(n.startswith("data_") for n in tool_names)
        data_distinction_note = ""
        if has_data_tools:
            data_distinction_note = (
                "\nNOTE: For direct database operations (query/create/update/delete records), "
                "use data_* tools instead of page operations."
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
                screenshot_hint = (
                    "\nScreenshot rule: use capture_screenshot only when text page context, DOM structure, "
                    "or visible-row/form data is insufficient for a visual/layout question. "
                    "Do NOT take repeated screenshots unless the page visibly changed."
                )
            dedicated_hint = (
                f"\nDedicated pageop_* tools available for: {', '.join(dedicated_ops)}"
                if dedicated_ops
                else ""
            )
            other_ops_hint = ""
            if other_ops:
                other_ops_hint = (
                    f"\nOther operations (use invoke_page_operation): "
                    f"{', '.join(other_ops)}\n"
                    f'Format: invoke_page_operation(page_key="{page_key}", '
                    f'operation_name="<name>", params={{...}})'
                )
            mutation_ops = [
                str(o.get("name", ""))
                for o in raw_ops
                if isinstance(o, dict) and o.get("name") and not bool(o.get("readonly", False))
            ]
            mutation_hint = ""
            if mutation_ops:
                mutation_hint = (
                    f"\nWritable page operations are available: {', '.join(mutation_ops)}."
                    "\nWhen the user asks to create, edit, fill, submit, or delete records, "
                    "you MUST use these page operations instead of replying that the page is read-only."
                )
            editor_flow_hint = ""
            if "get_editor_html" in pageop_tool_ops:
                editor_flow_hint = (
                    "\nEditor order: 1) pageop_get_editor_html to read; "
                    "2) pageop_replace_section for partial edits; "
                    "3) pageop_replace_content only for full rewrite; "
                    "4) pageop_update_title for metadata title (not body H1)."
                )
            return (
                f"\n\n[PAGE OPERATIONS]\n"
                f"Current page: {page_key}{desc_line}"
                f"Preferred: use dedicated pageop_* tools directly when available.\n"
                f"{dedicated_hint}"
                f"{mutation_hint}"
                f"{editor_flow_hint}"
                f"{other_ops_hint}\n"
                f"{screenshot_hint}"
                f"Do NOT show HTML, JSON, tool params or call examples to the user. "
                f"Tools are for internal execution; return natural language results only."
                f"{data_distinction_note}"
            )
        # Fallback: invoke_page_operation format for non-rich-text pages / 上文为英文说明 / English above
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
            screenshot_guidance = (
                "\nScreenshot rule: use capture_screenshot only when page context, DOM structure, "
                "or table/form data is insufficient for a visual/layout question. "
                "Avoid repeated screenshots unless the page visibly changed."
            )
        mutation_ops = [
            str(o.get("name", ""))
            for o in raw_ops
            if isinstance(o, dict) and o.get("name") and not bool(o.get("readonly", False))
        ]
        mutation_guidance = ""
        if mutation_ops:
            mutation_guidance = (
                f"\nWritable operations available: {', '.join(mutation_ops)}."
                "\nIf the user asks to create, edit, fill, submit, or delete, do not answer with a capability summary only."
                " Execute the writable page operations."
            )

        return (
            f"\n\n[PAGE OPERATIONS]\n"
            f"Current page: {page_key}{desc_line}"
            f"Available operations: {', '.join(op_names)}\n"
            f"Call format: invoke_page_operation("
            f'page_key="{page_key}", '
            f'operation_name="<pick one>", '
            f"params={{...}})\n"
            f"{read_example}"
            f"{search_example}"
            f"{section_example}"
            f"{screenshot_guidance}"
            f"{mutation_guidance}"
            f"{data_distinction_note}"
        )

    @staticmethod
    def _build_data_operations_hint(tools: list[ToolDefinition]) -> str:
        """
        Build a DATA OPERATIONS hint when data_* tools are available.
        当存在 data_* 工具时构建 DATA OPERATIONS 提示。
        """
        data_tools = [t.name for t in tools if t.name.startswith("data_")]
        if not data_tools:
            return ""
        return (
            "\n\n[DATA OPERATIONS]\n"
            f"Database tools available: {', '.join(data_tools)}.\n"
            "When the user asks to query data, create/update/delete records, "
            "view statistics, or explicitly mentions '平台数据管理' / 'data management', "
            "you MUST use data_* tools to operate the database directly.\n"
            "Do NOT use get_page_context / invoke_page_operation for database CRUD — "
            "those are for page UI interactions only (opening forms, navigating pages).\n"
            "Distinction: data_create = direct DB insert; "
            "create_record (page op) = open a UI form for user to fill."
        )

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

        return (
            "\n\n[WEB RESEARCH]\n"
            "When the user asks for internet research, latest information, or details from a specific web page, "
            "follow this workflow: "
            + "; ".join(workflow)
            + ".\n"
            "If the user explicitly says phrases like '联网搜索', '上网搜索', or 'web_search', "
            "treat that as an instruction to call web_search instead of explaining the capability in prose. "
            "If web_search or fetch_url is listed in your available tools, do NOT claim that internet search or webpage fetching is unavailable. "
            "Do not answer only from search snippets when concrete page details are needed. "
            "If the user explicitly asks for multiple articles, multiple sources, or cross-verification, inspect more than one distinct source before the final summary. "
            "If fetch_url returns a site block or weak content, pick another relevant source instead of pretending the page was read successfully."
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

        return (
            "\n\n[WEATHER TOOLS]\n"
            "When the user asks about weather, forecast, temperature, rain, humidity, wind, or named cities/counties/regions, "
            + "; ".join(workflow)
            + ".\n"
            "If both weather tools and web research tools are available, prefer weather tools first for direct weather questions. "
            "Only fall back to web_search/fetch_url when the user explicitly asks for web sources or the weather tools are unavailable. "
            "If the request asks for both current weather and future forecast, you may use both weather tools. "
            "If a weather tool is listed in your available tools, do NOT claim that weather tools are unavailable. "
            "If consent is required, ask for consent or wait for confirmation instead of saying you lack the tool."
        )

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
        return (
            "\n\n[CAPABILITY REPORTING]\n"
            "If the user asks what tools, skills, or capabilities you currently have, "
            "answer strictly from the tools and page operations available in this turn only.\n"
            f"Current tools: {tool_line}.\n"
            f"Current page operations: {page_line}.\n"
            "Do NOT claim a listed tool is unavailable. "
            "Do NOT invent external capabilities that are not present in the current tool list."
        )

    @staticmethod
    def _build_research_continuation_hint(
        continuation: ResearchContinuationContext | None,
    ) -> str:
        if not continuation or not continuation.active:
            return ""
        if continuation.family != "web_research":
            return ""

        target = continuation.research_target_text or continuation.effective_user_query
        intro = (
            "This turn continues the previous external web research task."
            if continuation.origin == "continuation"
            else "This turn is an external web research task."
        )
        multi_source = (
            "\nThe user explicitly wants multiple sources / articles / cross-verification. "
            f"Do not produce the final answer until you have inspected at least {_WEB_RESEARCH_MULTI_SOURCE_MIN_FETCHES} distinct sources when fetch_url is available."
            if continuation.requires_multi_source
            else ""
        )
        return (
            "\n\n[RESEARCH CONTINUATION]\n"
            f"{intro}\n"
            f"Research target: {target or '(same target as previous turn)'}.\n"
            "Use web_search and fetch_url again as needed. "
            "Do NOT say that web research tools are unavailable, and do NOT switch to data_query for this research task unless the user explicitly asks for internal platform data."
            f"{multi_source}"
        )

    @staticmethod
    def _user_message(content: str) -> ChatMessage:
        """Build user message / 构建 user 消息"""
        return ChatMessage(role="user", content=content)

    @staticmethod
    def _normalize_match_text(text: str) -> str:
        return " ".join((text or "").strip().lower().split())

    @classmethod
    def _contains_entity_reference(cls, text: str) -> bool:
        normalized = cls._normalize_match_text(text)
        return any(token in normalized for token in _WEB_RESEARCH_ENTITY_REFERENCE_HINTS)

    @classmethod
    def _is_web_research_continuation_text(cls, text: str) -> bool:
        normalized = cls._normalize_match_text(text)
        return any(token in normalized for token in _WEB_RESEARCH_CONTINUATION_HINTS)

    @classmethod
    def _is_web_research_request_text(cls, text: str) -> bool:
        normalized = cls._normalize_match_text(text)
        if any(token in normalized for token in _WEB_RESEARCH_REQUEST_HINTS):
            return True
        return "http://" in normalized or "https://" in normalized or "site:" in normalized

    @classmethod
    def _looks_like_weather_request(
        cls,
        text: str,
        all_tools: list[ToolDefinition],
    ) -> bool:
        tool_names = {tool.name for tool in all_tools}
        if not ({"get_current_weather", "get_weather_forecast"} & tool_names):
            return False
        normalized = cls._normalize_match_text(text)
        return any(token in normalized for token in _WEATHER_REQUEST_HINTS)

    @classmethod
    def _requires_multi_source_research(cls, text: str) -> bool:
        normalized = cls._normalize_match_text(text)
        return any(token in normalized for token in _WEB_RESEARCH_MULTI_SOURCE_HINTS)

    @classmethod
    def _is_web_research_capability_denial(cls, text: str) -> bool:
        normalized = cls._normalize_match_text(text)
        return any(token in normalized for token in _WEB_RESEARCH_DENIAL_HINTS)

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
    def _needs_more_web_research_sources(
        cls,
        messages: list[ChatMessage],
        tools: list[ToolDefinition],
        continuation: ResearchContinuationContext | None,
    ) -> bool:
        if not continuation or not continuation.active:
            return False
        if continuation.family != "web_research" or not continuation.requires_multi_source:
            return False

        tool_names = {tool.name for tool in tools}
        search_queries, fetched_urls = cls._collect_web_research_evidence(messages)

        if "fetch_url" in tool_names:
            return len(fetched_urls) < _WEB_RESEARCH_MULTI_SOURCE_MIN_FETCHES
        if "web_search" in tool_names:
            return len(search_queries) < _WEB_RESEARCH_MULTI_SOURCE_MIN_FETCHES
        return False

    @classmethod
    def _extract_last_substantive_user_query(
        cls,
        messages: list[ChatMessage],
    ) -> str:
        for msg in reversed(messages):
            if msg.role != "user":
                continue
            text = (msg.content or "").strip()
            if not text:
                continue
            if cls._is_web_research_continuation_text(text):
                continue
            if len(text) <= 4:
                continue
            return text
        return ""

    @classmethod
    def _extract_research_intent_terms(cls, text: str) -> list[str]:
        normalized = cls._normalize_match_text(text)
        terms: list[str] = []
        mapping = (
            ("盈利", "盈利模式"),
            ("赚钱", "盈利模式"),
            ("经营范围", "经营范围"),
            ("主营", "主营业务"),
            ("商标", "商标"),
            ("员工", "员工人数"),
            ("人数", "员工人数"),
            ("招聘", "招聘"),
            ("法人", "法人"),
            ("地址", "地址"),
            ("电话", "电话"),
            ("统一社会信用代码", "统一社会信用代码"),
        )
        for needle, term in mapping:
            if needle in normalized and term not in terms:
                terms.append(term)
        return terms

    @classmethod
    def _build_web_research_continuation_context(
        cls,
        messages: list[ChatMessage],
        all_tools: list[ToolDefinition],
    ) -> ResearchContinuationContext:
        tool_names = {tool.name for tool in all_tools}
        if "web_search" not in tool_names:
            return ResearchContinuationContext()

        current_user_text = ""
        prior_messages: list[ChatMessage] = []
        for idx in range(len(messages) - 1, -1, -1):
            msg = messages[idx]
            if msg.role == "user":
                current_user_text = (msg.content or "").strip()
                prior_messages = messages[:idx]
                break

        if not current_user_text:
            return ResearchContinuationContext()

        recent_successful_tool_names = cls._extract_recent_successful_tool_names(
            prior_messages,
        )
        recent_web_queries = cls._extract_recent_web_queries(prior_messages)
        requires_multi_source = cls._requires_multi_source_research(
            current_user_text,
        )
        intent_terms = cls._extract_research_intent_terms(current_user_text)
        has_recent_web_research = any(
            name in {"web_search", "fetch_url"}
            for name in recent_successful_tool_names
        )
        if not has_recent_web_research:
            if cls._is_web_research_request_text(
                current_user_text,
            ) and not cls._looks_like_weather_request(
                current_user_text,
                all_tools,
            ):
                effective_user_query = current_user_text
                if intent_terms:
                    effective_user_query = " ".join(
                        part for part in [effective_user_query, *intent_terms] if part
                    )
                if requires_multi_source:
                    for token in ("更多来源", "交叉验证"):
                        if token not in effective_user_query:
                            effective_user_query = f"{effective_user_query} {token}".strip()
                return ResearchContinuationContext(
                    active=True,
                    family="web_research",
                    origin="initial",
                    current_user_text=current_user_text,
                    effective_user_query=effective_user_query,
                    research_target_text=current_user_text,
                    recent_successful_tool_names=recent_successful_tool_names,
                    recent_web_queries=recent_web_queries,
                    requires_multi_source=requires_multi_source,
                )
            return ResearchContinuationContext(
                current_user_text=current_user_text,
                recent_successful_tool_names=recent_successful_tool_names,
                recent_web_queries=recent_web_queries,
                requires_multi_source=requires_multi_source,
            )

        is_continuation = cls._is_web_research_continuation_text(
            current_user_text,
        ) or cls._contains_entity_reference(current_user_text)
        if not is_continuation:
            return ResearchContinuationContext(
                current_user_text=current_user_text,
                recent_successful_tool_names=recent_successful_tool_names,
                recent_web_queries=recent_web_queries,
                requires_multi_source=requires_multi_source,
            )

        research_target_text = (
            recent_web_queries[0]
            if recent_web_queries
            else cls._extract_last_substantive_user_query(prior_messages)
        )

        if (
            cls._contains_entity_reference(current_user_text)
            or cls._is_web_research_continuation_text(current_user_text)
        ):
            effective_user_query = research_target_text or current_user_text
        else:
            effective_user_query = current_user_text

        if intent_terms:
            effective_user_query = " ".join(
                part
                for part in [effective_user_query, *intent_terms]
                if part
            )

        if requires_multi_source:
            for token in ("更多来源", "交叉验证"):
                if token not in effective_user_query:
                    effective_user_query = f"{effective_user_query} {token}".strip()

        return ResearchContinuationContext(
            active=True,
            family="web_research",
            origin="continuation",
            current_user_text=current_user_text,
            effective_user_query=effective_user_query,
            research_target_text=research_target_text,
            recent_successful_tool_names=recent_successful_tool_names,
            recent_web_queries=recent_web_queries,
            requires_multi_source=requires_multi_source,
        )

    @classmethod
    def _build_web_research_retry_prompt(
        cls,
        continuation: ResearchContinuationContext | None,
    ) -> str:
        query = (
            continuation.effective_user_query
            if continuation and continuation.effective_user_query
            else ""
        )
        multi_source_note = (
            " The user asked for multi-source verification, so continue searching and/or fetching more sources before summarizing."
            if continuation and continuation.requires_multi_source
            else ""
        )
        query_note = f" Continue the research for: {query}." if query else ""
        return (
            "Correction: web_search and fetch_url are available in this turn."
            " Ignore any prior assistant claim that web research tools are unavailable."
            " Continue the external web research instead of replying with a capability explanation or switching to internal database tools."
            f"{query_note}{multi_source_note}"
        )

    @classmethod
    def _build_multi_source_retry_prompt(
        cls,
        continuation: ResearchContinuationContext | None,
        messages: list[ChatMessage],
        tools: list[ToolDefinition],
    ) -> str:
        search_queries, fetched_urls = cls._collect_web_research_evidence(messages)
        tool_names = {tool.name for tool in tools}
        query = (
            continuation.effective_user_query
            if continuation and continuation.effective_user_query
            else ""
        )

        if "fetch_url" in tool_names:
            inspected = len(fetched_urls)
            remaining = max(_WEB_RESEARCH_MULTI_SOURCE_MIN_FETCHES - inspected, 1)
            next_step = (
                f"Use fetch_url on at least {remaining} more distinct relevant URL(s) before writing the final answer."
            )
        else:
            inspected = len(search_queries)
            remaining = max(_WEB_RESEARCH_MULTI_SOURCE_MIN_FETCHES - inspected, 1)
            next_step = (
                f"Run web_search for at least {remaining} more distinct search pass(es) or query variants before writing the final answer."
            )

        query_note = f" Keep the research focused on: {query}." if query else ""
        return (
            "Correction: the user explicitly asked for multiple articles or source cross-verification. "
            f"You have only inspected {inspected} distinct source step(s) so far. "
            f"{next_step}"
            " Do not switch to internal database tools and do not finalize the answer yet."
            f"{query_note}"
        )

    @classmethod
    def _should_retry_web_research_denial(
        cls,
        response: ChatResponse,
        tools: list[ToolDefinition],
        continuation: ResearchContinuationContext | None,
    ) -> bool:
        if not continuation or not continuation.active:
            return False
        if continuation.family != "web_research":
            return False
        if response.tool_calls:
            return False
        tool_names = {tool.name for tool in tools}
        if "web_search" not in tool_names:
            return False
        return cls._is_web_research_capability_denial(
            response.message.content or "",
        )

    async def _retry_web_research_denial_if_needed(
        self,
        *,
        agent: Agent,
        messages: list[ChatMessage],
        response: ChatResponse,
        tools: list[ToolDefinition],
        request: ExecutionRequest,
        route_result: Any | None,
        continuation: ResearchContinuationContext | None,
        log_user_type: str | None,
    ) -> ChatResponse:
        if not self._should_retry_web_research_denial(
            response,
            tools,
            continuation,
        ):
            return response

        retry_prompt = self._build_web_research_retry_prompt(continuation)
        messages.append(
            ChatMessage(
                role="user",
                content=retry_prompt,
                internal_only=True,
            )
        )
        retry_response = await self._call_llm(
            agent=agent,
            messages=messages,
            tools=tools,
            tenant_id=request.tenant_id,
            user_id=request.user_id,
            conversation_id=request.conversation_id,
            billing_context=request.billing_context,
            route_result=route_result,
            log_user_type=log_user_type,
        )
        if response.total_tokens is not None and retry_response.total_tokens is not None:
            retry_response.total_tokens += response.total_tokens
        return retry_response

    async def _retry_web_research_multi_source_if_needed(
        self,
        *,
        agent: Agent,
        messages: list[ChatMessage],
        response: ChatResponse,
        tools: list[ToolDefinition],
        request: ExecutionRequest,
        route_result: Any | None,
        continuation: ResearchContinuationContext | None,
        log_user_type: str | None,
    ) -> ChatResponse:
        retry_response = response
        accumulated_tokens = response.total_tokens or 0
        attempts = 0

        while (
            not retry_response.tool_calls
            and attempts < 2
            and self._needs_more_web_research_sources(
                messages,
                tools,
                continuation,
            )
        ):
            attempts += 1
            messages.append(
                ChatMessage(
                    role="user",
                    content=self._build_multi_source_retry_prompt(
                        continuation,
                        messages,
                        tools,
                    ),
                    internal_only=True,
                )
            )
            retry_response = await self._call_llm(
                agent=agent,
                messages=messages,
                tools=tools,
                tenant_id=request.tenant_id,
                user_id=request.user_id,
                conversation_id=request.conversation_id,
                billing_context=request.billing_context,
                route_result=route_result,
                log_user_type=log_user_type,
            )
            accumulated_tokens += retry_response.total_tokens or 0
            retry_response.total_tokens = accumulated_tokens

        return retry_response

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
        )

        rag_sources = None
        agent_kb_ids, agent_kb_weights = await load_agent_kb_bindings(
            self.db,
            agent.id,
            request.tenant_id,
        )
        # User-selected KB ids (already sanitized to bound subset in AgentChatService) narrow retrieval.
        # 用户选中的知识库（已在 AgentChatService 校验为绑定子集）用于收窄检索范围。
        if request.knowledge_base_ids:
            sel = set(request.knowledge_base_ids)
            merged_kb_ids = [kid for kid in (agent_kb_ids or []) if kid in sel]
            if not merged_kb_ids:
                merged_kb_ids = agent_kb_ids
        else:
            merged_kb_ids = agent_kb_ids
        effective_rag_config = agent.rag_config or {}
        if merged_kb_ids:
            messages, rag_sources = await inject_rag_context(
                self.db,
                agent,
                messages,
                request.tenant_id,
                kb_ids=merged_kb_ids,
                rag_config=effective_rag_config or None,
                kb_weights=agent_kb_weights,
            )

        # 4. Get tool list + expand dedicated page tools (before optimize) + optimize / 上文为英文说明 / English above
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
        )

        # 4.5 Enhance tool schemas with page context (enum/default) / 用页面上下文增强工具 Schema
        if all_tools:
            from app.ai.tools.enhancer import enhance_tools_with_page_context

            enhance_tools_with_page_context(all_tools, request.input_variables)

        optimize_event: dict[str, Any] | None = None
        if all_tools:
            user_query = continuation_context.effective_user_query or ""
            if not user_query:
                for _m in reversed(messages):
                    if _m.role == "user":
                        user_query = _m.content or ""
                        break
            from app.ai.tools.optimizer import optimize_tools

            opt = optimize_tools(
                all_tools,
                user_query,
                used_tool_names=set(
                    continuation_context.recent_successful_tool_names,
                )
                or None,
                preferred_family=continuation_context.family
                if continuation_context.active
                else None,
            )
            tools = opt.tools
            if not opt.skipped:
                optimize_event = {"total": opt.total, "selected": opt.selected}

        # 5. Inject tool awareness hint / 注入工具感知提示
        if tools:
            self._inject_tool_awareness(
                messages,
                tools,
                request.input_variables,
                continuation_context=continuation_context,
            )

        # 6. Extract consent_modes / 提取 consent_modes
        tool_consent_modes = skill_result.tool_consent_modes if skill_result else {}

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

        return PreparedExecution(
            messages=messages,
            tools=tools,
            all_tools=all_tools,
            continuation_context=continuation_context,
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
        conversation_id: int | None = None,
        billing_context: dict[str, Any] | None = None,
        route_result: Any | None = None,
        log_user_type: str | None = None,
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
            all_tools=all_tools,
            consent_modes=tool_consent_modes or {},
        )

        all_tool_results: list[ToolResult] = []
        total_tokens = response.total_tokens or 0
        current_response = response
        multi_source_retry_count = 0
        max_multi_source_retries = 2

        for _round in range(MAX_TOOL_CALL_ROUNDS):
            tool_calls = current_response.tool_calls
            if not tool_calls:
                break

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

            # Execute each tool call (using ToolCallProcessor shared logic) / 执行每个工具调用（使用 ToolCallProcessor 共享逻辑）
            # consent_mode pre-check: same semantic as stream path / consent_mode 前置检查：与流式路径语义一致
            for tc in tool_calls:
                tc_id = tc.get("id", "")
                func = tc.get("function", {})
                func_name = func.get("name", "")
                raw_args = func.get("arguments", "{}")
                arguments, parse_error = processor.parse_arguments(raw_args)

                # consent_mode check only when args parse ok (else process_single handles parse error) / 上文为英文说明 / English above
                if not parse_error:
                    _skill_info = processor.get_skill_info(func_name)
                    processor.annotate_tool_call(tc, skill_info=_skill_info)
                    _consent = processor.check_consent(func_name)
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
                        )

                single = await processor.process_single(
                    tc,
                    conversation_id=request.conversation_id or 0,
                )
                if single.tool_result:
                    all_tool_results.append(single.tool_result)
                    processor.annotate_tool_call(
                        tc,
                        duration_ms=single.duration_ms,
                        result=single.tool_result,
                        skill_info=processor.get_skill_info(func_name),
                    )
                    _conf_data = processor.check_confirmation_output(single.tool_result)
                    if _conf_data:
                        processor.annotate_tool_call(
                            tc,
                            pending_confirmation=processor.build_pending_confirmation_payload(
                                _conf_data,
                            ),
                        )
                if single.tool_message:
                    messages.append(single.tool_message)
                if single.follow_up_message:
                    follow_up_messages.append(single.follow_up_message)

            if follow_up_messages:
                messages.extend(follow_up_messages)

            if skip_final_call:
                if _round < MAX_TOOL_CALL_ROUNDS - 1:
                    peek_response = await self._call_llm(
                        agent=agent,
                        messages=messages,
                        tools=tools,
                        tenant_id=request.tenant_id,
                        user_id=request.user_id,
                        conversation_id=request.conversation_id,
                        billing_context=request.billing_context,
                        route_result=route_result,
                        log_user_type=log_user_type_for_call_log(request.user_role),
                    )
                    total_tokens += peek_response.total_tokens or 0
                    while (
                        not peek_response.tool_calls
                        and multi_source_retry_count < max_multi_source_retries
                        and self._needs_more_web_research_sources(
                            messages,
                            tools,
                            continuation_context,
                        )
                    ):
                        multi_source_retry_count += 1
                        messages.append(
                            ChatMessage(
                                role="user",
                                content=self._build_multi_source_retry_prompt(
                                    continuation_context,
                                    messages,
                                    tools,
                                ),
                                internal_only=True,
                            )
                        )
                        peek_response = await self._call_llm(
                            agent=agent,
                            messages=messages,
                            tools=tools,
                            tenant_id=request.tenant_id,
                            user_id=request.user_id,
                            conversation_id=request.conversation_id,
                            billing_context=request.billing_context,
                            route_result=route_result,
                            log_user_type=log_user_type_for_call_log(
                                request.user_role
                            ),
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
                conversation_id=request.conversation_id,
                billing_context=request.billing_context,
                route_result=route_result,
                log_user_type=log_user_type_for_call_log(request.user_role),
            )
            total_tokens += current_response.total_tokens or 0
            while (
                not current_response.tool_calls
                and multi_source_retry_count < max_multi_source_retries
                and self._needs_more_web_research_sources(
                    messages,
                    tools,
                    continuation_context,
                )
            ):
                multi_source_retry_count += 1
                messages.append(
                    ChatMessage(
                        role="user",
                        content=self._build_multi_source_retry_prompt(
                            continuation_context,
                            messages,
                            tools,
                        ),
                        internal_only=True,
                    )
                )
                current_response = await self._call_llm(
                    agent=agent,
                    messages=messages,
                    tools=tools,
                    tenant_id=request.tenant_id,
                    user_id=request.user_id,
                    conversation_id=request.conversation_id,
                    billing_context=request.billing_context,
                    route_result=route_result,
                    log_user_type=log_user_type_for_call_log(request.user_role),
                )
                total_tokens += current_response.total_tokens or 0

        return current_response, all_tool_results, total_tokens

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


__all__ = ["BaseEngine", "log_user_type_for_call_log"]
