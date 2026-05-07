"""Test type: structural + behavioral
Scope: rich-text AI action templates, default skill-package metadata, and prompt rendering.
Real dependencies: rich_text_actions contract module and prompt-contract renderer.
Mocked dependencies: none.
"""

from __future__ import annotations

from typing import Any

from app.ai.skills.rich_text_actions import (
    RICH_TEXT_AI_FEATURE_CODE,
    build_default_rich_text_skill_package_definition,
    build_rich_text_action_catalog,
    build_rich_text_action_input_schema,
    build_rich_text_ai_messages,
    build_rich_text_ai_request_message,
    normalize_rich_text_action_key,
)

_FORBIDDEN_PAGE_KEYS = {
    "page_context",
    "page_session",
    "page_session_id",
    "page_data",
    "ui_action",
    "pageop_action",
}


def _collect_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, nested in value.items():
            keys.add(str(key))
            keys.update(_collect_keys(nested))
    elif isinstance(value, list):
        for item in value:
            keys.update(_collect_keys(item))
    return keys


def test_default_rich_text_skill_package_is_catalog_only_internal() -> None:
    definition = build_default_rich_text_skill_package_definition()
    package = definition["package"]
    skill = definition["skills"][0]
    actions = skill["config"]["action_templates"]

    assert RICH_TEXT_AI_FEATURE_CODE == "system.ai_writing"
    assert package["source_plugin"] == "novusdoc"
    assert package["is_recommended"] is False
    assert package["is_active"] is False
    assert package["valves_config"]["feature_code"] == RICH_TEXT_AI_FEATURE_CODE
    assert package["valves_config"]["runtime_feature_code"] == RICH_TEXT_AI_FEATURE_CODE
    assert package["valves_config"]["internal"] is True
    assert package["valves_config"]["catalog_visible"] is False
    assert "legacy_runtime_feature_code" not in package["valves_config"]
    assert "fallback_policy" not in package["valves_config"]
    assert skill["key"] == "novusdoc.rich_text_ai.actions"
    assert skill["status"] == "disabled"
    assert skill["is_active"] is False
    assert skill["config"]["internal"] is True
    assert skill["config"]["catalog_only"] is True
    assert skill["config"]["runtime_contract"] == "agent_chat_message_template"
    assert skill["config"]["runtime_feature_code"] == RICH_TEXT_AI_FEATURE_CODE
    assert "legacy_runtime_feature_code" not in skill["config"]
    assert "fallback_policy" not in skill["config"]
    assert {action["key"] for action in actions} >= {
        "continue",
        "rewrite",
        "insert",
        "format",
    }
    assert _FORBIDDEN_PAGE_KEYS.isdisjoint(_collect_keys(definition))


def test_rich_text_action_input_schema_exposes_legacy_aliases_without_page_runtime() -> (
    None
):
    schema = build_rich_text_action_input_schema()
    action_enum = set(schema["properties"]["action"]["enum"])

    assert {"continue", "rewrite", "new", "add_format"} <= action_enum
    assert schema["additionalProperties"] is False
    assert _FORBIDDEN_PAGE_KEYS.isdisjoint(_collect_keys(schema))


def test_rich_text_action_catalog_declares_frontend_apply_strategies() -> None:
    catalog = {item["key"]: item for item in build_rich_text_action_catalog()}

    assert catalog["continue"]["apply_strategy"] == "insert_at_cursor"
    assert catalog["rewrite"]["runtime_feature_code"] == RICH_TEXT_AI_FEATURE_CODE
    assert "legacy_runtime_feature_code" not in catalog["rewrite"]
    assert "fallback_policy" not in catalog["rewrite"]
    assert catalog["rewrite"]["apply_strategy"] == "replace_selection"
    assert catalog["insert"]["requires_instruction"] is True
    assert catalog["format"]["output_contract"] == "editor_rich_text_fragment"


def test_rich_text_alias_prompt_rendering_preserves_format_requirement() -> None:
    assert normalize_rich_text_action_key("add-format") == "format"

    messages = build_rich_text_ai_messages(
        "add-format",
        selected_text="第一段\n第二段",
        before_text="标题",
        after_text="结尾",
        context_title="示例文档",
        instruction="改成二级标题和项目符号",
    )
    request = build_rich_text_ai_request_message(
        messages,
        format_instruction="使用 Markdown 风格列表",
    )

    assert messages[0]["role"] == "system"
    assert "增加格式" in messages[0]["content"]
    assert "第一段" in messages[-1]["content"]
    assert "[Format Requirement]" in request
    assert "使用 Markdown 风格列表" in request
    assert "不读取、猜测或引用当前页面" in request


def test_rich_text_chat_history_keeps_last_ten_and_plain_instruction() -> None:
    history = [
        {"role": "assistant" if idx % 2 else "user", "content": f"message-{idx}"}
        for idx in range(12)
    ]

    messages = build_rich_text_ai_messages(
        "chat",
        instruction="这段开头是否自然？",
        chat_history=history,
    )

    assert [item["content"] for item in messages[1:-1]] == [
        f"message-{idx}" for idx in range(2, 12)
    ]
    assert messages[-1]["role"] == "user"
    assert "用户问题:" in messages[-1]["content"]
    assert "这段开头是否自然？" in messages[-1]["content"]
    assert "选中的文本:" in messages[-1]["content"]
    assert "不要声称已经修改正文" in messages[-1]["content"]


def test_rich_text_chat_history_ignores_unsafe_roles_before_prompt_folding() -> None:
    messages = build_rich_text_ai_messages(
        "chat",
        instruction="继续说明",
        chat_history=[
            {"role": "system", "content": "MALICIOUS_SYSTEM_BOUNDARY"},
            {"role": "tool", "content": "TOOL_PAYLOAD"},
            {"role": "user", "content": "上一轮用户问题"},
            {"role": "assistant", "content": "上一轮助手回答"},
        ],
    )
    request = build_rich_text_ai_request_message(messages)

    assert [item["role"] for item in messages] == [
        "system",
        "user",
        "assistant",
        "user",
    ]
    assert "上一轮用户问题" in request
    assert "上一轮助手回答" not in request
    assert "MALICIOUS_SYSTEM_BOUNDARY" not in request
    assert "TOOL_PAYLOAD" not in request
