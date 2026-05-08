"""Test type: behavioral
中文: 覆盖富文本 AI action 校验与全局 AgentChat 消息模板，不覆盖独立 SSE 写作流。
EN: Covers rich-text AI action validation and global AgentChat message template
behavior; no standalone writing SSE runtime is exercised.
Real dependencies: rich-text prompt-contract rendering and AgentChatRequest schema.
Mocked dependencies: none.
"""

from __future__ import annotations

import pytest


class TestBuildAiMessages:
    def test_build_ai_messages_truncates_inputs_and_keeps_last_10_history(self):
        from app.services.ai.writing_service import (
            MAX_AFTER_TEXT,
            MAX_BEFORE_TEXT,
            MAX_INSTRUCTION,
            MAX_SELECTED_TEXT,
            build_ai_messages,
        )

        history = [
            {"role": "assistant" if idx % 2 else "user", "content": f"message-{idx}"}
            for idx in range(12)
        ]

        messages = build_ai_messages(
            "chat",
            selected_text="s" * (MAX_SELECTED_TEXT + 20),
            before_text="b" * (MAX_BEFORE_TEXT + 20),
            after_text="a" * (MAX_AFTER_TEXT + 20),
            context_title="Demo Doc",
            instruction="i" * (MAX_INSTRUCTION + 20),
            chat_history=history,
        )

        assert messages[0]["role"] == "system"
        assert len(messages) == 12
        assert [item["content"] for item in messages[1:-1]] == [
            f"message-{idx}" for idx in range(2, 12)
        ]
        assert messages[-1]["role"] == "user"
        assert "选中的文本:" in messages[-1]["content"]
        assert "s" * MAX_SELECTED_TEXT in messages[-1]["content"]
        assert "s" * (MAX_SELECTED_TEXT + 1) not in messages[-1]["content"]
        assert "用户问题:" in messages[-1]["content"]
        assert "i" * MAX_INSTRUCTION in messages[-1]["content"]

    def test_legacy_aliases_are_not_skill_activation_inputs(self):
        from app.exceptions import ValidationException
        from app.services.ai.writing_service import (
            is_valid_writing_action,
            normalize_writing_action,
        )

        assert is_valid_writing_action("more") is False
        with pytest.raises(ValidationException) as exc_info:
            normalize_writing_action("more")
        assert exc_info.value.status_code == 422
        assert "more" in exc_info.value.message

    def test_build_ai_messages_rejects_unknown_feature(self):
        from app.exceptions import ValidationException
        from app.services.ai.writing_service import build_ai_messages

        with pytest.raises(ValidationException) as exc_info:
            build_ai_messages("unknown-feature")

        assert exc_info.value.status_code == 422
        assert "unknown-feature" in exc_info.value.message

    def test_rewrite_requires_selected_text(self):
        from app.exceptions import ValidationException
        from app.services.ai.writing_service import build_ai_messages

        with pytest.raises(ValidationException) as exc_info:
            build_ai_messages("rewrite", selected_text="   ")

        assert exc_info.value.data is not None
        errors = exc_info.value.data["errors"]
        assert errors == [
            {
                "loc": ["selected_text"],
                "msg": exc_info.value.message,
                "type": "value_error",
            }
        ]
        assert "rewrite" in exc_info.value.message

    def test_summarize_keeps_source_language_without_english_target(self):
        from app.services.ai.writing_service import build_ai_messages

        messages = build_ai_messages(
            "summarize",
            selected_text="胡萝卜是兔子的刻板印象，但兔子也需要草和干草。",
        )
        rendered = "\n\n".join(message["content"] for message in messages)

        assert "匹配原文语言" in rendered
        assert "目标语言: English" not in rendered
        assert "目标语言:" not in rendered

    def test_non_translate_actions_ignore_client_target_language(self):
        from app.services.ai.writing_service import build_ai_messages

        messages = build_ai_messages(
            "rewrite",
            selected_text="原始内容",
            target_lang="English",
        )
        rendered = "\n\n".join(message["content"] for message in messages)

        assert "目标语言: English" not in rendered
        assert "原始内容" in rendered

    def test_translate_keeps_explicit_target_language(self):
        from app.services.ai.writing_service import build_ai_messages

        messages = build_ai_messages(
            "translate",
            selected_text="Original content",
            target_lang="Simplified Chinese",
        )
        rendered = "\n\n".join(message["content"] for message in messages)

        assert "动作规则：翻译为目标语言" in rendered
        assert "目标语言: Simplified Chinese" in rendered


