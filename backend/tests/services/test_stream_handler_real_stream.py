"""
StreamExecutionHandler 真实流式行为测试
"""

from __future__ import annotations

import json
from dataclasses import asdict
from types import SimpleNamespace

import pytest

from app.ai.engine.stream_handler import StreamExecutionHandler
from app.ai.tools.types import ToolDefinition, ToolResult
from app.ai.types import ChatChunk, ChatMessage


def _parse_sse_payload(raw: str) -> dict:
    """
    解析单条 SSE 文本（data: {...}\n\n）为 dict。
    """
    line = raw.strip()
    assert line.startswith("data: ")
    return json.loads(line[6:])


class _FakeSandbox:
    async def execute(
        self,
        tool_call_id: str,
        name: str,
        arguments: dict,
        definitions: list[ToolDefinition],
        conversation_id: int,
    ) -> ToolResult:
        _ = arguments, definitions, conversation_id
        return ToolResult(
            tool_call_id=tool_call_id,
            name=name,
            success=True,
            output='{"ok": true}',
        )


class _FakeEngine:
    def __init__(self, rounds: list[list[ChatChunk]]):
        self.sandbox = _FakeSandbox()
        self._rounds = rounds
        self._cursor = 0

    async def _stream_llm_chunks(self, **kwargs):
        _ = kwargs
        idx = self._cursor if self._cursor < len(self._rounds) else len(self._rounds) - 1
        self._cursor += 1
        for chunk in self._rounds[idx]:
            yield chunk

    @staticmethod
    def _messages_to_dicts(messages: list[ChatMessage]) -> list[dict]:
        return [asdict(m) for m in messages]


def _build_handler(engine: _FakeEngine) -> StreamExecutionHandler:
    request = SimpleNamespace(
        tenant_id=1,
        user_id=1,
        conversation_id=9001,
        messages=[ChatMessage(role="user", content="测试流式")],
    )
    prep = SimpleNamespace(
        messages=[ChatMessage(role="user", content="测试流式")],
        tools=[ToolDefinition(name="query_db", description="查询数据库")],
        rag_sources=None,
        optimize_event=None,
        tool_consent_modes={},
        route_result=None,
    )
    agent = SimpleNamespace(id=1)
    return StreamExecutionHandler(
        engine=engine,
        agent=agent,
        request=request,
        prep=prep,
        start_time=0.0,
        on_complete=None,
    )


@pytest.mark.asyncio
async def test_stream_handler_with_tools_keeps_real_delta_order():
    """
    有 tools 但本轮未触发 tool_call 时，必须直接透传模型增量，不允许整段合并。
    """
    engine = _FakeEngine(
        rounds=[
            [
                ChatChunk(delta="第", total_tokens=10),
                ChatChunk(delta="一", total_tokens=11),
                ChatChunk(delta="段", finish_reason="stop", total_tokens=12),
            ],
        ]
    )
    handler = _build_handler(engine)

    events: list[dict] = []
    async for raw in handler.generate():
        if raw.strip().startswith("data: {"):
            events.append(_parse_sse_payload(raw))

    message_deltas = [e["delta"] for e in events if e.get("event") == "message"]
    assert message_deltas == ["第", "一", "段"]
    assert any(e.get("event") == "done" for e in events)
    assert not any(e.get("event") == "thinking" for e in events)


@pytest.mark.asyncio
async def test_stream_handler_merges_stream_tool_calls_and_runs_tool():
    """
    流式 tool_call 增量（name/arguments 分片）应能正确合并并执行工具。
    """
    engine = _FakeEngine(
        rounds=[
            [
                ChatChunk(
                    delta="",
                    tool_calls=[
                        {
                            "index": 0,
                            "id": "call_1",
                            "type": "function",
                            "function": {"name": "query_", "arguments": '{"sql":"SE'},
                        }
                    ],
                    total_tokens=30,
                ),
                ChatChunk(
                    delta="",
                    tool_calls=[
                        {
                            "index": 0,
                            "id": "",
                            "type": "function",
                            "function": {"name": "query_db", "arguments": 'LECT 1"}'},
                        }
                    ],
                    finish_reason="tool_calls",
                    total_tokens=36,
                ),
            ],
            [
                ChatChunk(delta="查询完成", total_tokens=50),
                ChatChunk(delta="。", finish_reason="stop", total_tokens=52),
            ],
        ]
    )
    handler = _build_handler(engine)

    events: list[dict] = []
    async for raw in handler.generate():
        if raw.strip().startswith("data: {"):
            events.append(_parse_sse_payload(raw))

    assert any(e.get("event") == "thinking" for e in events)
    assert any(e.get("event") == "tool_start" and e.get("name") == "query_db" for e in events)
    assert any(e.get("event") == "tool_call" and e.get("success") is True for e in events)
    assert [e["delta"] for e in events if e.get("event") == "message"] == ["查询完成", "。"]
