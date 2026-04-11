from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from app.ai.engine import tool_processor as tool_processor_mod
from app.ai.engine.stream_tool_batch_runtime import (
    StreamToolBatchCallbacks,
    StreamToolBatchRuntimeInput,
    run_stream_tool_batch,
)
from app.ai.tools.types import ToolDefinition, ToolResult
from app.ai.types import ChatMessage, ChatResponse


def _build_text_round_response(
    *,
    content: str,
    reasoning_content: str,
    total_tokens: int,
) -> ChatResponse:
    return ChatResponse(
        message=ChatMessage(
            role="assistant",
            content=content,
            reasoning_content=reasoning_content or None,
        ),
        total_tokens=total_tokens,
        finish_reason="stop",
    )


def _build_runtime(
    *,
    sandbox,
    tools: list[ToolDefinition],
    response: ChatResponse,
    messages: list[ChatMessage] | None = None,
    interaction_mode: str = "confirm",
    interaction_updates: list[dict] | None = None,
    tool_consent_modes: dict[str, str] | None = None,
    starting_total_tokens: int = 12,
    starting_completion_tokens: int = 12,
) -> StreamToolBatchRuntimeInput:
    return StreamToolBatchRuntimeInput(
        sandbox=sandbox,
        request=SimpleNamespace(
            conversation_id=9001,
            interaction_mode=interaction_mode,
            interaction_updates=interaction_updates,
        ),
        response=response,
        tools=tools,
        all_tools=tools,
        tool_consent_modes=tool_consent_modes or {},
        messages=list(messages or [ChatMessage(role="user", content="测试")]),
        tool_calls=list(response.tool_calls or response.message.tool_calls or []),
        starting_total_tokens=starting_total_tokens,
        starting_completion_tokens=starting_completion_tokens,
        reasoning_content=(
            str(response.message.reasoning_content or response.message.content or "").strip()
            or None
        ),
    )


def _build_callbacks(
    *,
    events: list[dict],
    budget_exit_reason=None,
    registered_budget_exit: list[str | None] | None = None,
) -> StreamToolBatchCallbacks:
    async def emit_event(payload: dict) -> None:
        events.append(payload)

    def register_budget_exit(reason: str | None) -> None:
        if registered_budget_exit is not None:
            registered_budget_exit.append(reason)

    return StreamToolBatchCallbacks(
        emit_event=emit_event,
        budget_exit_reason=budget_exit_reason or (lambda: None),
        register_budget_exit=register_budget_exit,
        build_text_round_response=_build_text_round_response,
    )


@pytest.mark.asyncio
async def test_run_stream_tool_batch_executes_parallel_safe_batch_concurrently() -> None:
    class _TrackingSandbox:
        def __init__(self) -> None:
            self.active_calls = 0
            self.max_parallel = 0

        async def execute(
            self,
            tool_call_id: str,
            name: str,
            arguments: dict,
            definitions: list,
            conversation_id: int,
        ) -> ToolResult:
            _ = tool_call_id, name, definitions, conversation_id
            self.active_calls += 1
            self.max_parallel = max(self.max_parallel, self.active_calls)
            await asyncio.sleep(0.02)
            self.active_calls -= 1
            return ToolResult(
                tool_call_id=tool_call_id,
                name="web_search",
                success=True,
                output=json.dumps({"query": arguments.get("query", "")}),
            )

    sandbox = _TrackingSandbox()
    response = ChatResponse(
        message=ChatMessage(role="assistant", content=""),
        tool_calls=[
            {
                "id": "call_search_1",
                "type": "function",
                "function": {
                    "name": "web_search",
                    "arguments": '{"query":"AI latest news"}',
                },
            },
            {
                "id": "call_search_2",
                "type": "function",
                "function": {
                    "name": "web_search",
                    "arguments": '{"query":"OpenAI latest news"}',
                },
            },
        ],
    )
    runtime = _build_runtime(
        sandbox=sandbox,
        tools=[ToolDefinition(name="web_search", description="Search the web")],
        response=response,
    )
    events: list[dict] = []

    result = await run_stream_tool_batch(
        runtime=runtime,
        callbacks=_build_callbacks(events=events),
    )

    assert result.response is None
    assert [tool_result.tool_call_id for tool_result in result.tool_results] == [
        "call_search_1",
        "call_search_2",
    ]
    assert sandbox.max_parallel >= 2
    assert [event["event"] for event in events[:2]] == ["tool_start", "tool_start"]