class TestRichTextAgentChatMessage:
    def test_builds_message_accepted_by_global_agent_chat_request(self) -> None:
        from app.schemas.ai.agent_chat import AgentChatRequest
        from app.services.ai.writing_service import (
            FEATURE_CODE,
            build_rich_text_agent_chat_message,
        )

        message = build_rich_text_agent_chat_message(
            "rewrite",
            {
                "selected_text": "原始内容",
                "before_text": "标题",
                "after_text": "结尾",
                "document_title": "Demo Doc",
                "format_instruction": "保留项目符号",
            },
        )
        request = AgentChatRequest.model_validate(
            {
                "message": message,
            }
        )

        assert FEATURE_CODE == "system.ai_writing"
        assert request.message == message
        assert "[Task Instructions]" in request.message
        assert "[Format Requirement]" in request.message
        assert "原始内容" in request.message
        assert "保留项目符号" in request.message
        assert "system.ai_writing" not in request.message
        assert "plugin.novusdoc.rich_text_ai" not in request.message

    def test_chat_message_includes_explicit_editor_context(self) -> None:
        from app.services.ai.writing_service import build_rich_text_agent_chat_message

        message = build_rich_text_agent_chat_message(
            "chat",
            {
                "selected_text": "这段论证需要更紧凑。",
                "before_text": "前一段介绍了背景。",
                "after_text": "后一段准备列出方案。",
                "document_title": "产品方案",
                "instruction": "帮我判断这里应该扩写还是压缩。",
                "history": [
                    {"role": "user", "content": "先看这个段落。"},
                    {"role": "assistant", "content": "可以，我会基于选区判断。"},
                ],
            },
        )

        assert "文档标题: 产品方案" in message
        assert "选中的文本:" in message
        assert "这段论证需要更紧凑。" in message
        assert "光标前的内容:" in message
        assert "前一段介绍了背景。" in message
        assert "光标后的内容:" in message
        assert "后一段准备列出方案。" in message
        assert "用户问题:" in message
        assert "帮我判断这里应该扩写还是压缩。" in message
        assert "不要声称已经修改正文" in message
        assert "DOM snapshot" not in message
        assert "active_surface" not in message

    def test_agent_chat_message_builder_rejects_page_context_fields_by_schema(
        self,
    ) -> None:
        from pydantic import ValidationError

        from app.api.admin.ai_writing import AIWritingRequest

        with pytest.raises(ValidationError) as exc_info:
            AIWritingRequest.model_validate(
                {
                    "selected_text": "hello",
                    "page_context": {"url": "/admin/plugins/novusdoc/editor/9"},
                }
            )

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["type"] == "extra_forbidden"
        assert errors[0]["loc"] == ("page_context",)

    def test_standalone_stream_runtime_is_not_exported(self) -> None:
        import app.services.ai.writing_service as writing_service

        assert "stream_writing_feature" not in writing_service.__all__
        assert (
            "build_default_rich_text_skill_package_definition"
            not in writing_service.__all__
        )
        assert not hasattr(writing_service, "stream_writing_feature")
        assert not hasattr(writing_service, "_resolve_writing_agent")
        assert not hasattr(
            writing_service,
            "build_default_rich_text_skill_package_definition",
        )
