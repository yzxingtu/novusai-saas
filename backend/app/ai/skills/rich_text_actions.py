"""
Rich-text AI action contracts / 富文本 AI 动作契约。

Defines stable action semantics used by editor APIs and skill-package catalog
metadata. Runtime callers resolve system.ai_writing and send the rendered action
message through global AgentChat/conversation routes.
/ 定义编辑器 API 与技能包目录元数据复用的稳定动作语义。运行时调用方解析
system.ai_writing，并通过全局 AgentChat/会话路由发送渲染后的动作消息。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from app.ai.prompt_contracts import PromptContractName, render_prompt_contract
from app.enums.agent import SkillTypeEnum
from app.enums.skill import SkillSourceTypeEnum, SkillStatusEnum

RICH_TEXT_AI_FEATURE_CODE = "system.ai_writing"
RICH_TEXT_AI_PACKAGE_NAME = "NovusDoc Rich Text AI"
RICH_TEXT_AI_PACKAGE_SOURCE_PLUGIN = "novusdoc"
RICH_TEXT_AI_SKILL_KEY = "novusdoc.rich_text_ai.actions"
RICH_TEXT_AI_CONTRACT_VERSION = "2026-05-05"

MAX_BEFORE_TEXT = 2000
MAX_AFTER_TEXT = 500
MAX_SELECTED_TEXT = 5000
MAX_INSTRUCTION = 1000


@dataclass(frozen=True, slots=True)
class RichTextAIActionTemplate:
    """富文本 AI 动作模板 / Rich-text AI action template."""

    key: str
    display_name: dict[str, str]
    description: str
    operation: str
    apply_strategy: str
    selection_policy: str
    output_contract: str
    aliases: tuple[str, ...] = ()
    supports_format_instruction: bool = False
    supports_target_lang: bool = False
    requires_instruction: bool = False
    sort_order: int = 0

    def to_contract(self) -> dict[str, Any]:
        """返回可序列化契约 / Return a serializable contract."""
        payload = asdict(self)
        payload["aliases"] = list(self.aliases)
        payload["feature"] = self.key
        payload["endpoint_feature"] = self.key
        payload["runtime_feature_code"] = RICH_TEXT_AI_FEATURE_CODE
        return payload

    def to_prompt_payload(self) -> dict[str, Any]:
        """返回 prompt 渲染所需动作信息 / Return action data used by prompt rendering."""
        return {
            "key": self.key,
            "label": self.display_name.get("zh-CN")
            or self.display_name.get("en")
            or self.key,
            "label_en": self.display_name.get("en") or self.key,
            "description": self.description,
            "operation": self.operation,
            "apply_strategy": self.apply_strategy,
            "selection_policy": self.selection_policy,
            "output_contract": self.output_contract,
        }


_RICH_TEXT_ACTIONS: tuple[RichTextAIActionTemplate, ...] = (
    RichTextAIActionTemplate(
        key="continue",
        display_name={"zh-CN": "续写", "en": "Continue"},
        description="Continue naturally from the cursor using explicit before/after document context.",
        operation="generate",
        apply_strategy="insert_at_cursor",
        selection_policy="cursor_context",
        output_contract="editor_plain_text_fragment",
        aliases=("continue_writing", "续写"),
        supports_format_instruction=True,
        sort_order=10,
    ),
    RichTextAIActionTemplate(
        key="insert",
        display_name={"zh-CN": "新增内容", "en": "Insert"},
        description="Create new editor-ready content at the cursor from an explicit user instruction.",
        operation="generate",
        apply_strategy="insert_at_cursor",
        selection_policy="cursor_context",
        output_contract="editor_plain_text_fragment",
        aliases=("new", "add", "create", "新增", "新建"),
        supports_format_instruction=True,
        requires_instruction=True,
        sort_order=20,
    ),
    RichTextAIActionTemplate(
        key="rewrite",
        display_name={"zh-CN": "改写", "en": "Rewrite"},
        description="Rewrite the selected text with different wording while preserving the same meaning.",
        operation="transform",
        apply_strategy="replace_selection",
        selection_policy="selection_required",
        output_contract="editor_plain_text_fragment",
        aliases=("rewrite_text", "改写", "重写"),
        supports_format_instruction=True,
        sort_order=30,
    ),
    RichTextAIActionTemplate(
        key="optimize",
        display_name={"zh-CN": "优化", "en": "Optimize"},
        description="Improve clarity, concision, and readability without changing the selected text's meaning.",
        operation="transform",
        apply_strategy="replace_selection",
        selection_policy="selection_required",
        output_contract="editor_plain_text_fragment",
        aliases=("improve", "polish", "优化"),
        supports_format_instruction=True,
        sort_order=40,
    ),
    RichTextAIActionTemplate(
        key="proofread",
        display_name={"zh-CN": "校对", "en": "Proofread"},
        description="Fix spelling, grammar, punctuation, and obvious wording errors while preserving style.",
        operation="transform",
        apply_strategy="replace_selection",
        selection_policy="selection_required",
        output_contract="editor_plain_text_fragment",
        aliases=("correct", "fix", "校对", "纠错"),
        sort_order=50,
    ),
    RichTextAIActionTemplate(
        key="translate",
        display_name={"zh-CN": "翻译", "en": "Translate"},
        description="Translate the selected text to the requested language while preserving structure.",
        operation="transform",
        apply_strategy="replace_selection",
        selection_policy="selection_required",
        output_contract="editor_plain_text_fragment",
        aliases=("translation", "翻译"),
        supports_format_instruction=True,
        supports_target_lang=True,
        sort_order=60,
    ),
    RichTextAIActionTemplate(
        key="summarize",
        display_name={"zh-CN": "摘要", "en": "Summarize"},
        description="Summarize selected text into concise editor-ready content.",
        operation="analyze",
        apply_strategy="replace_selection",
        selection_policy="selection_required",
        output_contract="editor_plain_text_fragment",
        aliases=("summary", "摘要", "总结"),
        supports_format_instruction=True,
        sort_order=70,
    ),
    RichTextAIActionTemplate(
        key="expand",
        display_name={"zh-CN": "扩写", "en": "Expand"},
        description="Expand selected text with concrete details while preserving topic, structure, and style.",
        operation="transform",
        apply_strategy="replace_selection",
        selection_policy="selection_required",
        output_contract="editor_plain_text_fragment",
        aliases=(
            "elaborate",
            "more",
            "more_content",
            "add_more",
            "扩写",
            "更多",
            "更多内容",
        ),
        supports_format_instruction=True,
        sort_order=80,
    ),
    RichTextAIActionTemplate(
        key="format",
        display_name={"zh-CN": "增加格式", "en": "Format"},
        description="Apply the requested formatting or structure to selected text without adding unsupported facts.",
        operation="format",
        apply_strategy="replace_selection",
        selection_policy="selection_required",
        output_contract="editor_rich_text_fragment",
        aliases=("format_text", "add_format", "formatting", "排版", "增加格式"),
        supports_format_instruction=True,
        requires_instruction=True,
        sort_order=90,
    ),
    RichTextAIActionTemplate(
        key="custom",
        display_name={"zh-CN": "自定义", "en": "Custom"},
        description="Run a user-provided explicit instruction against the selected text and document context.",
        operation="custom",
        apply_strategy="replace_or_insert_by_context",
        selection_policy="optional_selection",
        output_contract="editor_plain_text_fragment",
        aliases=("instruction", "custom_action", "自定义"),
        supports_format_instruction=True,
        requires_instruction=True,
        sort_order=100,
    ),
    RichTextAIActionTemplate(
        key="chat",
        display_name={"zh-CN": "写作问答", "en": "Chat"},
        description="Answer writing questions in the editor side panel using only explicit document context.",
        operation="chat",
        apply_strategy="chat_response",
        selection_policy="optional_selection",
        output_contract="assistant_message",
        aliases=("ask", "qa", "问答"),
        requires_instruction=True,
        sort_order=110,
    ),
)

_RICH_TEXT_ACTIONS_BY_KEY: dict[str, RichTextAIActionTemplate] = {
    action.key: action for action in _RICH_TEXT_ACTIONS
}
_RICH_TEXT_ACTION_ALIASES: dict[str, str] = {
    alias.strip().lower().replace("-", "_"): action.key
    for action in _RICH_TEXT_ACTIONS
    for alias in action.aliases
}

VALID_RICH_TEXT_ACTIONS = frozenset(_RICH_TEXT_ACTIONS_BY_KEY)
VALID_RICH_TEXT_FEATURES = frozenset(
    set(VALID_RICH_TEXT_ACTIONS) | set(_RICH_TEXT_ACTION_ALIASES)
)


class RichTextAIActionError(ValueError):
    """富文本 AI 动作契约错误 / Rich-text AI action contract error."""


def iter_rich_text_action_templates() -> tuple[RichTextAIActionTemplate, ...]:
    """列出规范动作模板 / List canonical action templates."""
    return _RICH_TEXT_ACTIONS


def normalize_rich_text_action_key(
    feature: str,
    *,
    default: str | None = "custom",
) -> str:
    """归一化旧 feature/action 名称 / Normalize legacy feature/action names."""
    key = str(feature or "").strip().lower().replace("-", "_")
    if key in _RICH_TEXT_ACTIONS_BY_KEY:
        return key
    if key in _RICH_TEXT_ACTION_ALIASES:
        return _RICH_TEXT_ACTION_ALIASES[key]
    if default is not None:
        return default
    raise RichTextAIActionError(f"Unsupported rich text AI action: {feature}")


def get_rich_text_action_template(feature: str) -> RichTextAIActionTemplate:
    """按 feature 获取动作模板 / Resolve an action template by feature."""
    return _RICH_TEXT_ACTIONS_BY_KEY[
        normalize_rich_text_action_key(feature, default="custom")
    ]


def build_rich_text_action_catalog() -> list[dict[str, Any]]:
    """构建前端/DB 可消费动作目录 / Build frontend/DB consumable action catalog."""
    return [action.to_contract() for action in _RICH_TEXT_ACTIONS]


def _bounded_text(value: Any, max_length: int, *, tail: bool = False) -> str:
    text = str(value or "")
    if len(text) <= max_length:
        return text
    return text[-max_length:] if tail else text[:max_length]


def build_rich_text_action_context(
    *,
    selected_text: str = "",
    before_text: str = "",
    after_text: str = "",
    context_title: str = "",
    instruction: str = "",
    target_lang: str = "English",
    format_instruction: str = "",
) -> dict[str, str]:
    """裁剪并规范化编辑器上下文 / Trim and normalize explicit editor context."""
    return {
        "selected_text": _bounded_text(selected_text, MAX_SELECTED_TEXT)
        or "(no selection)",
        "before_text": _bounded_text(before_text, MAX_BEFORE_TEXT, tail=True)
        or "(beginning of document)",
        "after_text": _bounded_text(after_text, MAX_AFTER_TEXT) or "(end of document)",
        "context_title": _bounded_text(context_title, 200) or "Untitled",
        "instruction": _bounded_text(instruction, MAX_INSTRUCTION),
        "target_lang": _bounded_text(target_lang, 50) or "English",
        "format_instruction": _bounded_text(format_instruction, MAX_INSTRUCTION),
    }


def build_rich_text_ai_messages(
    feature: str,
    *,
    selected_text: str = "",
    before_text: str = "",
    after_text: str = "",
    context_title: str = "",
    instruction: str = "",
    target_lang: str = "English",
    format_instruction: str = "",
    chat_history: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    """构建富文本 AI 消息 / Build rich-text AI messages."""
    action = get_rich_text_action_template(feature)
    context = build_rich_text_action_context(
        selected_text=selected_text,
        before_text=before_text,
        after_text=after_text,
        context_title=context_title,
        instruction=instruction,
        target_lang=target_lang,
        format_instruction=format_instruction,
    )
    action_payload = action.to_prompt_payload()

    system_content = render_prompt_contract(
        PromptContractName.RICH_TEXT_AI_ACTION_SYSTEM.value,
        action=action_payload,
        **context,
    )
    user_content = render_prompt_contract(
        PromptContractName.RICH_TEXT_AI_ACTION_USER.value,
        action=action_payload,
        **context,
    )

    messages: list[dict[str, str]] = [{"role": "system", "content": system_content}]
    if action.key == "chat" and chat_history:
        for msg in chat_history[-10:]:
            messages.append(
                {
                    "role": str(msg.get("role") or "user"),
                    "content": str(msg.get("content") or ""),
                }
            )
    messages.append({"role": "user", "content": user_content})
    return messages


def build_rich_text_ai_request_message(
    messages: list[dict[str, str]],
    *,
    format_instruction: str = "",
) -> str:
    """将消息折叠为临时聊天请求 / Fold messages into an ephemeral chat request."""
    system_content = "\n\n".join(
        str(message.get("content") or "")
        for message in messages
        if message.get("role") == "system"
    )
    user_content = "\n\n".join(
        str(message.get("content") or "")
        for message in messages
        if message.get("role") == "user"
    )
    return render_prompt_contract(
        PromptContractName.RICH_TEXT_AI_ACTION_ENVELOPE.value,
        system_content=system_content,
        user_content=user_content,
        format_instruction=_bounded_text(format_instruction, MAX_INSTRUCTION),
    )


def build_rich_text_action_input_schema() -> dict[str, Any]:
    """构建前后端请求契约 schema / Build frontend-backend request contract schema."""
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "action": {
                "type": "string",
                "enum": sorted(VALID_RICH_TEXT_FEATURES),
                "description": "Rich-text AI action key or legacy alias.",
            },
            "selected_text": {"type": "string", "maxLength": 10000},
            "before_text": {"type": "string", "maxLength": 5000},
            "after_text": {"type": "string", "maxLength": 2000},
            "context_title": {"type": "string", "maxLength": 200},
            "instruction": {"type": "string", "maxLength": 2000},
            "target_lang": {"type": "string", "maxLength": 50, "default": "English"},
            "format_instruction": {"type": "string", "maxLength": 2000},
            "history": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "role": {"type": "string", "enum": ["user", "assistant"]},
                        "content": {"type": "string"},
                    },
                    "required": ["role", "content"],
                },
            },
        },
        "required": ["action"],
    }


def build_rich_text_action_output_schema() -> dict[str, Any]:
    """构建 SSE/动作结果契约 schema / Build SSE/action result contract schema."""
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "event": {"type": "string", "enum": ["message", "done", "error"]},
            "delta": {"type": "string"},
            "action": {"type": "string", "enum": sorted(VALID_RICH_TEXT_ACTIONS)},
            "apply_strategy": {
                "type": "string",
                "enum": sorted(
                    {action.apply_strategy for action in _RICH_TEXT_ACTIONS}
                ),
            },
            "output_contract": {
                "type": "string",
                "enum": sorted(
                    {action.output_contract for action in _RICH_TEXT_ACTIONS}
                ),
            },
        },
        "required": ["event"],
    }


def build_default_rich_text_skill_package_definition() -> dict[str, Any]:
    """构建默认技能包定义 / Build the default skill-package definition."""
    actions = build_rich_text_action_catalog()
    input_schema = build_rich_text_action_input_schema()
    output_schema = build_rich_text_action_output_schema()
    return {
        "package": {
            "name": RICH_TEXT_AI_PACKAGE_NAME,
            "description": "Internal historical metadata for NovusDoc rich-text AI editor actions; runtime uses system.ai_writing.",
            "avatar": "lucide:file-pen-line",
            "is_recommended": False,
            "is_system": True,
            "is_active": False,
            "sort_order": 20,
            "source_plugin": RICH_TEXT_AI_PACKAGE_SOURCE_PLUGIN,
            "valves_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "feature_code": {
                        "type": "string",
                        "const": RICH_TEXT_AI_FEATURE_CODE,
                        "default": RICH_TEXT_AI_FEATURE_CODE,
                    },
                    "contract_version": {
                        "type": "string",
                        "const": RICH_TEXT_AI_CONTRACT_VERSION,
                        "default": RICH_TEXT_AI_CONTRACT_VERSION,
                    },
                    "runtime_feature_code": {
                        "type": "string",
                        "const": RICH_TEXT_AI_FEATURE_CODE,
                        "default": RICH_TEXT_AI_FEATURE_CODE,
                    },
                },
            },
            "valves_config": {
                "feature_code": RICH_TEXT_AI_FEATURE_CODE,
                "contract_version": RICH_TEXT_AI_CONTRACT_VERSION,
                "runtime_feature_code": RICH_TEXT_AI_FEATURE_CODE,
                "internal": True,
                "catalog_visible": False,
            },
        },
        "skills": [
            {
                "name": "Rich Text AI Actions",
                "key": RICH_TEXT_AI_SKILL_KEY,
                "description": "Internal historical templates for editor AI actions; runtime sends rendered messages after resolving system.ai_writing.",
                "type": SkillTypeEnum.BUILTIN.value,
                "source_type": SkillSourceTypeEnum.PLATFORM_BUILTIN.value,
                "source_ref": RICH_TEXT_AI_SKILL_KEY,
                "version": "1.0.0",
                "status": SkillStatusEnum.DISABLED.value,
                "is_readonly": True,
                "config": {
                    "internal": True,
                    "catalog_only": True,
                    "runtime_feature_code": RICH_TEXT_AI_FEATURE_CODE,
                    "runtime_contract": "agent_chat_message_template",
                    "contract_version": RICH_TEXT_AI_CONTRACT_VERSION,
                    "action_templates": actions,
                    "legacy_features": sorted(VALID_RICH_TEXT_FEATURES),
                },
                "input_schema": input_schema,
                "output_schema": output_schema,
                "is_system": True,
                "is_active": False,
                "sort_order": 10,
                "timeout": 30,
            }
        ],
    }


__all__ = [
    "MAX_AFTER_TEXT",
    "MAX_BEFORE_TEXT",
    "MAX_INSTRUCTION",
    "MAX_SELECTED_TEXT",
    "RICH_TEXT_AI_CONTRACT_VERSION",
    "RICH_TEXT_AI_FEATURE_CODE",
    "RICH_TEXT_AI_PACKAGE_NAME",
    "RICH_TEXT_AI_PACKAGE_SOURCE_PLUGIN",
    "RICH_TEXT_AI_SKILL_KEY",
    "RichTextAIActionError",
    "RichTextAIActionTemplate",
    "VALID_RICH_TEXT_ACTIONS",
    "VALID_RICH_TEXT_FEATURES",
    "build_default_rich_text_skill_package_definition",
    "build_rich_text_action_catalog",
    "build_rich_text_action_context",
    "build_rich_text_action_input_schema",
    "build_rich_text_action_output_schema",
    "build_rich_text_ai_messages",
    "build_rich_text_ai_request_message",
    "get_rich_text_action_template",
    "iter_rich_text_action_templates",
    "normalize_rich_text_action_key",
]
