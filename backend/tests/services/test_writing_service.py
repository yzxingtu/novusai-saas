"""Writing service unit tests / AI 写作服务单元测试。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


async def _iter_chunks(chunks):
    for chunk in chunks:
        yield chunk


def _build_sse_response(*chunks):
    return SimpleNamespace(body_iterator=_iter_chunks(chunks))


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
        assert messages[-1]["content"] == "i" * MAX_INSTRUCTION

    def test_build_ai_messages_uses_custom_defaults_for_unknown_feature(self):
        from app.services.ai.writing_service import build_ai_messages

        messages = build_ai_messages("unknown-feature")

        assert messages[0]["role"] == "system"
        assert "自定义指令" in messages[0]["content"]
        assert "Untitled" in messages[-1]["content"]
        assert "(no selection)" in messages[-1]["content"]


class TestStreamWritingFeature:

    @pytest.mark.asyncio
    async def test_stream_writing_feature_yields_message_deltas(self, mock_db):
        from app.services.ai.writing_service import stream_writing_feature

        chat_service = MagicMock()
        chat_service.stream_chat_ephemeral = AsyncMock(
            return_value=_build_sse_response(
                b'data: {"event":"message","delta":"Hello "}\n\n',
                b'data: {"event":"message","delta":"world"}\n\n',
                b"data: [DONE]\n\n",
            )
        )

        with patch(
            "app.services.ai.writing_service._resolve_writing_agent",
            new=AsyncMock(return_value=42),
        ), patch(
            "app.services.ai.agent_chat_service.AgentChatService",
            return_value=chat_service,
        ):
            chunks = [
                chunk
                async for chunk in stream_writing_feature(
                    mock_db,
                    tenant_id=7,
                    feature="translate",
                    body={
                        "selected_text": "hello",
                        "target_lang": "Chinese",
                        "format_instruction": "return plain text",
                    },
                )
            ]

        assert "".join(chunks) == "Hello world"
        chat_service.stream_chat_ephemeral.assert_awaited_once()
        request_message = chat_service.stream_chat_ephemeral.await_args.kwargs["message"]
        assert "[Task Instructions]" in request_message
        assert "[Format Requirement]" in request_message
        assert "[User Request]" in request_message

    @pytest.mark.asyncio
    async def test_stream_writing_feature_raises_on_error_event(self, mock_db):
        from app.exceptions import BusinessException
        from app.services.ai.writing_service import stream_writing_feature

        chat_service = MagicMock()
        chat_service.stream_chat_ephemeral = AsyncMock(
            return_value=_build_sse_response(
                b'data: {"error":true,"message":"upstream failed"}\n\n',
            )
        )

        with patch(
            "app.services.ai.writing_service._resolve_writing_agent",
            new=AsyncMock(return_value=9),
        ), patch(
            "app.services.ai.agent_chat_service.AgentChatService",
            return_value=chat_service,
        ), pytest.raises(BusinessException, match="upstream failed"):
            async for _chunk in stream_writing_feature(
                mock_db,
                tenant_id=None,
                feature="optimize",
                body={"selected_text": "draft"},
            ):
                pass
