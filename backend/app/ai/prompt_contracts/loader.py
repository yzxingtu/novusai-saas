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

import json
import re
from dataclasses import dataclass
from enum import StrEnum
from functools import cache
from pathlib import Path

from jinja2 import ChainableUndefined, Environment, FileSystemLoader

# Jinja template root (mostly ``*.md`` next to this package) / Jinja 模板根目录（同目录 resources，多为 md）
_RESOURCE_DIR = Path(__file__).resolve().parent / "resources"
# Shared loader: keep final newline; undefined keys chain to empty string / 共享加载器：保留末尾换行；未定义变量链式为空
# 中文: Prompt contract 模板输出纯文本给模型，不是浏览器 HTML；autoescape 会改变契约文本。
# EN: Prompt contract templates produce model-facing plain text, not browser HTML; autoescape would change contract text.
_ENV = Environment(
    loader=FileSystemLoader(str(_RESOURCE_DIR)),
    keep_trailing_newline=True,
    undefined=ChainableUndefined,
)  # nosec B701
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]+")
_WHITESPACE_RE = re.compile(r"\s+")


def _normalize_prompt_data(value: object) -> object:
    """中文: 将外部元数据压成不可跨行注入的 prompt 数据。

    EN: Fold external metadata into prompt-safe data that cannot inject new lines.
    """
    if isinstance(value, str):
        without_controls = _CONTROL_CHARS_RE.sub(" ", value)
        return _WHITESPACE_RE.sub(" ", without_controls).strip()
    if isinstance(value, dict):
        return {
            str(_normalize_prompt_data(key)): _normalize_prompt_data(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [_normalize_prompt_data(item) for item in value]
    return value


def _prompt_json(value: object) -> str:
    """中文: 将 prompt 元数据序列化为紧凑 JSON 字面量。

    EN: Serialize prompt metadata as compact JSON literals.
    """
    return json.dumps(
        _normalize_prompt_data(value),
        ensure_ascii=False,
        separators=(",", ":"),
    )


_ENV.filters["prompt_json"] = _prompt_json


class PromptContractName(StrEnum):
    """Stable template ids (``resources/*.md``) / 契约模板标识（对应 ``resources/*.md``）。"""

    # --- Tool runtime & contract recovery / 工具运行时与契约恢复 ---
    TOOL_RUNTIME_SUMMARY = "tool_runtime_summary"
    CONTRACT_RECOVERY = "contract_recovery"
    PARTIAL_EXIT = "partial_exit"

    # --- Domain capability blocks (time) / 领域能力块 ---
    TIME_TOOLS = "time_tools"

    # --- Turn capability & research state / 轮次能力与调研状态 ---
    TURN_CAPABILITIES = "turn_capabilities"

    # --- RAG helper prompts (rewrite / HyDE / rerank) / RAG 辅助提示（改写、HyDE、重排）---
    RAG_MULTI_QUERY_SYSTEM = "rag_multi_query_system"
    RAG_HYDE_SYSTEM = "rag_hyde_system"
    RAG_RERANKER_SYSTEM = "rag_reranker_system"
    RAG_RERANKER_USER = "rag_reranker_user"

    # --- Memory extraction & agent router / 记忆抽取与智能体路由 ---
    MEMORY_EXTRACTION = "memory_extraction"
    AGENT_ROUTER_SELECTION = "agent_router_selection"

    # --- Capability output locale / 能力输出语言 ---
    VISIBLE_OUTPUT_LOCALE = "visible_output_locale"

    # --- Contract leak recovery / 契约泄漏恢复 ---
    CONTRACT_RECOVERY_LEAK_GUIDANCE = "contract_recovery_leak_guidance"
    # --- Router preambles / 路由前言 ---
    AGENT_ROUTER_VISION_PREAMBLE = "agent_router_vision_preamble"
    AGENT_ROUTER_ATTACHMENT_PREAMBLE = "agent_router_attachment_preamble"

    # --- Builtin tools & toolkit-style tools / 内置工具与类 toolkit 工具描述 ---
    BUILTIN_CURRENT_TIME_DESCRIPTION = "builtin_current_time_description"
    EMAIL_TOOL_DESCRIPTION = "email_tool_description"
    EXECUTE_CODE_TOOL_DESCRIPTION = "execute_code_tool_description"

    # --- Rich-text editor AI actions / 富文本编辑器 AI 动作 ---
    RICH_TEXT_AI_ACTION_SYSTEM = "rich_text_ai_action_system"
    RICH_TEXT_AI_ACTION_USER = "rich_text_ai_action_user"
    RICH_TEXT_AI_ACTION_ENVELOPE = "rich_text_ai_action_envelope"


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
    PromptContractName.TIME_TOOLS.value: PromptContractSpec(
        name=PromptContractName.TIME_TOOLS,
        template_name="time_tools.md",
        description="Time tool guidance block.",
    ),
    # --- Turn capability & research state / 轮次能力与调研状态 ---
    PromptContractName.TURN_CAPABILITIES.value: PromptContractSpec(
        name=PromptContractName.TURN_CAPABILITIES,
        template_name="turn_capabilities.md",
        description="Turn-specific runtime capability block.",
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
    # --- Rich-text editor AI actions / 富文本编辑器 AI 动作 ---
    PromptContractName.RICH_TEXT_AI_ACTION_SYSTEM.value: PromptContractSpec(
        name=PromptContractName.RICH_TEXT_AI_ACTION_SYSTEM,
        template_name="rich_text_ai_action_system.md",
        description="System instructions for explicit rich-text editor AI actions.",
    ),
    PromptContractName.RICH_TEXT_AI_ACTION_USER.value: PromptContractSpec(
        name=PromptContractName.RICH_TEXT_AI_ACTION_USER,
        template_name="rich_text_ai_action_user.md",
        description="User prompt body for explicit rich-text editor AI actions.",
    ),
    PromptContractName.RICH_TEXT_AI_ACTION_ENVELOPE.value: PromptContractSpec(
        name=PromptContractName.RICH_TEXT_AI_ACTION_ENVELOPE,
        template_name="rich_text_ai_action_envelope.md",
        description="Ephemeral AgentChat request envelope for rich-text editor AI actions.",
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
