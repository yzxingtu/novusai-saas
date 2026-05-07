from __future__ import annotations

import json
import time
from dataclasses import asdict
from types import SimpleNamespace

import pytest

from app.ai.engine.stream_handler import StreamExecutionHandler
from app.ai.engine.turn_executor import TurnExecutionResult
from app.ai.types import ChatMessage, ChatResponse


def test_last_visible_assistant_content_ignores_previous_round_messages() -> None:
    messages = [
        ChatMessage(role="assistant", content="old output", tool_calls=None),
        ChatMessage(
            role="assistant",
            content="",
            tool_calls=[
                {
                    "id": "call-old",
                    "name": "crm_lookup",
                }
            ],
        ),
    ]
    start_index = 1
    assert (
        StreamExecutionHandler._last_visible_assistant_content(messages[start_index:])
        == ""
    )


class _StubEngine:
    @staticmethod
    def _messages_to_dicts(messages: list[ChatMessage]) -> list[dict]:
        return [asdict(message) for message in messages]


@pytest.mark.asyncio
async def test_partial_finalize_replays_and_appends_new_output_after_clear() -> None:
    prep = SimpleNamespace(
        messages=[ChatMessage(role="user", content="继续处理")],
        rag_sources=None,
        optimize_event=None,
        stream_runtime=None,
        tools=[],
        all_tools=[],
        intent_plan=[],
        execution_budget=None,
        execution_path="fast",
        context_compacted=False,
        memory_flush_triggered=False,
        memory_recalled=False,
        prune_stats=None,
        tool_planner=None,
        rag_source_kinds=[],
        context_engine=None,
        tool_consent_modes={},
        route_result=None,
    )
    handler = StreamExecutionHandler(
        engine=_StubEngine(),
        agent=SimpleNamespace(id=1),
        request=SimpleNamespace(
            tenant_id=1,
            user_id=1,
            conversation_id=42,
            input_variables={},
        ),
        prep=prep,
        start_time=time.perf_counter(),
        on_complete=None,
    )

    async def _fake_turn_execution() -> TurnExecutionResult:
        handler.prep.messages.append(
            ChatMessage(role="assistant", content="上一轮先查一下")
        )
        return TurnExecutionResult(
            output="这是本轮最终文本",
            total_tokens=18,
            completion_tokens_used=18,
            tool_results=[],
            response=ChatResponse(
                message=ChatMessage(role="assistant", content=""),
                total_tokens=18,
                output_tokens=18,
            ),
            partial=True,
            paused_for_consent=False,
            completion_reason="retry_budget_exhausted",
            final_output_source="partial_output",
        )

    handler._run_with_turn_executor = _fake_turn_execution  # type: ignore[method-assign]

    events: list[dict] = []
    async for raw in handler.generate():
        payload = raw.strip()
        if not payload.startswith("data: {"):
            continue
        events.append(json.loads(payload[6:]))

    message_text = "".join(
        str(event.get("delta") or "")
        for event in events
        if event.get("event") == "message"
    )
    assistant_messages = [
        message
        for message in handler.prep.messages
        if message.role == "assistant" and not message.tool_calls
    ]

    assert message_text == "这是本轮最终文本"
    assert assistant_messages[-1].content == "这是本轮最终文本"
