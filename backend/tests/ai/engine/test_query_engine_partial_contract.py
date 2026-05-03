"""
Test type: behavioral
Scope: ConversationQueryEngine rescue and retry stop-loss behavior.
Mock strategy: only adapter/protocol transport edges are faked; runtime decisions are real.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.ai.exceptions import ProviderAuthError, ProviderError, ProviderTimeoutError
from app.ai.runtime.query_engine import ConversationQueryEngine
from app.ai.types import ChatChunk, ChatMessage, ChatResponse


class _BoomAfterChunkAdapter:
    wire_api = "chat_completions"

    async def stream_chat(self, **kwargs):
        _ = kwargs
        yield ChatChunk(delta="partial reply", role="assistant")
        raise RuntimeError("provider failed after partial progress")

    async def chat(self, **kwargs):
        _ = kwargs
        raise AssertionError("sync rescue should not be used in this test")


class _BudgetExitAfterChunkError(RuntimeError):
    termination_reason = "elapsed_budget_exceeded"


class _BudgetAfterChunkAdapter:
    wire_api = "chat_completions"

    async def stream_chat(self, **kwargs):
        _ = kwargs
        yield ChatChunk(delta="partial reply", role="assistant")
        raise _BudgetExitAfterChunkError("elapsed budget exceeded")

    async def chat(self, **kwargs):
        _ = kwargs
        raise AssertionError("sync rescue should not be used in this test")


class _ToolTimeoutAfterChunkError(RuntimeError):
    provider_failure_kind = "tool_timeout"


class _ToolTimeoutAfterChunkAdapter:
    wire_api = "chat_completions"

    async def stream_chat(self, **kwargs):
        _ = kwargs
        yield ChatChunk(delta="partial reply", role="assistant")
        raise _ToolTimeoutAfterChunkError("tool timeout after partial chunk")

    async def chat(self, **kwargs):
        _ = kwargs
        raise AssertionError("sync rescue should not be used in this test")


class _ReasoningOnlyThenErrorAdapter:
    wire_api = "responses"
    protocol_capabilities = SimpleNamespace(
        primary_wire_api="responses",
        allowed_wire_apis=("responses",),
        allowed_cross_protocol_fallbacks={},
        allow_adapter_cross_protocol_fallback=False,
    )

    def __init__(self) -> None:
        self.chat_calls = 0

    async def stream_chat(self, **kwargs):
        _ = kwargs
        yield ChatChunk(delta="", reasoning_delta="先检查公开资料", role="assistant")
        raise RuntimeError("responses stream interrupted after reasoning")

    async def chat(self, **kwargs):
        _ = kwargs
        self.chat_calls += 1
        return ChatResponse(
            message=ChatMessage(role="assistant", content="rescued reply"),
            finish_reason="stop",
            model="gpt-5.4",
        )


class _ReasoningOnlyThenTimeoutAdapter:
    wire_api = "responses"
    protocol_capabilities = SimpleNamespace(
        primary_wire_api="responses",
        allowed_wire_apis=("responses",),
        allowed_cross_protocol_fallbacks={},
        allow_adapter_cross_protocol_fallback=False,
    )

    def __init__(self) -> None:
        self.chat_calls = 0

    async def stream_chat(self, **kwargs):
        _ = kwargs
        yield ChatChunk(delta="", reasoning_delta="先检查公开资料", role="assistant")
        raise ProviderTimeoutError(
            "provider timed out",
            provider_code="openai_compatible",
            model_code="gpt-5.4",
        )

    async def chat(self, **kwargs):
        _ = kwargs
        self.chat_calls += 1
        raise AssertionError("timeout path should not trigger sync rescue")


class _ReasoningOnlyThenRetryableRescueAdapter:
    wire_api = "responses"
    protocol_capabilities = SimpleNamespace(
        primary_wire_api="responses",
        allowed_wire_apis=("responses",),
        allowed_cross_protocol_fallbacks={},
        allow_adapter_cross_protocol_fallback=False,
    )

    def __init__(self) -> None:
        self.chat_calls = 0
        self.chat_kwargs: list[dict] = []

    async def stream_chat(self, **kwargs):
        _ = kwargs
        yield ChatChunk(delta="", reasoning_delta="先检查公开资料", role="assistant")
        raise RuntimeError("responses stream interrupted after reasoning")

    async def chat(self, **kwargs):
        self.chat_kwargs.append(dict(kwargs))
        self.chat_calls += 1
        if self.chat_calls == 1:
            raise ProviderError(
                "service unavailable",
                provider_code="openai_compatible",
                model_code="gpt-5.4",
                error_code="503",
            )
        return ChatResponse(
            message=ChatMessage(role="assistant", content="rescued after retry"),
            finish_reason="stop",
            model="gpt-5.4",
        )


class _HostedSearchTimeoutThenBuiltinToolAdapter:
    wire_api = "chat_completions"
    protocol_capabilities = SimpleNamespace(
        primary_wire_api="chat_completions",
        allowed_wire_apis=("chat_completions", "responses"),
        allowed_cross_protocol_fallbacks={},
        allow_adapter_cross_protocol_fallback=False,
    )

    def __init__(self) -> None:
        self.stream_protocols: list[str] = []
        self.stream_tools: list[list[str]] = []

    async def stream_chat(self, **kwargs):
        protocol = str(kwargs.get("_runtime_force_wire_api") or "").strip()
        self.stream_protocols.append(protocol)
        self.stream_tools.append(
            [
                str((tool.get("function") or {}).get("name") or "").strip()
                for tool in kwargs.get("tools", []) or []
                if isinstance(tool, dict)
            ]
        )
        if protocol == "responses":
            assert kwargs["_runtime_hosted_web_search_required"] is True
            raise ProviderTimeoutError(
                "hosted search timed out",
                provider_code="openai_compatible",
                model_code="gpt-5.4",
            )
        yield ChatChunk(
            delta="",
            role="assistant",
            tool_calls=[
                {
                    "id": "call_builtin_search",
                    "type": "function",
                    "function": {
                        "name": "web_search",
                        "arguments": '{"query":"今天新闻"}',
                    },
                }
            ],
            finish_reason="tool_calls",
        )

    async def chat(self, **kwargs):
        _ = kwargs
        raise AssertionError("stream fallback should not use sync chat rescue")


class _HostedSearchTimeoutThenBuiltinChatAdapter:
    wire_api = "chat_completions"
    protocol_capabilities = SimpleNamespace(
        primary_wire_api="chat_completions",
        allowed_wire_apis=("chat_completions", "responses"),
        allowed_cross_protocol_fallbacks={},
        allow_adapter_cross_protocol_fallback=False,
    )

    def __init__(self) -> None:
        self.chat_protocols: list[str] = []

    async def stream_chat(self, **kwargs):
        _ = kwargs
        raise AssertionError("sync test should not stream")
        yield ChatChunk(delta="")

    async def chat(self, **kwargs):
        protocol = str(kwargs.get("_runtime_force_wire_api") or "").strip()
        self.chat_protocols.append(protocol)
        if protocol == "responses":
            raise ProviderTimeoutError(
                "hosted search timed out",
                provider_code="openai_compatible",
                model_code="gpt-5.4",
            )
        return ChatResponse(
            message=ChatMessage(
                role="assistant",
                content="",
                tool_calls=[
                    {
                        "id": "call_builtin_search",
                        "type": "function",
                        "function": {
                            "name": "web_search",
                            "arguments": '{"query":"今天新闻"}',
                        },
                    }
                ],
            ),
            finish_reason="tool_calls",
            model="gpt-5.4",
        )


class _HostedSearchAuthThenBuiltinResponsesAdapter:
    wire_api = "responses"
    protocol_capabilities = SimpleNamespace(
        primary_wire_api="responses",
        allowed_wire_apis=("responses",),
        allowed_cross_protocol_fallbacks={},
        allow_adapter_cross_protocol_fallback=False,
    )

    def __init__(self) -> None:
        self.stream_protocols: list[str] = []
        self.hosted_required_flags: list[bool] = []
        self.fallback_variants: list[str] = []

    async def stream_chat(self, **kwargs):
        protocol = str(kwargs.get("_runtime_force_wire_api") or "").strip()
        hosted_required = bool(kwargs.get("_runtime_hosted_web_search_required"))
        self.stream_protocols.append(protocol)
        self.hosted_required_flags.append(hosted_required)
        self.fallback_variants.append(
            str(kwargs.get("_runtime_native_web_search_fallback_variant") or "")
        )
        if hosted_required:
            raise ProviderAuthError(
                "hosted search quota is unavailable",
                provider_code="openai_compatible",
                model_code="gpt-5.4",
                error_code="insufficient_quota",
                status_code=403,
            )
        yield ChatChunk(
            delta="",
            role="assistant",
            tool_calls=[
                {
                    "id": "call_builtin_search",
                    "type": "function",
                    "function": {
                        "name": "web_search",
                        "arguments": '{"query":"今天新闻"}',
                    },
                }
            ],
            finish_reason="tool_calls",
        )

    async def chat(self, **kwargs):
        _ = kwargs
        raise AssertionError("stream fallback should not use sync chat rescue")


class _HostedSearchAuthThenBuiltinResponsesChatAdapter:
    wire_api = "responses"
    protocol_capabilities = SimpleNamespace(
        primary_wire_api="responses",
        allowed_wire_apis=("responses",),
        allowed_cross_protocol_fallbacks={},
        allow_adapter_cross_protocol_fallback=False,
    )

    def __init__(self) -> None:
        self.chat_protocols: list[str] = []
        self.hosted_required_flags: list[bool] = []
        self.fallback_variants: list[str] = []

    async def stream_chat(self, **kwargs):
        _ = kwargs
        raise AssertionError("sync test should not stream")
        yield ChatChunk(delta="")

    async def chat(self, **kwargs):
        protocol = str(kwargs.get("_runtime_force_wire_api") or "").strip()
        hosted_required = bool(kwargs.get("_runtime_hosted_web_search_required"))
        self.chat_protocols.append(protocol)
        self.hosted_required_flags.append(hosted_required)
        self.fallback_variants.append(
            str(kwargs.get("_runtime_native_web_search_fallback_variant") or "")
        )
        if hosted_required:
            raise ProviderAuthError(
                "hosted search quota is unavailable",
                provider_code="openai_compatible",
                model_code="gpt-5.4",
                error_code="insufficient_quota",
                status_code=403,
            )
        return ChatResponse(
            message=ChatMessage(
                role="assistant",
                content="",
                tool_calls=[
                    {
                        "id": "call_builtin_search",
                        "type": "function",
                        "function": {
                            "name": "web_search",
                            "arguments": '{"query":"今天新闻"}',
                        },
                    }
                ],
            ),
            finish_reason="tool_calls",
            model="gpt-5.4",
        )


class _HostedSearchProgressThenTimeoutAdapter:
    wire_api = "chat_completions"
    protocol_capabilities = SimpleNamespace(
        primary_wire_api="chat_completions",
        allowed_wire_apis=("chat_completions", "responses"),
        allowed_cross_protocol_fallbacks={},
        allow_adapter_cross_protocol_fallback=False,
    )

    def __init__(self) -> None:
        self.stream_protocols: list[str] = []

    async def stream_chat(self, **kwargs):
        protocol = str(kwargs.get("_runtime_force_wire_api") or "").strip()
        self.stream_protocols.append(protocol)
        if protocol == "responses":
            yield ChatChunk(delta="", metadata={"web_search_in_progress": True})
            raise ProviderTimeoutError(
                "hosted search timed out after progress",
                provider_code="openai_compatible",
                model_code="gpt-5.4",
            )
        yield ChatChunk(
            delta="",
            role="assistant",
            tool_calls=[
                {
                    "id": "call_builtin_search",
                    "type": "function",
                    "function": {
                        "name": "web_search",
                        "arguments": '{"query":"今天新闻"}',
                    },
                }
            ],
            finish_reason="tool_calls",
        )

    async def chat(self, **kwargs):
        _ = kwargs
        raise AssertionError("stream fallback should not use sync chat rescue")


class _HostedSearchProgressTimeoutThenBuiltinResponses502Adapter:
    wire_api = "responses"
    protocol_capabilities = SimpleNamespace(
        primary_wire_api="responses",
        allowed_wire_apis=("responses",),
        allowed_cross_protocol_fallbacks={},
        allow_adapter_cross_protocol_fallback=False,
    )

    def __init__(self) -> None:
        self.stream_attempts: list[dict[str, object]] = []
        self.chat_attempts: list[dict[str, object]] = []

    @staticmethod
    def _tool_names(kwargs: dict[str, object]) -> list[str]:
        return [
            str((tool.get("function") or {}).get("name") or "").strip()
            for tool in kwargs.get("tools", []) or []
            if isinstance(tool, dict)
        ]

    async def stream_chat(self, **kwargs):
        protocol = str(kwargs.get("_runtime_force_wire_api") or "").strip()
        hosted_required = bool(kwargs.get("_runtime_hosted_web_search_required"))
        fallback_variant = str(
            kwargs.get("_runtime_native_web_search_fallback_variant") or ""
        )
        self.stream_attempts.append(
            {
                "protocol": protocol,
                "hosted_required": hosted_required,
                "fallback_variant": fallback_variant,
                "tool_names": self._tool_names(kwargs),
            }
        )
        if hosted_required:
            yield ChatChunk(delta="", metadata={"web_search_in_progress": True})
            raise ProviderTimeoutError(
                "hosted search timed out after progress",
                provider_code="openai_compatible",
                model_code="gpt-5.4",
            )
        raise ProviderError(
            "builtin responses fallback upstream 502",
            provider_code="openai_compatible",
            model_code="gpt-5.4",
            error_code="502",
            status_code=502,
        )

    async def chat(self, **kwargs):
        protocol = str(kwargs.get("_runtime_force_wire_api") or "").strip()
        self.chat_attempts.append(
            {
                "protocol": protocol,
                "hosted_required": bool(
                    kwargs.get("_runtime_hosted_web_search_required")
                ),
                "fallback_variant": str(
                    kwargs.get("_runtime_native_web_search_fallback_variant") or ""
                ),
                "tool_names": self._tool_names(kwargs),
            }
        )
        if kwargs.get("_runtime_hosted_web_search_required"):
            raise ProviderTimeoutError(
                "hosted search timed out",
                provider_code="openai_compatible",
                model_code="gpt-5.4",
            )
        raise ProviderError(
            "builtin responses fallback upstream 502",
            provider_code="openai_compatible",
            model_code="gpt-5.4",
            error_code="502",
            status_code=502,
        )


class _HostedSearchProgressOnlyThenBuiltinAdapter:
    wire_api = "chat_completions"
    protocol_capabilities = SimpleNamespace(
        primary_wire_api="chat_completions",
        allowed_wire_apis=("chat_completions", "responses"),
        allowed_cross_protocol_fallbacks={},
        allow_adapter_cross_protocol_fallback=False,
    )

    def __init__(self) -> None:
        self.stream_protocols: list[str] = []

    async def stream_chat(self, **kwargs):
        protocol = str(kwargs.get("_runtime_force_wire_api") or "").strip()
        self.stream_protocols.append(protocol)
        if protocol == "responses":
            yield ChatChunk(delta="", metadata={"web_search_in_progress": True})
            return
        yield ChatChunk(
            delta="",
            role="assistant",
            tool_calls=[
                {
                    "id": "call_builtin_search",
                    "type": "function",
                    "function": {
                        "name": "web_search",
                        "arguments": '{"query":"今天新闻"}',
                    },
                }
            ],
            finish_reason="tool_calls",
        )

    async def chat(self, **kwargs):
        _ = kwargs
        raise AssertionError("stream fallback should not use sync chat rescue")


@pytest.mark.asyncio
async def test_runtime_query_engine_marks_partial_provider_failure_after_meaningful_chunk() -> (
    None
):
    query_engine = ConversationQueryEngine(
        adapter=_BoomAfterChunkAdapter(),
        strict_contract=False,
    )

    with pytest.raises(RuntimeError, match="provider failed after partial progress"):
        await query_engine.run_stream_turn(
            messages=[ChatMessage(role="user", content="继续")],
            model="gpt-5.4",
            temperature=0.0,
            max_tokens=None,
            top_p=1.0,
            tools=None,
            tool_choice=None,
            supports_vision=False,
            supports_audio=False,
            supports_video=False,
        )

    assert query_engine.turn_record.turn_outcome == "partial"
    assert (
        query_engine.turn_record.termination_reason
        == "provider_failure_after_partial_progress"
    )


@pytest.mark.asyncio
async def test_runtime_query_engine_preserves_specific_partial_termination_reason() -> (
    None
):
    query_engine = ConversationQueryEngine(
        adapter=_BudgetAfterChunkAdapter(),
        strict_contract=False,
    )

    with pytest.raises(_BudgetExitAfterChunkError, match="elapsed budget exceeded"):
        await query_engine.run_stream_turn(
            messages=[ChatMessage(role="user", content="继续")],
            model="gpt-5.4",
            temperature=0.0,
            max_tokens=None,
            top_p=1.0,
            tools=None,
            tool_choice=None,
            supports_vision=False,
            supports_audio=False,
            supports_video=False,
        )

    assert query_engine.turn_record.turn_outcome == "partial"
    assert query_engine.turn_record.termination_reason == "elapsed_budget_exceeded"


@pytest.mark.asyncio
async def test_runtime_query_engine_preserves_typed_tool_timeout_reason() -> None:
    query_engine = ConversationQueryEngine(
        adapter=_ToolTimeoutAfterChunkAdapter(),
        strict_contract=False,
    )

    with pytest.raises(_ToolTimeoutAfterChunkError, match="tool timeout"):
        await query_engine.run_stream_turn(
            messages=[ChatMessage(role="user", content="继续")],
            model="gpt-5.4",
            temperature=0.0,
            max_tokens=None,
            top_p=1.0,
            tools=None,
            tool_choice=None,
            supports_vision=False,
            supports_audio=False,
            supports_video=False,
        )

    assert query_engine.turn_record.turn_outcome == "partial"
    assert query_engine.turn_record.termination_reason == "tool_timeout"


@pytest.mark.asyncio
async def test_runtime_query_engine_sync_rescues_reasoning_only_stream_failure_without_fallback_chain() -> (
    None
):
    adapter = _ReasoningOnlyThenErrorAdapter()
    query_engine = ConversationQueryEngine(
        adapter=adapter,
        strict_contract=False,
    )

    chunks = await query_engine.run_stream_turn(
        messages=[ChatMessage(role="user", content="继续")],
        model="gpt-5.4",
        temperature=0.0,
        max_tokens=None,
        top_p=1.0,
        tools=None,
        tool_choice=None,
        supports_vision=False,
        supports_audio=False,
        supports_video=False,
    )

    assert [chunk.reasoning_delta for chunk in chunks if chunk.reasoning_delta] == [
        "先检查公开资料"
    ]
    assert [chunk.delta for chunk in chunks if chunk.delta] == ["rescued reply"]
    assert adapter.chat_calls == 1
    assert query_engine.turn_record.turn_outcome == "success"
    assert query_engine.turn_record.termination_reason == "protocol_fallback"
    assert query_engine.turn_record.metadata["sync_rescue"] is True
    assert query_engine.turn_record.metadata["sync_rescue_source"] == "stream_error"


@pytest.mark.asyncio
async def test_runtime_query_engine_does_not_sync_rescue_reasoning_only_timeout_failure() -> (
    None
):
    adapter = _ReasoningOnlyThenTimeoutAdapter()
    query_engine = ConversationQueryEngine(
        adapter=adapter,
        strict_contract=False,
    )

    with pytest.raises(ProviderTimeoutError, match="provider timed out"):
        await query_engine.run_stream_turn(
            messages=[ChatMessage(role="user", content="继续")],
            model="gpt-5.4",
            temperature=0.0,
            max_tokens=None,
            top_p=1.0,
            tools=None,
            tool_choice=None,
            supports_vision=False,
            supports_audio=False,
            supports_video=False,
        )

    assert adapter.chat_calls == 0
    assert query_engine.turn_record.turn_outcome == "failed"
    assert query_engine.turn_record.metadata["protocol_fallback_blocked_reason"] == (
        "provider_timeout"
    )


@pytest.mark.asyncio
async def test_runtime_query_engine_does_not_retry_sync_rescue_after_retryable_failure(
    monkeypatch,
) -> None:
    adapter = _ReasoningOnlyThenRetryableRescueAdapter()
    query_engine = ConversationQueryEngine(
        adapter=adapter,
        strict_contract=False,
    )

    async def _noop_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr("app.ai.runtime.query_engine.asyncio.sleep", _noop_sleep)

    with pytest.raises(ProviderError, match="service unavailable"):
        await query_engine.run_stream_turn(
            messages=[ChatMessage(role="user", content="继续")],
            model="gpt-5.4",
            temperature=0.0,
            max_tokens=None,
            top_p=1.0,
            tools=None,
            tool_choice=None,
            supports_vision=False,
            supports_audio=False,
            supports_video=False,
        )

    assert adapter.chat_calls == 1
    assert adapter.chat_kwargs[0]["_runtime_reasoning_effort_override"] == "low"
    assert query_engine.turn_record.turn_outcome == "failed"
    assert query_engine.turn_record.metadata["sync_rescue_attempt_count"] == 1
    assert query_engine.turn_record.metadata["sync_rescue_retry_count"] == 0


@pytest.mark.asyncio
async def test_runtime_query_engine_stream_falls_back_from_hosted_search_timeout_to_builtin_tools() -> (
    None
):
    adapter = _HostedSearchTimeoutThenBuiltinToolAdapter()
    query_engine = ConversationQueryEngine(
        adapter=adapter,
        strict_contract=True,
    )

    chunks = await query_engine.run_stream_turn(
        messages=[ChatMessage(role="user", content="联网查今天新闻")],
        model="gpt-5.4",
        temperature=0.0,
        max_tokens=None,
        top_p=1.0,
        tools=[
            {"type": "function", "function": {"name": "web_search"}},
            {"type": "function", "function": {"name": "fetch_url"}},
        ],
        tool_choice="required",
        supports_vision=False,
        supports_audio=False,
        supports_video=False,
        extra_kwargs={
            "_runtime_force_protocol_path": "responses",
            "_runtime_hosted_web_search_required": True,
        },
    )

    assert adapter.stream_protocols == ["responses", "chat_completions"]
    assert adapter.stream_tools == [
        ["web_search", "fetch_url"],
        ["web_search", "fetch_url"],
    ]
    assert chunks[0].tool_calls[0]["function"]["name"] == "web_search"
    assert query_engine.turn_record.turn_outcome == "success"
    assert query_engine.turn_record.termination_reason == "protocol_fallback"
    assert query_engine.turn_record.fallback_history[0].from_protocol == "responses"
    assert (
        query_engine.turn_record.fallback_history[0].to_protocol == "chat_completions"
    )
    assert (
        query_engine.turn_record.fallback_history[0].reason
        == "hosted_web_search_unavailable:provider_timeout"
    )
    assert "protocol_fallback_blocked_reason" not in query_engine.turn_record.metadata


@pytest.mark.asyncio
async def test_runtime_query_engine_stream_falls_back_from_hosted_search_auth_to_responses_builtin_tools() -> (
    None
):
    adapter = _HostedSearchAuthThenBuiltinResponsesAdapter()
    query_engine = ConversationQueryEngine(
        adapter=adapter,
        strict_contract=True,
    )

    chunks = await query_engine.run_stream_turn(
        messages=[ChatMessage(role="user", content="联网查今天新闻")],
        model="gpt-5.4",
        temperature=0.0,
        max_tokens=None,
        top_p=1.0,
        tools=[
            {"type": "function", "function": {"name": "web_search"}},
            {"type": "function", "function": {"name": "fetch_url"}},
        ],
        tool_choice="required",
        supports_vision=False,
        supports_audio=False,
        supports_video=False,
        extra_kwargs={
            "_runtime_force_protocol_path": "responses",
            "_runtime_hosted_web_search_required": True,
        },
    )

    assert adapter.stream_protocols == ["responses", "responses"]
    assert adapter.hosted_required_flags == [True, False]
    assert adapter.fallback_variants == ["", "builtin_web_research_tools"]
    assert chunks[0].tool_calls[0]["function"]["name"] == "web_search"
    assert query_engine.turn_record.turn_outcome == "success"
    assert query_engine.turn_record.termination_reason == "protocol_fallback"
    assert (
        query_engine.turn_record.fallback_history[0].reason
        == "hosted_web_search_unavailable:"
        "stream_exception_before_first_meaningful_chunk:ProviderAuthError"
    )


@pytest.mark.asyncio
async def test_runtime_query_engine_stream_falls_back_after_hosted_search_progress_only() -> (
    None
):
    adapter = _HostedSearchProgressOnlyThenBuiltinAdapter()
    query_engine = ConversationQueryEngine(
        adapter=adapter,
        strict_contract=True,
    )

    chunks = await query_engine.run_stream_turn(
        messages=[ChatMessage(role="user", content="联网查今天新闻")],
        model="gpt-5.4",
        temperature=0.0,
        max_tokens=None,
        top_p=1.0,
        tools=[
            {"type": "function", "function": {"name": "web_search"}},
            {"type": "function", "function": {"name": "fetch_url"}},
        ],
        tool_choice="required",
        supports_vision=False,
        supports_audio=False,
        supports_video=False,
        extra_kwargs={
            "_runtime_force_protocol_path": "responses",
            "_runtime_hosted_web_search_required": True,
        },
    )

    assert adapter.stream_protocols == ["responses", "chat_completions"]
    assert (chunks[0].metadata or {}).get("web_search_in_progress") is True
    assert chunks[1].tool_calls[0]["function"]["name"] == "web_search"
    assert (
        query_engine.turn_record.fallback_history[0].reason
        == "hosted_web_search_unavailable:stream_progress_only_no_meaningful_output"
    )


@pytest.mark.asyncio
async def test_runtime_query_engine_stream_falls_back_after_hosted_search_progress_timeout() -> (
    None
):
    adapter = _HostedSearchProgressThenTimeoutAdapter()
    query_engine = ConversationQueryEngine(
        adapter=adapter,
        strict_contract=True,
    )

    chunks = await query_engine.run_stream_turn(
        messages=[ChatMessage(role="user", content="联网查今天新闻")],
        model="gpt-5.4",
        temperature=0.0,
        max_tokens=None,
        top_p=1.0,
        tools=[
            {"type": "function", "function": {"name": "web_search"}},
            {"type": "function", "function": {"name": "fetch_url"}},
        ],
        tool_choice="required",
        supports_vision=False,
        supports_audio=False,
        supports_video=False,
        extra_kwargs={
            "_runtime_force_protocol_path": "responses",
            "_runtime_hosted_web_search_required": True,
        },
    )

    assert adapter.stream_protocols == ["responses", "chat_completions"]
    assert (chunks[0].metadata or {}).get("web_search_in_progress") is True
    assert chunks[1].tool_calls[0]["function"]["name"] == "web_search"
    assert query_engine.turn_record.turn_outcome == "success"
    assert query_engine.turn_record.termination_reason == "protocol_fallback"
    assert (
        query_engine.turn_record.fallback_history[0].reason
        == "hosted_web_search_unavailable:provider_timeout"
    )
    assert "protocol_fallback_blocked_reason" not in query_engine.turn_record.metadata


@pytest.mark.asyncio
async def test_runtime_query_engine_stream_synthesizes_builtin_web_search_after_builtin_responses_502() -> (
    None
):
    adapter = _HostedSearchProgressTimeoutThenBuiltinResponses502Adapter()
    query_engine = ConversationQueryEngine(
        adapter=adapter,
        strict_contract=True,
    )

    chunks = await query_engine.run_stream_turn(
        messages=[
            ChatMessage(role="user", content="帮我搜索一下2025年大模型使用token排行")
        ],
        model="gpt-5.4",
        temperature=0.0,
        max_tokens=None,
        top_p=1.0,
        tools=[
            {"type": "function", "function": {"name": "web_search"}},
            {"type": "function", "function": {"name": "fetch_url"}},
        ],
        tool_choice="required",
        supports_vision=False,
        supports_audio=False,
        supports_video=False,
        extra_kwargs={
            "_runtime_force_protocol_path": "responses",
            "_runtime_hosted_web_search_required": True,
        },
    )

    assert adapter.stream_attempts == [
        {
            "protocol": "responses",
            "hosted_required": True,
            "fallback_variant": "",
            "tool_names": ["web_search", "fetch_url"],
        },
        {
            "protocol": "responses",
            "hosted_required": False,
            "fallback_variant": "builtin_web_research_tools",
            "tool_names": ["web_search", "fetch_url"],
        },
    ]
    assert adapter.chat_attempts == []
    assert (chunks[0].metadata or {}).get("web_search_in_progress") is True
    assert chunks[1].tool_calls == [
        {
            "id": "synthetic_builtin_web_search_fallback",
            "type": "function",
            "function": {
                "name": "web_search",
                "arguments": (
                    '{"query":"帮我搜索一下2025年大模型使用token排行","max_results":5}'
                ),
            },
        }
    ]
    assert query_engine.turn_record.turn_outcome == "success"
    assert query_engine.turn_record.termination_reason == "protocol_fallback"
    assert query_engine.turn_record.fallback_history[0].recovered is True
    assert query_engine.turn_record.fallback_history[0].metadata["recovery_path"] == (
        "synthetic_builtin_web_search_tool_call"
    )
    assert (
        query_engine.turn_record.metadata[
            "native_web_search_builtin_fallback_synthesized"
        ]
        is True
    )
    assert (
        query_engine.turn_record.metadata[
            "native_web_search_builtin_fallback_error_status_code"
        ]
        == 502
    )
    assert "protocol_fallback_blocked_reason" not in query_engine.turn_record.metadata


@pytest.mark.asyncio
async def test_runtime_query_engine_sync_synthesizes_builtin_web_search_after_builtin_responses_502() -> (
    None
):
    adapter = _HostedSearchProgressTimeoutThenBuiltinResponses502Adapter()
    query_engine = ConversationQueryEngine(
        adapter=adapter,
        strict_contract=True,
    )

    response = await query_engine.run_chat_turn(
        messages=[
            ChatMessage(role="user", content="帮我搜索一下2025年大模型使用token排行")
        ],
        model="gpt-5.4",
        temperature=0.0,
        max_tokens=None,
        top_p=1.0,
        tools=[
            {"type": "function", "function": {"name": "web_search"}},
            {"type": "function", "function": {"name": "fetch_url"}},
        ],
        tool_choice="required",
        supports_vision=False,
        supports_audio=False,
        supports_video=False,
        extra_kwargs={
            "_runtime_force_protocol_path": "responses",
            "_runtime_hosted_web_search_required": True,
        },
    )

    assert adapter.chat_attempts == [
        {
            "protocol": "responses",
            "hosted_required": True,
            "fallback_variant": "",
            "tool_names": ["web_search", "fetch_url"],
        },
        {
            "protocol": "responses",
            "hosted_required": False,
            "fallback_variant": "builtin_web_research_tools",
            "tool_names": ["web_search", "fetch_url"],
        },
    ]
    assert adapter.stream_attempts == []
    assert response.tool_calls == [
        {
            "id": "synthetic_builtin_web_search_fallback",
            "type": "function",
            "function": {
                "name": "web_search",
                "arguments": (
                    '{"query":"帮我搜索一下2025年大模型使用token排行","max_results":5}'
                ),
            },
        }
    ]
    assert query_engine.turn_record.turn_outcome == "success"
    assert query_engine.turn_record.termination_reason == "protocol_fallback"
    assert query_engine.turn_record.fallback_history[0].recovered is True
    assert (
        query_engine.turn_record.metadata[
            "native_web_search_builtin_fallback_synthesized"
        ]
        is True
    )


@pytest.mark.asyncio
async def test_runtime_query_engine_sync_falls_back_from_hosted_search_timeout_to_builtin_tools() -> (
    None
):
    adapter = _HostedSearchTimeoutThenBuiltinChatAdapter()
    query_engine = ConversationQueryEngine(
        adapter=adapter,
        strict_contract=True,
    )

    response = await query_engine.run_chat_turn(
        messages=[ChatMessage(role="user", content="联网查今天新闻")],
        model="gpt-5.4",
        temperature=0.0,
        max_tokens=None,
        top_p=1.0,
        tools=[
            {"type": "function", "function": {"name": "web_search"}},
            {"type": "function", "function": {"name": "fetch_url"}},
        ],
        tool_choice="required",
        supports_vision=False,
        supports_audio=False,
        supports_video=False,
        extra_kwargs={
            "_runtime_force_protocol_path": "responses",
            "_runtime_hosted_web_search_required": True,
        },
    )

    assert adapter.chat_protocols == ["responses", "chat_completions"]
    assert response.message.tool_calls[0]["function"]["name"] == "web_search"
    assert query_engine.turn_record.turn_outcome == "success"
    assert query_engine.turn_record.termination_reason == "protocol_fallback"
    assert (
        query_engine.turn_record.fallback_history[0].reason
        == "hosted_web_search_unavailable:provider_timeout"
    )


@pytest.mark.asyncio
async def test_runtime_query_engine_sync_falls_back_from_hosted_search_auth_to_responses_builtin_tools() -> (
    None
):
    adapter = _HostedSearchAuthThenBuiltinResponsesChatAdapter()
    query_engine = ConversationQueryEngine(
        adapter=adapter,
        strict_contract=True,
    )

    response = await query_engine.run_chat_turn(
        messages=[ChatMessage(role="user", content="联网查今天新闻")],
        model="gpt-5.4",
        temperature=0.0,
        max_tokens=None,
        top_p=1.0,
        tools=[
            {"type": "function", "function": {"name": "web_search"}},
            {"type": "function", "function": {"name": "fetch_url"}},
        ],
        tool_choice="required",
        supports_vision=False,
        supports_audio=False,
        supports_video=False,
        extra_kwargs={
            "_runtime_force_protocol_path": "responses",
            "_runtime_hosted_web_search_required": True,
        },
    )

    assert adapter.chat_protocols == ["responses", "responses"]
    assert adapter.hosted_required_flags == [True, False]
    assert adapter.fallback_variants == ["", "builtin_web_research_tools"]
    assert response.message.tool_calls[0]["function"]["name"] == "web_search"
    assert query_engine.turn_record.turn_outcome == "success"
    assert query_engine.turn_record.termination_reason == "protocol_fallback"
    assert (
        query_engine.turn_record.fallback_history[0].reason
        == "hosted_web_search_unavailable:exception:ProviderAuthError"
    )


@pytest.mark.asyncio
async def test_runtime_query_engine_does_not_inject_invalid_runtime_retry_override() -> (
    None
):
    query_engine = ConversationQueryEngine(
        adapter=_ReasoningOnlyThenTimeoutAdapter(),
        strict_contract=False,
    )

    captured_extra_kwargs: list[dict[str, object]] = []

    async def _fake_chat(*, protocol_path, command, turn_record):
        _ = protocol_path, turn_record
        captured_extra_kwargs.append(dict(command.extra_kwargs or {}))
        return ChatResponse(
            message=ChatMessage(role="assistant", content="ok"),
            finish_reason="stop",
            model="gpt-5.4",
        )

    query_engine.runner.chat = _fake_chat  # type: ignore[method-assign]

    response = await query_engine.run_chat_turn(
        messages=[ChatMessage(role="user", content="继续")],
        model="gpt-5.4",
        temperature=0.0,
        max_tokens=None,
        top_p=1.0,
        tools=None,
        tool_choice=None,
        supports_vision=False,
        supports_audio=False,
        supports_video=False,
    )

    assert response.message.content == "ok"
    assert "_runtime_client_max_retries_override" not in captured_extra_kwargs[0]
    assert "timeout_seconds" not in captured_extra_kwargs[0]
