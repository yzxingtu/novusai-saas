"""StreamExecutionHandler 真实流式行为测试 / Test."""

from __future__ import annotations

import json
import sys
import types
from dataclasses import asdict
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

# Stub redis/bcrypt/socketio before app imports (same pattern as test_tool_argument_recovery)
redis_module = types.ModuleType("redis")
redis_asyncio_module = types.ModuleType("redis.asyncio")
redis_asyncio_client_module = types.ModuleType("redis.asyncio.client")
redis_exceptions_module = types.ModuleType("redis.exceptions")


class _RedisConnectionPool:
    @classmethod
    def from_url(cls, *args, **kwargs):
        return cls()

    async def aclose(self) -> None:
        return None


class _RedisClient:
    def __init__(self, *args, **kwargs) -> None:
        return None


class _RedisPipeline:
    pass


redis_exceptions_module.RedisError = type("RedisError", (Exception,), {})
redis_asyncio_module.ConnectionPool = _RedisConnectionPool
redis_asyncio_module.Redis = _RedisClient
redis_asyncio_client_module.Pipeline = _RedisPipeline
redis_module.asyncio = redis_asyncio_module
redis_module.exceptions = redis_exceptions_module
bcrypt_module = types.ModuleType("bcrypt")
bcrypt_module.checkpw = lambda *a, **k: True
bcrypt_module.gensalt = lambda: b"salt"
bcrypt_module.hashpw = lambda p, s: p + s
sys.modules.setdefault("redis", redis_module)
sys.modules.setdefault("redis.asyncio", redis_asyncio_module)
sys.modules.setdefault("redis.asyncio.client", redis_asyncio_client_module)
sys.modules.setdefault("redis.exceptions", redis_exceptions_module)
sys.modules.setdefault("bcrypt", bcrypt_module)

_mock_sio = MagicMock()
_mock_sio.emit = AsyncMock()
_sio_mod = types.ModuleType("app.core.socketio_server")
_sio_mod.get_sio = lambda: _mock_sio
sys.modules.setdefault("app.core.socketio_server", _sio_mod)

from app.ai.engine.stream_handler import StreamExecutionHandler
from app.ai.tools.types import ToolDefinition, ToolResult
from app.ai.types import ChatChunk, ChatMessage


def _parse_sse_payload(raw: str) -> dict:
    """解析单条 SSE 文本（data: {...}\n\n）为 dict。 / Parse."""
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


def _build_handler(
    engine: _FakeEngine,
    tools: list[ToolDefinition] | None = None,
) -> StreamExecutionHandler:
    if tools is None:
        tools = [ToolDefinition(name="query_db", description="查询数据库")]
    request = SimpleNamespace(
        tenant_id=1,
        user_id=1,
        conversation_id=9001,
        messages=[ChatMessage(role="user", content="测试流式")],
    )
    prep = SimpleNamespace(
        messages=[ChatMessage(role="user", content="测试流式")],
        tools=tools,
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
    """有 tools 但本轮未触发 tool_call 时，必须直接透传模型增量，不允许整段合并。 / Model."""
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


@pytest.mark.asyncio
async def test_tool_call_name_matches_tool_start_when_sandbox_redirects():
    """
    When sandbox redirects pageop_* to invoke_page_operation, tool_call event
    must use original func_name (name_override) so frontend matches correctly.
    pageop_* 重定向后 tool_call 事件的 name 必须与 tool_start 一致（原始 func_name）。
    """
    class _RedirectSandbox:
        async def execute(
            self,
            tool_call_id: str,
            name: str,
            arguments: dict,
            definitions: list,
            conversation_id: int,
        ):
            _ = tool_call_id, arguments, definitions, conversation_id
            # Simulate sandbox redirect: pageop_* -> invoke_page_operation
            result_name = "invoke_page_operation" if name.startswith("pageop_") else name
            return ToolResult(
                tool_call_id="call_1",
                name=result_name,
                success=True,
                output='{"ok": true}',
            )

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
                            "function": {
                                "name": "pageop_get_editor_html",
                                "arguments": '{"page_key":"test"}',
                            },
                        },
                    ],
                    finish_reason="tool_calls",
                    total_tokens=50,
                ),
            ],
            [
                ChatChunk(delta="Done", finish_reason="stop", total_tokens=60),
            ],
        ],
    )
    engine.sandbox = _RedirectSandbox()
    tools = [
        ToolDefinition(name="pageop_get_editor_html", description="Get editor HTML"),
    ]
    handler = _build_handler(engine, tools=tools)

    events: list[dict] = []
    async for raw in handler.generate():
        if raw.strip().startswith("data: {"):
            events.append(_parse_sse_payload(raw))

    tool_starts = [e for e in events if e.get("event") == "tool_start"]
    tool_calls = [e for e in events if e.get("event") == "tool_call" and e.get("success")]
    assert len(tool_starts) >= 1
    assert len(tool_calls) >= 1
    assert tool_starts[0].get("name") == "pageop_get_editor_html"
    assert tool_calls[0].get("name") == "pageop_get_editor_html", (
        "tool_call name must match tool_start (name_override) when sandbox redirects"
    )


@pytest.mark.asyncio
async def test_parse_error_abort_after_consecutive_page_op_failures():
    """
    parse error 连续 3 次后触发熔断，停止工具循环并输出恢复提示。
    验证富文本审计方案：parse error 分支纳入熔断计数。
    """
    # 3 个 invoke_page_operation 调用，每个 arguments 为非法 JSON
    engine = _FakeEngine(
        rounds=[
            [
                ChatChunk(
                    delta="",
                    tool_calls=[
                        {"index": 0, "id": "c1", "type": "function", "function": {"name": "invoke_page_operation", "arguments": "{bad json 1"}},
                        {"index": 1, "id": "c2", "type": "function", "function": {"name": "invoke_page_operation", "arguments": "{bad json 2"}},
                        {"index": 2, "id": "c3", "type": "function", "function": {"name": "invoke_page_operation", "arguments": "{bad json 3"}},
                    ],
                    finish_reason="tool_calls",
                    total_tokens=100,
                ),
            ],
        ]
    )
    tools = [ToolDefinition(name="invoke_page_operation", description="Execute page op")]
    handler = _build_handler(engine, tools=tools)

    events: list[dict] = []
    async for raw in handler.generate():
        if raw.strip().startswith("data: {"):
            events.append(_parse_sse_payload(raw))

    # 应有 3 个 tool_call 失败事件
    failed_calls = [e for e in events if e.get("event") == "tool_call" and e.get("success") is False]
    assert len(failed_calls) >= 3

    # 熔断后 output 应包含恢复提示
    assert "Multiple page operations failed" in (handler._output or "")
    assert "retry" in (handler._output or "").lower() or "refresh" in (handler._output or "").lower()
