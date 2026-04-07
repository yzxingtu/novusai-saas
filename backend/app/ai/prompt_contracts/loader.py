"""Prompt contract registry and renderer / Prompt 契约注册表与渲染器。

What this module does / 本模块职责：
- ``PromptContractName``: stable string ids, each maps to one file under ``resources/``.
  / 枚举契约 ID，与 ``resources/*.md`` 模板一一对应。
- ``_PROMPT_CONTRACTS``: maps id → template filename + short description for maintainers.
  / 注册表：id → 模板文件名 + 简述（给人看的元数据，不参与渲染）。
- ``render_prompt_contract(name, **kwargs)``: render Jinja2 and return stripped text for callers
  (engine, router, capability builder, etc.). / 按名渲染 Jinja，返回去首尾空白的字符串，供引擎等拼接提示词。

Pass ``name`` as the contract id (usually ``PromptContractName.X.value``) and template variables as kwargs.
/ 调用时 ``name`` 传契约 id（常用枚举的 ``.value``），其余关键字参数传入模板变量。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from functools import cache
from pathlib import Path

from jinja2 import ChainableUndefined, Environment, FileSystemLoader

# Jinja template root (mostly ``*.md`` next to this package) / Jinja 模板根目录（同目录 resources，多为 md）
_RESOURCE_DIR = Path(__file__).resolve().parent / "resources"
# Shared loader: keep final newline; undefined keys chain to empty string / 共享加载器：保留末尾换行；未定义变量链式为空
_ENV = Environment(
    loader=FileSystemLoader(str(_RESOURCE_DIR)),
    keep_trailing_newline=True,
    undefined=ChainableUndefined,
)


class PromptContractName(StrEnum):
    """Stable template ids (``resources/*.md``) / 契约模板标识（对应 ``resources/*.md``）。"""

    # --- Tool runtime & contract recovery / 工具运行时与契约恢复 ---
    TOOL_RUNTIME_SUMMARY = "tool_runtime_summary"
    TOOL_USAGE_RULES = "tool_usage_rules"
    CONTRACT_RECOVERY = "contract_recovery"
    PARTIAL_EXIT = "partial_exit"

    # --- Page workflow & cross-page navigation / 页面工作流与跨页导航 ---
    PAGE_WORKFLOW_BASIC = "page_workflow_basic"
    PAGE_WORKFLOW_REMOTE_SELECT = "page_workflow_remote_select"
    NAVIGATION_CONTINUATION = "navigation_continuation"
    PAGE_OPERATIONS_DEDICATED = "page_operations_dedicated"
    PAGE_OPERATIONS_FALLBACK = "page_operations_fallback"

    # --- Domain capability blocks (web / weather / time) / 领域能力块 ---
    WEB_RESEARCH = "web_research"
    WEATHER_TOOLS = "weather_tools"
    TIME_TOOLS = "time_tools"

    # --- Turn capability & research state / 轮次能力与调研状态 ---
    CAPABILITY_REPORTING = "capability_reporting"
    TURN_CAPABILITIES = "turn_capabilities"
    ORDERED_CAPABILITY_INTENT = "ordered_capability_intent"
    RESEARCH_STATE = "research_state"
    PAGE_FLOW_RECOVERY = "page_flow_recovery"

    # --- Fetch gate & page-op HTML relay / 抓取门禁与页面操作 HTML 透传 ---
    FETCH_URL_GATE = "fetch_url_gate"
    PAGE_OPERATION_HTML_RELAY = "page_operation_html_relay"

    # --- Agent loop: form fill / validate / Agent 循环：表单填充与校验 ---
    PAGE_OPERATION_FORM_ALREADY_OPEN = "page_operation_form_already_open"
    PAGE_OPERATION_FILL_REMAINING = "page_operation_fill_remaining"
    PAGE_OPERATION_FILL_READY = "page_operation_fill_ready"
    PAGE_OPERATION_VALIDATE_PASSED = "page_operation_validate_passed"
    PAGE_OPERATION_VALIDATE_FAILED = "page_operation_validate_failed"
    PAGE_OPERATION_FORM_OPENED = "page_operation_form_opened"
    PAGE_OPERATION_FORM_CLOSED = "page_operation_form_closed"

    # --- Agent loop: navigation follow-up / Agent 循环：导航后续 ---
    PAGE_OPERATION_NAV_READY = "page_operation_nav_ready"
    PAGE_OPERATION_NAV_DISABLED = "page_operation_nav_disabled"
    PAGE_OPERATION_NAV_PENDING = "page_operation_nav_pending"
    PAGE_OPERATION_NAV_AVAILABLE_OPS = "page_operation_nav_available_ops"
    PAGE_OPERATION_NAV_CONTINUE_NOW = "page_operation_nav_continue_now"
    PAGE_OPERATION_NAV_REASON = "page_operation_nav_reason"

    # --- RAG helper prompts (rewrite / HyDE / rerank) / RAG 辅助提示（改写、HyDE、重排）---
    RAG_MULTI_QUERY_SYSTEM = "rag_multi_query_system"
    RAG_HYDE_SYSTEM = "rag_hyde_system"
    RAG_RERANKER_SYSTEM = "rag_reranker_system"
    RAG_RERANKER_USER = "rag_reranker_user"

    # --- Memory extraction & agent router / 记忆抽取与智能体路由 ---
    MEMORY_EXTRACTION = "memory_extraction"
    AGENT_ROUTER_SELECTION = "agent_router_selection"

    # --- Capability summary fragments (builder) / 能力摘要片段（构建器用）---
    CAPABILITY_PAGE_CURRENT = "capability_page_current"
    CAPABILITY_PAGE_OPERATIONS = "capability_page_operations"
    CAPABILITY_MEMORY_SESSION = "capability_memory_session"
    CAPABILITY_MEMORY_LONG_TERM = "capability_memory_long_term"
    PAGE_LOCALE_THINKING = "page_locale_thinking"
    PAGE_WORKFLOW_INTRO = "page_workflow_intro"

    # --- Page-aware execution discipline & extra page-op hints / 页面感知执行纪律与扩展页面操作说明 ---
    EXECUTION_DISCIPLINE = "execution_discipline"
    PAGE_OPERATIONS_DATA_DISTINCTION = "page_operations_data_distinction"
    PAGE_OPERATIONS_SCREENSHOT_DEDICATED = "page_operations_screenshot_dedicated"
    PAGE_OPERATIONS_SCREENSHOT_FALLBACK = "page_operations_screenshot_fallback"
    PAGE_OPERATIONS_OTHER_OPS = "page_operations_other_ops"
    PAGE_OPERATIONS_MUTATION = "page_operations_mutation"
    PAGE_OPERATIONS_EDITOR_FLOW = "page_operations_editor_flow"
    CONTRACT_RECOVERY_LEAK_GUIDANCE = "contract_recovery_leak_guidance"

    # --- Router preambles & repeated page context / 路由前言与重复页面上下文 ---
    AGENT_ROUTER_VISION_PREAMBLE = "agent_router_vision_preamble"
    AGENT_ROUTER_ATTACHMENT_PREAMBLE = "agent_router_attachment_preamble"
    PAGE_CONTEXT_REPEATED = "page_context_repeated"
    PAGE_CONTEXT_UNAVAILABLE = "page_context_unavailable"

    # --- Builtin tools & toolkit-style tools / 内置工具与类 toolkit 工具描述 ---
    BUILTIN_WEB_SEARCH_DESCRIPTION = "builtin_web_search_description"
    BUILTIN_FETCH_URL_DESCRIPTION = "builtin_fetch_url_description"
    BUILTIN_CURRENT_TIME_DESCRIPTION = "builtin_current_time_description"
    EMAIL_TOOL_DESCRIPTION = "email_tool_description"
    EXECUTE_CODE_TOOL_DESCRIPTION = "execute_code_tool_description"
    PAGE_TOOL_EXPANDER_NAVIGATE = "page_tool_expander_navigate"


@dataclass(frozen=True)
class PromptContractSpec:
    """One registered contract: enum, file, short description / 单条注册：枚举名、模板文件、简述。

    ``description`` is for humans maintaining this file; it is not sent to the model.
    / ``description`` 仅供维护者阅读，不会传给模型。
    """

    name: PromptContractName
    template_name: str
    description: str


# Maps contract id → template + maintainer note (aligned with enum sections below) / 契约 id → 模板与说明（分组与上方枚举一致）
_PROMPT_CONTRACTS: dict[str, PromptContractSpec] = {
    # --- Tool runtime & contract recovery / 工具运行时与契约恢复 ---
    PromptContractName.TOOL_RUNTIME_SUMMARY.value: PromptContractSpec(
        name=PromptContractName.TOOL_RUNTIME_SUMMARY,
        template_name="tool_runtime_summary.md",
        description="Compact orchestration runtime summary for the current turn.",
    ),
    PromptContractName.TOOL_USAGE_RULES.value: PromptContractSpec(
        name=PromptContractName.TOOL_USAGE_RULES,
        template_name="tool_usage_rules.md",
        description="Compact tool execution rules used when capability summary is suppressed.",
    ),
    PromptContractName.CONTRACT_RECOVERY.value: PromptContractSpec(
        name=PromptContractName.CONTRACT_RECOVERY,
        template_name="contract_recovery.md",
        description="Recovery prompt injected after tool-contract breaches.",
    ),
    PromptContractName.PARTIAL_EXIT.value: PromptContractSpec(
        name=PromptContractName.PARTIAL_EXIT,
        template_name="partial_exit.md",
        description="User-facing summary returned when orchestration exits partially.",
    ),
    # --- Page workflow & cross-page navigation / 页面工作流与跨页导航 ---
    PromptContractName.PAGE_WORKFLOW_BASIC.value: PromptContractSpec(
        name=PromptContractName.PAGE_WORKFLOW_BASIC,
        template_name="page_workflow_basic.md",
        description="Baseline page form workflow guidance for page context output.",
    ),
    PromptContractName.PAGE_WORKFLOW_REMOTE_SELECT.value: PromptContractSpec(
        name=PromptContractName.PAGE_WORKFLOW_REMOTE_SELECT,
        template_name="page_workflow_remote_select.md",
        description="Page form workflow guidance when remote option fields are present.",
    ),
    PromptContractName.NAVIGATION_CONTINUATION.value: PromptContractSpec(
        name=PromptContractName.NAVIGATION_CONTINUATION,
        template_name="navigation_continuation.md",
        description="Cross-page navigation continuation guidance for page-aware turns.",
    ),
    # --- Dedicated vs fallback page-op blocks / 专用与回退页面操作块 ---
    PromptContractName.PAGE_OPERATIONS_DEDICATED.value: PromptContractSpec(
        name=PromptContractName.PAGE_OPERATIONS_DEDICATED,
        template_name="page_operations_dedicated.md",
        description="Dedicated page operations guidance block.",
    ),
    PromptContractName.PAGE_OPERATIONS_FALLBACK.value: PromptContractSpec(
        name=PromptContractName.PAGE_OPERATIONS_FALLBACK,
        template_name="page_operations_fallback.md",
        description="Fallback page operations guidance block.",
    ),
    # --- Domain capability blocks (web / weather / time) / 领域能力块 ---
    PromptContractName.WEB_RESEARCH.value: PromptContractSpec(
        name=PromptContractName.WEB_RESEARCH,
        template_name="web_research.md",
        description="Web research guidance block.",
    ),
    PromptContractName.WEATHER_TOOLS.value: PromptContractSpec(
        name=PromptContractName.WEATHER_TOOLS,
        template_name="weather_tools.md",
        description="Weather tool guidance block.",
    ),
    PromptContractName.TIME_TOOLS.value: PromptContractSpec(
        name=PromptContractName.TIME_TOOLS,
        template_name="time_tools.md",
        description="Time tool guidance block.",
    ),
    # --- Turn capability & research state / 轮次能力与调研状态 ---
    PromptContractName.CAPABILITY_REPORTING.value: PromptContractSpec(
        name=PromptContractName.CAPABILITY_REPORTING,
        template_name="capability_reporting.md",
        description="Capability reporting block.",
    ),
    PromptContractName.TURN_CAPABILITIES.value: PromptContractSpec(
        name=PromptContractName.TURN_CAPABILITIES,
        template_name="turn_capabilities.md",
        description="Turn-specific runtime capability block.",
    ),
    PromptContractName.ORDERED_CAPABILITY_INTENT.value: PromptContractSpec(
        name=PromptContractName.ORDERED_CAPABILITY_INTENT,
        template_name="ordered_capability_intent.md",
        description="Ordered multi-capability intent block.",
    ),
    PromptContractName.RESEARCH_STATE.value: PromptContractSpec(
        name=PromptContractName.RESEARCH_STATE,
        template_name="research_state.md",
        description="Research continuation state block.",
    ),
    # --- Page-flow recovery & fetch-before-summary gate / 页面流恢复与先抓取再总结门禁 ---
    PromptContractName.PAGE_FLOW_RECOVERY.value: PromptContractSpec(
        name=PromptContractName.PAGE_FLOW_RECOVERY,
        template_name="page_flow_recovery.md",
        description="Page-flow recovery block after no-progress rounds.",
    ),
    PromptContractName.FETCH_URL_GATE.value: PromptContractSpec(
        name=PromptContractName.FETCH_URL_GATE,
        template_name="fetch_url_gate.md",
        description="Enforced fetch-before-summary gate for web research.",
    ),
    # --- Page operation: HTML relay & form/validate loop / 页面操作：HTML 透传与表单校验循环 ---
    PromptContractName.PAGE_OPERATION_HTML_RELAY.value: PromptContractSpec(
        name=PromptContractName.PAGE_OPERATION_HTML_RELAY,
        template_name="page_operation_html_relay.md",
        description="Internal HTML relay warning for page operations.",
    ),
    PromptContractName.PAGE_OPERATION_FORM_ALREADY_OPEN.value: PromptContractSpec(
        name=PromptContractName.PAGE_OPERATION_FORM_ALREADY_OPEN,
        template_name="page_operation_form_already_open.md",
        description="Agent loop guidance when form is already open.",
    ),
    PromptContractName.PAGE_OPERATION_FILL_REMAINING.value: PromptContractSpec(
        name=PromptContractName.PAGE_OPERATION_FILL_REMAINING,
        template_name="page_operation_fill_remaining.md",
        description="Agent loop guidance for remaining empty form fields.",
    ),
    PromptContractName.PAGE_OPERATION_FILL_READY.value: PromptContractSpec(
        name=PromptContractName.PAGE_OPERATION_FILL_READY,
        template_name="page_operation_fill_ready.md",
        description="Agent loop guidance when form appears filled.",
    ),
    PromptContractName.PAGE_OPERATION_VALIDATE_PASSED.value: PromptContractSpec(
        name=PromptContractName.PAGE_OPERATION_VALIDATE_PASSED,
        template_name="page_operation_validate_passed.md",
        description="Agent loop guidance after validation success.",
    ),
    PromptContractName.PAGE_OPERATION_VALIDATE_FAILED.value: PromptContractSpec(
        name=PromptContractName.PAGE_OPERATION_VALIDATE_FAILED,
        template_name="page_operation_validate_failed.md",
        description="Agent loop guidance after validation failure.",
    ),
    PromptContractName.PAGE_OPERATION_FORM_OPENED.value: PromptContractSpec(
        name=PromptContractName.PAGE_OPERATION_FORM_OPENED,
        template_name="page_operation_form_opened.md",
        description="Agent loop guidance when a form just opened.",
    ),
    PromptContractName.PAGE_OPERATION_FORM_CLOSED.value: PromptContractSpec(
        name=PromptContractName.PAGE_OPERATION_FORM_CLOSED,
        template_name="page_operation_form_closed.md",
        description="Agent loop guidance when a form just closed.",
    ),
    # --- Page operation: navigation follow-up / 页面操作：导航后续 ---
    PromptContractName.PAGE_OPERATION_NAV_READY.value: PromptContractSpec(
        name=PromptContractName.PAGE_OPERATION_NAV_READY,
        template_name="page_operation_nav_ready.md",
        description="Navigation guidance when destination is ready.",
    ),
    PromptContractName.PAGE_OPERATION_NAV_DISABLED.value: PromptContractSpec(
        name=PromptContractName.PAGE_OPERATION_NAV_DISABLED,
        template_name="page_operation_nav_disabled.md",
        description="Navigation guidance when destination is ready but auto-continuation is disabled.",
    ),
    PromptContractName.PAGE_OPERATION_NAV_PENDING.value: PromptContractSpec(
        name=PromptContractName.PAGE_OPERATION_NAV_PENDING,
        template_name="page_operation_nav_pending.md",
        description="Navigation guidance when destination is pending.",
    ),
    PromptContractName.PAGE_OPERATION_NAV_AVAILABLE_OPS.value: PromptContractSpec(
        name=PromptContractName.PAGE_OPERATION_NAV_AVAILABLE_OPS,
        template_name="page_operation_nav_available_ops.md",
        description="Navigation follow-up listing available operations.",
    ),
    PromptContractName.PAGE_OPERATION_NAV_CONTINUE_NOW.value: PromptContractSpec(
        name=PromptContractName.PAGE_OPERATION_NAV_CONTINUE_NOW,
        template_name="page_operation_nav_continue_now.md",
        description="Navigation follow-up for immediate continuation.",
    ),
    PromptContractName.PAGE_OPERATION_NAV_REASON.value: PromptContractSpec(
        name=PromptContractName.PAGE_OPERATION_NAV_REASON,
        template_name="page_operation_nav_reason.md",
        description="Navigation follow-up describing readiness reason.",
    ),
    # --- RAG helper prompts (rewrite / HyDE / rerank) / RAG 辅助提示 ---
    PromptContractName.RAG_MULTI_QUERY_SYSTEM.value: PromptContractSpec(
        name=PromptContractName.RAG_MULTI_QUERY_SYSTEM,
        template_name="rag_multi_query_system.md",
        description="System prompt for multi-query rewriting.",
    ),
    PromptContractName.RAG_HYDE_SYSTEM.value: PromptContractSpec(
        name=PromptContractName.RAG_HYDE_SYSTEM,
        template_name="rag_hyde_system.md",
        description="System prompt for HyDE rewriting.",
    ),
    PromptContractName.RAG_RERANKER_SYSTEM.value: PromptContractSpec(
        name=PromptContractName.RAG_RERANKER_SYSTEM,
        template_name="rag_reranker_system.md",
        description="System prompt for reranker scoring.",
    ),
    PromptContractName.RAG_RERANKER_USER.value: PromptContractSpec(
        name=PromptContractName.RAG_RERANKER_USER,
        template_name="rag_reranker_user.md",
        description="User prompt for reranker scoring.",
    ),
    # --- Memory extraction & agent router / 记忆抽取与路由选择 ---
    PromptContractName.MEMORY_EXTRACTION.value: PromptContractSpec(
        name=PromptContractName.MEMORY_EXTRACTION,
        template_name="memory_extraction.md",
        description="Prompt for extracting memory-worthy facts from a turn.",
    ),
    PromptContractName.AGENT_ROUTER_SELECTION.value: PromptContractSpec(
        name=PromptContractName.AGENT_ROUTER_SELECTION,
        template_name="agent_router_selection.md",
        description="Prompt for selecting the best router agent candidate.",
    ),
    # --- Capability summary fragments (builder) / 能力摘要片段 ---
    PromptContractName.CAPABILITY_PAGE_CURRENT.value: PromptContractSpec(
        name=PromptContractName.CAPABILITY_PAGE_CURRENT,
        template_name="capability_page_current.md",
        description="Page context item describing the current page.",
    ),
    PromptContractName.CAPABILITY_PAGE_OPERATIONS.value: PromptContractSpec(
        name=PromptContractName.CAPABILITY_PAGE_OPERATIONS,
        template_name="capability_page_operations.md",
        description="Page context item describing available operations.",
    ),
    PromptContractName.CAPABILITY_MEMORY_SESSION.value: PromptContractSpec(
        name=PromptContractName.CAPABILITY_MEMORY_SESSION,
        template_name="capability_memory_session.md",
        description="Session memory capability item.",
    ),
    PromptContractName.CAPABILITY_MEMORY_LONG_TERM.value: PromptContractSpec(
        name=PromptContractName.CAPABILITY_MEMORY_LONG_TERM,
        template_name="capability_memory_long_term.md",
        description="Long-term memory capability item.",
    ),
    PromptContractName.PAGE_LOCALE_THINKING.value: PromptContractSpec(
        name=PromptContractName.PAGE_LOCALE_THINKING,
        template_name="page_locale_thinking.md",
        description="Page-locale guidance for visible thinking and final answer language.",
    ),
    # --- Page workflow intro & execution discipline & extra page-op hints / 页面流程引言、执行纪律与扩展页面操作 ---
    PromptContractName.PAGE_WORKFLOW_INTRO.value: PromptContractSpec(
        name=PromptContractName.PAGE_WORKFLOW_INTRO,
        template_name="page_workflow_intro.md",
        description="Intro guidance for page form workflows.",
    ),
    PromptContractName.EXECUTION_DISCIPLINE.value: PromptContractSpec(
        name=PromptContractName.EXECUTION_DISCIPLINE,
        template_name="execution_discipline.md",
        description="Execution discipline block for page-aware turns.",
    ),
    PromptContractName.PAGE_OPERATIONS_DATA_DISTINCTION.value: PromptContractSpec(
        name=PromptContractName.PAGE_OPERATIONS_DATA_DISTINCTION,
        template_name="page_operations_data_distinction.md",
        description="Data-vs-page operation distinction note.",
    ),
    PromptContractName.PAGE_OPERATIONS_SCREENSHOT_DEDICATED.value: PromptContractSpec(
        name=PromptContractName.PAGE_OPERATIONS_SCREENSHOT_DEDICATED,
        template_name="page_operations_screenshot_dedicated.md",
        description="Screenshot rule for dedicated page operations.",
    ),
    PromptContractName.PAGE_OPERATIONS_SCREENSHOT_FALLBACK.value: PromptContractSpec(
        name=PromptContractName.PAGE_OPERATIONS_SCREENSHOT_FALLBACK,
        template_name="page_operations_screenshot_fallback.md",
        description="Screenshot rule for fallback page operations.",
    ),
    PromptContractName.PAGE_OPERATIONS_OTHER_OPS.value: PromptContractSpec(
        name=PromptContractName.PAGE_OPERATIONS_OTHER_OPS,
        template_name="page_operations_other_ops.md",
        description="Fallback invoke_page_operation list for non-expanded page ops.",
    ),
    PromptContractName.PAGE_OPERATIONS_MUTATION.value: PromptContractSpec(
        name=PromptContractName.PAGE_OPERATIONS_MUTATION,
        template_name="page_operations_mutation.md",
        description="Mutation guidance for page operations.",
    ),
    PromptContractName.PAGE_OPERATIONS_EDITOR_FLOW.value: PromptContractSpec(
        name=PromptContractName.PAGE_OPERATIONS_EDITOR_FLOW,
        template_name="page_operations_editor_flow.md",
        description="Editor flow guidance for page operations.",
    ),
    # --- Contract leak recovery & router preambles & repeated context / 契约泄漏恢复、路由前言、重复上下文 ---
    PromptContractName.CONTRACT_RECOVERY_LEAK_GUIDANCE.value: PromptContractSpec(
        name=PromptContractName.CONTRACT_RECOVERY_LEAK_GUIDANCE,
        template_name="contract_recovery_leak_guidance.md",
        description="Leak-specific contract recovery guidance.",
    ),
    PromptContractName.AGENT_ROUTER_VISION_PREAMBLE.value: PromptContractSpec(
        name=PromptContractName.AGENT_ROUTER_VISION_PREAMBLE,
        template_name="agent_router_vision_preamble.md",
        description="Vision-specific router preamble.",
    ),
    PromptContractName.AGENT_ROUTER_ATTACHMENT_PREAMBLE.value: PromptContractSpec(
        name=PromptContractName.AGENT_ROUTER_ATTACHMENT_PREAMBLE,
        template_name="agent_router_attachment_preamble.md",
        description="Attachment preamble for router selection.",
    ),
    PromptContractName.PAGE_CONTEXT_REPEATED.value: PromptContractSpec(
        name=PromptContractName.PAGE_CONTEXT_REPEATED,
        template_name="page_context_repeated.md",
        description="Repeated page context warning within a single turn.",
    ),
    PromptContractName.PAGE_CONTEXT_UNAVAILABLE.value: PromptContractSpec(
        name=PromptContractName.PAGE_CONTEXT_UNAVAILABLE,
        template_name="page_context_unavailable.md",
        description="Tool output when execution variables carry no usable page_context.",
    ),
    # --- Builtin & email & code & page-tool expander / 内置工具、邮件、代码与页面工具展开 ---
    PromptContractName.BUILTIN_WEB_SEARCH_DESCRIPTION.value: PromptContractSpec(
        name=PromptContractName.BUILTIN_WEB_SEARCH_DESCRIPTION,
        template_name="builtin_web_search_description.md",
        description="Augmented description for web_search builtin tool.",
    ),
    PromptContractName.BUILTIN_FETCH_URL_DESCRIPTION.value: PromptContractSpec(
        name=PromptContractName.BUILTIN_FETCH_URL_DESCRIPTION,
        template_name="builtin_fetch_url_description.md",
        description="Augmented description for fetch_url builtin tool.",
    ),
    PromptContractName.BUILTIN_CURRENT_TIME_DESCRIPTION.value: PromptContractSpec(
        name=PromptContractName.BUILTIN_CURRENT_TIME_DESCRIPTION,
        template_name="builtin_current_time_description.md",
        description="Augmented description for get_current_time builtin tool.",
    ),
    PromptContractName.EMAIL_TOOL_DESCRIPTION.value: PromptContractSpec(
        name=PromptContractName.EMAIL_TOOL_DESCRIPTION,
        template_name="email_tool_description.md",
        description="Description for send_email tool.",
    ),
    PromptContractName.EXECUTE_CODE_TOOL_DESCRIPTION.value: PromptContractSpec(
        name=PromptContractName.EXECUTE_CODE_TOOL_DESCRIPTION,
        template_name="execute_code_tool_description.md",
        description="Description for execute_code tool.",
    ),
    PromptContractName.PAGE_TOOL_EXPANDER_NAVIGATE.value: PromptContractSpec(
        name=PromptContractName.PAGE_TOOL_EXPANDER_NAVIGATE,
        template_name="page_tool_expander_navigate.md",
        description="Additional navigate_menu guidance for expanded page tools.",
    ),
}


# --- Public API / 对外接口 ---


def render_prompt_contract(name: str, **kwargs: object) -> str:
    """Render a named contract template from ``resources/`` / 按名称渲染 ``resources/`` 下的契约模板。

    ``name`` must exist in ``_PROMPT_CONTRACTS``; kwargs are passed to Jinja ``render``.
    / ``name`` 须在注册表中；``kwargs`` 作为模板变量传入 Jinja。
    """
    spec = _PROMPT_CONTRACTS.get(str(name))
    if spec is None:
        raise KeyError(f"Unknown prompt contract: {name}")
    template = _get_template(spec.template_name)
    return template.render(**kwargs).strip()


@cache
def _get_template(template_name: str):
    """Load and cache a Jinja template by filename / 按文件名加载并缓存 Jinja 模板。"""
    return _ENV.get_template(template_name)


# Exported symbols for ``from app.ai.prompt_contracts import ...`` / 包导出符号
__all__ = ["PromptContractName", "render_prompt_contract"]