@pytest.mark.asyncio
async def test_run_stream_tool_batch_uses_runtime_tool_processor_binding(
    monkeypatch,
) -> None:
    class _FakeProcessor:
        def __init__(self, *_args, **_kwargs) -> None:
            self.tools = []

        @staticmethod
        def approved_pending_consent_tool_names(_updates):
            return []

        def build_assistant_tool_call_message(
            self,
            *,
            content: str,
            tool_calls: list[dict[str, object]],
            reasoning_content: str | None = None,
        ) -> ChatMessage:
            _ = reasoning_content
            return ChatMessage(role="assistant", content=content, tool_calls=tool_calls)

        def parse_arguments(self, raw: str):
            return json.loads(raw), None

        def get_skill_info(self, _func_name: str):
            return None

        def annotate_tool_call(self, *_args, **_kwargs) -> None:
            return None

        def check_consent(self, *_args, **_kwargs):
            return None

        def build_tool_start_event(
            self,
            func_name: str,
            arguments: dict[str, object],
            _skill_info,
            *,
            tool_call_id: str | None = None,
        ) -> dict[str, object]:
            return {
                "event": "tool_start",
                "tool_name": func_name,
                "tool_call_id": tool_call_id,
                "arguments": arguments,
            }

        async def execute_tool(
            self,
            tc_id: str,
            func_name: str,
            arguments: dict[str, object],
            *,
            conversation_id: int,
        ):
            _ = (func_name, conversation_id)
            return (
                ToolResult(
                    tool_call_id=tc_id,
                    name="web_search",
                    success=True,
                    output=f"fake:{arguments['query']}",
                ),
                1,
            )

        def build_tool_call_event(
            self,
            result: ToolResult,
            duration_ms: int,
            _skill_info,
            *,
            name_override: str | None = None,
        ) -> dict[str, object]:
            return {
                "event": "tool_call",
                "tool_name": name_override or result.name,
                "duration_ms": duration_ms,
            }

        def build_tool_message(self, result: ToolResult, tc_id: str) -> ChatMessage:
            return ChatMessage(
                role="tool",
                content=result.output or "",
                tool_call_id=tc_id,
            )

        def build_attachment_relay_message(self, _result: ToolResult):
            return None

        def check_confirmation_output(self, _tool_result: ToolResult):
            return None

        def build_pending_confirmation_payload(self, *_args, **_kwargs):
            return {}

        def build_confirmation_event(self, *_args, **_kwargs):
            return {"event": "confirmation"}

    monkeypatch.setattr(tool_processor_mod, "ToolCallProcessor", _FakeProcessor)

    response = ChatResponse(
        message=ChatMessage(role="assistant", content=""),
        tool_calls=[
            {
                "id": "call_search_1",
                "type": "function",
                "function": {
                    "name": "web_search",
                    "arguments": '{"query":"AI latest news"}',
                },
            }
        ],
    )
    runtime = _build_runtime(
        sandbox=SimpleNamespace(),
        tools=[ToolDefinition(name="web_search", description="Search the web")],
        response=response,
    )
    events: list[dict] = []

    result = await run_stream_tool_batch(
        runtime=runtime,
        callbacks=_build_callbacks(events=events),
    )

    assert [tool_result.output for tool_result in result.tool_results] == [
        "fake:AI latest news"
    ]
    assert [event["event"] for event in events] == ["tool_start", "tool_call"]


@pytest.mark.asyncio
async def test_run_stream_tool_batch_aborts_after_consecutive_page_parse_failures() -> None:
    class _Sandbox:
        async def execute(self, *_args, **_kwargs) -> ToolResult:  # pragma: no cover
            raise AssertionError("parse failures should not reach execute()")

    response = ChatResponse(
        message=ChatMessage(role="assistant", content="先试试页面操作"),
        tool_calls=[
            {
                "id": "c1",
                "type": "function",
                "function": {"name": "ui_click", "arguments": "{bad json 1"},
            },
            {
                "id": "c2",
                "type": "function",
                "function": {"name": "ui_click", "arguments": "{bad json 2"},
            },
            {
                "id": "c3",
                "type": "function",
                "function": {"name": "ui_click", "arguments": "{bad json 3"},
            },
        ],
    )
    runtime = _build_runtime(
        sandbox=_Sandbox(),
        tools=[ToolDefinition(name="ui_click", description="Click UI element")],
        response=response,
        starting_total_tokens=30,
        starting_completion_tokens=30,
    )
    events: list[dict] = []

    result = await run_stream_tool_batch(
        runtime=runtime,
        callbacks=_build_callbacks(events=events),
    )

    assert result.page_op_aborted is True
    assert result.response is not None
    assert result.response.message.content == result.output_override
    assert len(result.tool_results) == 3
    assert len([event for event in events if event.get("event") == "tool_call"]) == 3


