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

    # --- Page operation hints / 页面操作提示 ---
    PAGE_OPERATIONS_DEDICATED = "page_operations_dedicated"

    # --- Domain capability blocks (web / weather / time) / 领域能力块 ---
    WEB_RESEARCH = "web_research"
    WEATHER_TOOLS = "weather_tools"
    TIME_TOOLS = "time_tools"

    # --- Turn capability & research state / 轮次能力与调研状态 ---
    CAPABILITY_REPORTING = "capability_reporting"
    TURN_CAPABILITIES = "turn_capabilities"
    ORDERED_CAPABILITY_INTENT = "ordered_capability_intent"
    RESEARCH_STATE = "research_state"

    # --- Fetch gate / 抓取门禁 ---
    FETCH_URL_GATE = "fetch_url_gate"

    # --- RAG helper prompts (rewrite / HyDE / rerank) / RAG 辅助提示（改写、HyDE、重排）---
    RAG_MULTI_QUERY_SYSTEM = "rag_multi_query_system"
    RAG_HYDE_SYSTEM = "rag_hyde_system"
    RAG_RERANKER_SYSTEM = "rag_reranker_system"
    RAG_RERANKER_USER = "rag_reranker_user"

    # --- Memory extraction & agent router / 记忆抽取与智能体路由 ---
    MEMORY_EXTRACTION = "memory_extraction"
    AGENT_ROUTER_SELECTION = "agent_router_selection"

    # --- Capability output locale / 能力输出语言 ---
    PAGE_LOCALE_THINKING = "page_locale_thinking"
    VISIBLE_OUTPUT_LOCALE = "visible_output_locale"

    # --- Contract leak recovery / 契约泄漏恢复 ---
    CONTRACT_RECOVERY_LEAK_GUIDANCE = "contract_recovery_leak_guidance"
    CONTRACT_RECOVERY_WEB_RESEARCH_GUIDANCE = "contract_recovery_web_research_guidance"

    # --- Router preambles / 路由前言 ---
    AGENT_ROUTER_VISION_PREAMBLE = "agent_router_vision_preamble"
    AGENT_ROUTER_ATTACHMENT_PREAMBLE = "agent_router_attachment_preamble"

    # --- Builtin tools & toolkit-style tools / 内置工具与类 toolkit 工具描述 ---
    BUILTIN_WEB_SEARCH_DESCRIPTION = "builtin_web_search_description"
    BUILTIN_FETCH_URL_DESCRIPTION = "builtin_fetch_url_description"
    BUILTIN_CURRENT_TIME_DESCRIPTION = "builtin_current_time_description"
    EMAIL_TOOL_DESCRIPTION = "email_tool_description"
    EXECUTE_CODE_TOOL_DESCRIPTION = "execute_code_tool_description"
    HOSTED_WEB_SEARCH_CANDIDATE_INSTRUCTIONS = (
        "hosted_web_search_candidate_instructions"
    )


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
    # --- Dedicated page-op block / 专用页面操作块 ---
    PromptContractName.PAGE_OPERATIONS_DEDICATED.value: PromptContractSpec(
        name=PromptContractName.PAGE_OPERATIONS_DEDICATED,
        template_name="page_operations_dedicated.md",
        description="Dedicated page operations guidance block.",
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
    # --- Fetch-before-summary gate / 先抓取再总结门禁 ---
    PromptContractName.FETCH_URL_GATE.value: PromptContractSpec(
        name=PromptContractName.FETCH_URL_GATE,
        template_name="fetch_url_gate.md",
        description="Enforced fetch-before-summary gate for web research.",
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
    # --- Capability output locale / 能力输出语言 ---
    PromptContractName.PAGE_LOCALE_THINKING.value: PromptContractSpec(
        name=PromptContractName.PAGE_LOCALE_THINKING,
        template_name="page_locale_thinking.md",
        description="Page-locale guidance for visible thinking and final answer language.",
    ),
    PromptContractName.VISIBLE_OUTPUT_LOCALE.value: PromptContractSpec(
        name=PromptContractName.VISIBLE_OUTPUT_LOCALE,
        template_name="visible_output_locale.md",
        description="General visible-output language guidance for thinking and final answer.",
    ),
    # --- Contract leak recovery & router preambles / 契约泄漏恢复与路由前言 ---
    PromptContractName.CONTRACT_RECOVERY_LEAK_GUIDANCE.value: PromptContractSpec(
        name=PromptContractName.CONTRACT_RECOVERY_LEAK_GUIDANCE,
        template_name="contract_recovery_leak_guidance.md",
        description="Leak-specific contract recovery guidance.",
    ),
    PromptContractName.CONTRACT_RECOVERY_WEB_RESEARCH_GUIDANCE.value: PromptContractSpec(
        name=PromptContractName.CONTRACT_RECOVERY_WEB_RESEARCH_GUIDANCE,
        template_name="contract_recovery_web_research_guidance.md",
        description="Web-research-specific contract recovery guidance.",
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
    # --- Builtin & email & code tools / 内置工具、邮件与代码工具 ---
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
    PromptContractName.HOSTED_WEB_SEARCH_CANDIDATE_INSTRUCTIONS.value: (
        PromptContractSpec(
            name=PromptContractName.HOSTED_WEB_SEARCH_CANDIDATE_INSTRUCTIONS,
            template_name="hosted_web_search_candidate_instructions.md",
            description="Instructions for hosted Responses API web search candidates.",
        )
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