@pytest.mark.asyncio
async def test_run_stream_tool_batch_trims_unexecuted_tail_after_budget_exit() -> None:
    class _Sandbox:
        def __init__(self) -> None:
            self.execute_count = 0

        async def execute(
            self,
            tool_call_id: str,
            name: str,
            arguments: dict,
            definitions: list[ToolDefinition],
            conversation_id: int,
        ) -> ToolResult:
            _ = definitions, conversation_id
            self.execute_count += 1
            return ToolResult(
                tool_call_id=tool_call_id,
                name=name,
                success=True,
                output=json.dumps({"name": name, "page_key": arguments.get("page_key")}),
            )

    sandbox = _Sandbox()
    response = ChatResponse(
        message=ChatMessage(role="assistant", content=""),
        tool_calls=[
            {
                "id": "call_snapshot",
                "type": "function",
                "function": {
                    "name": "ui_get_snapshot",
                    "arguments": '{"page_key":"tenant.crm.detail"}',
                },
            },
            {
                "id": "call_fetch",
                "type": "function",
                "function": {
                    "name": "fetch_url",
                    "arguments": '{"url":"https://example.com"}',
                },
            },
        ],
    )
    runtime = _build_runtime(
        sandbox=sandbox,
        tools=[
            ToolDefinition(name="ui_get_snapshot", description="Get UI snapshot"),
            ToolDefinition(name="fetch_url", description="Fetch URL"),
        ],
        response=response,
        starting_total_tokens=24,
        starting_completion_tokens=24,
        messages=[ChatMessage(role="user", content="继续读取页面并补来源")],
    )
    events: list[dict] = []
    registered_budget_exit: list[str | None] = []

    result = await run_stream_tool_batch(
        runtime=runtime,
        callbacks=_build_callbacks(
            events=events,
            budget_exit_reason=lambda: (
                "tool_result_budget_exceeded" if sandbox.execute_count >= 1 else None
            ),
            registered_budget_exit=registered_budget_exit,
        ),
    )

    assert result.response is None
    assert [tool_result.name for tool_result in result.tool_results] == [
        "ui_get_snapshot"
    ]
    assert registered_budget_exit == ["tool_result_budget_exceeded"]
    assert [tc["id"] for tc in (runtime.messages[1].tool_calls or [])] == [
        "call_snapshot"
    ]
    assert [message.tool_call_id for message in runtime.messages if message.role == "tool"] == [
        "call_snapshot"
    ]


@pytest.mark.asyncio
async def test_run_stream_tool_batch_returns_confirmation_response_for_pending_consent() -> None:
    class _Sandbox:
        async def execute(self, *_args, **_kwargs) -> ToolResult:  # pragma: no cover
            raise AssertionError("consent pause should happen before execute()")

    response = ChatResponse(
        message=ChatMessage(role="assistant", content="我可以帮你抓网页"),
        tool_calls=[
            {
                "id": "call_fetch",
                "type": "function",
                "function": {
                    "name": "fetch_url",
                    "arguments": '{"url":"https://example.com"}',
                },
            }
        ],
    )
    runtime = _build_runtime(
        sandbox=_Sandbox(),
        tools=[ToolDefinition(name="fetch_url", description="Fetch URL")],
        response=response,
        tool_consent_modes={"fetch_url": "ask"},
    )
    events: list[dict] = []

    result = await run_stream_tool_batch(
        runtime=runtime,
        callbacks=_build_callbacks(events=events),
    )

    assert result.paused_for_confirmation is True
    assert result.response is not None
    assert result.response.metadata["skip_final_assistant"] is True
    tool_calls = result.response.tool_calls or []
    assert tool_calls[0]["pending_consent"]["tool_name"] == "fetch_url"
    assert any(event.get("event") == "tool_consent_request" for event in events)
