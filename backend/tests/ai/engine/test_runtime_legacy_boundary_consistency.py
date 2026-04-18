from __future__ import annotations

import importlib
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.ai.adapters.openai_compatible.compat.legacy_context_builder import (
    LegacyEntrypointGuardSnapshot,
)
from app.ai.adapters.openai_compatible.compat.legacy_entrypoint_facade import (
    execute_legacy_adapter_chat_entrypoint,
    execute_legacy_adapter_stream_entrypoint,
)
from app.ai.adapters.openai_compatible.compat.legacy_protocol_execution_helpers import (
    execute_legacy_chat,
)
from app.ai.adapters.openai_compatible.protocol_runtime_context import (
    prepare_protocol_execution_context,
)
from app.ai.context.engine import ConversationContextEngine
from app.ai.engine.conversation_entrypoints import _SyncIOAdapter
from app.ai.engine.stream_runtime_contract import build_stream_runtime_contract
from app.ai.engine.types import ExecutionRequest, ToolUsePolicy
from app.ai.exceptions import ProviderError
from app.ai.runtime.contracts import (
    ContextCapabilityAwareness,
    ContextCapabilityFinalization,
    ProtocolGuardContract,
    TurnCommand,
)
from app.ai.runtime.protocol_runner import ProtocolRunner
from app.ai.runtime.types import CapabilityBundle, TurnRecord
from app.ai.tools.types import ToolDefinition, ToolResult
from app.ai.types import ChatChunk, ChatMessage, ChatResponse


def test_runtime_bridge_and_engine_base_import_without_cycle() -> None:
    importlib.import_module("app.ai.runtime.context_capability_bridge")
    importlib.import_module("app.ai.engine.base")


def test_protocol_runtime_context_rejects_disabled_cross_protocol_guard() -> None:
    adapter = _ProtocolRuntimeAdapterStub()

    with pytest.raises(ProviderError) as exc_info:
        prepare_protocol_execution_context(
            adapter=adapter,
            wire_api="responses",
            model="gpt-5.4",
            stream=False,
            kwargs={
                ProtocolGuardContract.RUNTIME_DISABLE_CROSS_PROTOCOL_FALLBACK: False,
            },
            default_stream_timeout_seconds=15.0,
        )

    assert exc_info.value.error_code == "invalid_runtime_guard"


class _ProtocolRunnerAdapterStub:
    def __init__(self) -> None:
        self.protocol_calls: list[dict[str, Any]] = []
        self.chat_calls: list[dict[str, Any]] = []

    async def execute_protocol_chat(self, **kwargs: Any) -> ChatResponse:
        self.protocol_calls.append(dict(kwargs))
        return ChatResponse(message=ChatMessage(role="assistant", content="ok"))

    async def chat(self, **kwargs: Any) -> ChatResponse:
        self.chat_calls.append(dict(kwargs))
        return ChatResponse(message=ChatMessage(role="assistant", content="legacy"))


class _ProtocolRuntimeAdapterStub:
    def __init__(self) -> None:
        self.protocol_capabilities = SimpleNamespace(
            resolve_runtime_wire_api=lambda wire_api: wire_api
        )
        self.config = {"model_config": {"reasoning": {"effort": "low"}}}

    def resolve_effective_model_request(
        self,
        *,
        model: str,
        model_config: Any = None,
        wire_api: str | None = None,
    ) -> dict[str, Any]:
        _ = model_config, wire_api
        return {"upstream_model": model, "effective_params": {}}

    def _apply_runtime_reasoning_effort_override(
        self,
        effective_request: dict[str, Any],
        *,
        reasoning_effort: Any,
        wire_api: str,
    ) -> dict[str, Any]:
        _ = reasoning_effort, wire_api
        return effective_request

    def _log_effective_model_request(
        self,
        *,
        effective_request: dict[str, Any],
        wire_api: str,
    ) -> None:
        _ = effective_request, wire_api

    def _normalize_timeout_seconds(self, timeout: Any) -> float | None:
        _ = timeout
        return None


@pytest.mark.asyncio
async def test_protocol_runner_uses_protocol_entrypoint_only_once() -> None:
    adapter = _ProtocolRunnerAdapterStub()
    runner = ProtocolRunner(adapter=adapter)
    command = TurnCommand(
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4",
    )

    await runner.chat(
        protocol_path="responses",
        command=command,
        turn_record=TurnRecord(),
    )

    assert len(adapter.protocol_calls) == 1
    assert adapter.chat_calls == []
    assert adapter.protocol_calls[0]["wire_api"] == "responses"


class _LegacyEntrypointAdapterStub:
    def __init__(self) -> None:
        self.prepare_calls = 0
        self.chat_calls: list[dict[str, Any]] = []
        self.chat_fallback_flags: list[bool] = []
        self.responses_calls: list[dict[str, Any]] = []
        self.wire_api = "responses"

    def _prepare_protocol_execution_context(
        self,
        *,
        wire_api: str | None,
        model: str,
        stream: bool,
        kwargs: dict[str, Any],
    ) -> dict[str, Any]:
        _ = stream
        self.prepare_calls += 1
        if self.prepare_calls > 1:
            raise AssertionError("protocol context prepared more than once")
        active_wire_api = wire_api or self.wire_api
        return {
            "active_endpoint_path": f"/v1/{active_wire_api}",
            "active_wire_api": active_wire_api,
            "effective_request": {"upstream_model": model},
            "effective_error_model": model,
            "runtime_model_config": None,
            "supports_vision": False,
            "supports_audio": False,
            "supports_video": False,
            "kwargs": dict(kwargs),
        }

    async def _convert_messages(
        self,
        messages: list[ChatMessage],
        *,
        supports_vision: bool,
        supports_audio: bool,
        supports_video: bool,
    ) -> list[dict[str, Any]]:
        _ = supports_vision, supports_audio, supports_video
        return [
            {"role": message.role, "content": message.content} for message in messages
        ]

    def _build_chat_completions_request(
        self,
        *,
        openai_messages: list[dict[str, Any]],
        model: str,
        temperature: float,
        max_tokens: int | None,
        top_p: float,
        tools: list[dict] | None,
        tool_choice: str | None,
        stream: bool,
        **_kwargs: Any,
    ) -> dict[str, Any]:
        _ = (
            temperature,
            max_tokens,
            top_p,
            tools,
            tool_choice,
            stream,
        )
        return {"model": model, "messages": list(openai_messages)}

    async def _chat_via_chat_completions(
        self,
        *,
        request_params: dict[str, Any],
        messages: list[ChatMessage],
        model: str,
        fallback_to_responses: bool = True,
        responses_kwargs: dict[str, Any] | None = None,
    ) -> ChatResponse:
        _ = request_params, messages, model, responses_kwargs
        self.chat_fallback_flags.append(bool(fallback_to_responses))
        self.chat_calls.append({"wire_api": "chat_completions"})
        return ChatResponse(message=ChatMessage(role="assistant", content="ok"))

    async def _chat_via_responses(self, **kwargs: Any) -> ChatResponse:
        self.responses_calls.append(dict(kwargs))
        return ChatResponse(message=ChatMessage(role="assistant", content="responses"))

    def _augment_request_metadata(
        self,
        metadata: dict[str, Any] | None,
        *,
        effective_request: dict[str, Any],
    ) -> dict[str, Any]:
        _ = effective_request
        return dict(metadata or {})

    def _log_upstream_error(
        self,
        error: Exception,
        *,
        endpoint_path: str,
        model: str,
        wire_api: str,
    ) -> None:
        _ = error, endpoint_path, model, wire_api


class _LegacyFallbackError(Exception):
    def __init__(self, status_code: int) -> None:
        super().__init__("responses failure")
        self.status_code = status_code


class _LegacyFallbackAdapterStub:
    def __init__(self) -> None:
        def _allow_cross_protocol_fallback(*, from_wire_api, to_wire_api) -> bool:
            _ = from_wire_api, to_wire_api
            return True

        self.protocol_capabilities = SimpleNamespace(
            is_cross_protocol_fallback_allowed=_allow_cross_protocol_fallback
        )
        self.provider_config = {}
        self.responses_calls = 0
        self.chat_calls = 0

    async def _chat_via_responses(self, **kwargs: Any) -> ChatResponse:
        _ = kwargs
        self.responses_calls += 1
        raise _LegacyFallbackError(status_code=500)

    async def _chat_via_chat_completions(
        self,
        *,
        request_params: dict[str, Any],
        messages: list[ChatMessage],
        model: str,
        fallback_to_responses: bool = True,
        responses_kwargs: dict[str, Any] | None = None,
    ) -> ChatResponse:
        _ = request_params, messages, model, fallback_to_responses, responses_kwargs
        self.chat_calls += 1
        return ChatResponse(message=ChatMessage(role="assistant", content="ok"))


class _LegacyStreamEntrypointAdapterStub(_LegacyEntrypointAdapterStub):
    def __init__(self) -> None:
        super().__init__()
        self.request_builds: list[dict[str, Any]] = []
        self.stream_calls = 0
        self.sync_calls = 0
        self.sync_fallback_flags: list[bool] = []
        self.wire_api = "chat_completions"

    def _build_chat_completions_request(
        self,
        *args: Any,
        stream: bool,
        **kwargs: Any,
    ) -> dict[str, Any]:
        request = super()._build_chat_completions_request(*args, stream=stream, **kwargs)
        self.request_builds.append({"stream": stream, "model": request["model"]})
        return request

    async def _stream_chat_via_chat_completions(self, **kwargs: Any):
        _ = kwargs
        self.stream_calls += 1
        if False:
            yield ChatChunk(delta="noop")

    async def _stream_chat_via_responses(self, **kwargs: Any):
        _ = kwargs
        raise AssertionError("responses stream should not be used")

    async def _chat_via_chat_completions(
        self,
        *,
        request_params: dict[str, Any],
        messages: list[ChatMessage],
        model: str,
        fallback_to_responses: bool = True,
        responses_kwargs: dict[str, Any] | None = None,
    ) -> ChatResponse:
        _ = request_params, messages, model, responses_kwargs
        self.sync_calls += 1
        self.sync_fallback_flags.append(bool(fallback_to_responses))
        return ChatResponse(message=ChatMessage(role="assistant", content="rescued"))

    @staticmethod
    def _stream_chunk_blocks_fallback(chunk: ChatChunk) -> bool:
        return bool(str(getattr(chunk, "delta", "") or "").strip())

    def _chat_response_to_stream_chunk(self, response: ChatResponse) -> ChatChunk:
        return ChatChunk(delta=response.message.content, metadata=response.metadata)


@pytest.mark.asyncio
async def test_legacy_entrypoint_uses_prepared_protocol_context_once() -> None:
    adapter = _LegacyEntrypointAdapterStub()

    response = await execute_legacy_adapter_chat_entrypoint(
        adapter=adapter,
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4",
        temperature=0.2,
        max_tokens=128,
        top_p=0.9,
        tools=None,
        tool_choice=None,
        _runtime_force_wire_api="chat_completions",
        **ProtocolGuardContract(
            disable_cross_protocol_fallback=True,
            disable_sync_rescue=True,
        ).to_runtime_kwargs(),
    )

    assert response.message.content == "ok"
    assert adapter.prepare_calls == 1
    assert adapter.chat_calls == [{"wire_api": "chat_completions"}]
    assert adapter.chat_fallback_flags == [False]
    assert adapter.responses_calls == []


@pytest.mark.asyncio
async def test_legacy_entrypoint_respects_cross_protocol_guard() -> None:
    adapter = _LegacyFallbackAdapterStub()

    with pytest.raises(_LegacyFallbackError):
        await execute_legacy_chat(
            adapter=adapter,
            execution_state={
                "active_endpoint_path": "/v1/responses",
                "active_wire_api": "responses",
            },
            messages=[ChatMessage(role="user", content="hello")],
            model="gpt-5.4",
            tools=[{"type": "function", "function": {"name": "test"}}],
            tool_choice="required",
            use_responses_api=True,
            guard_snapshot=LegacyEntrypointGuardSnapshot(
                runtime_disable_cross_protocol_fallback=True,
                runtime_disable_sync_rescue=True,
            ),
            request_params={"model": "gpt-5.4"},
            responses_kwargs={"messages": [ChatMessage(role="user", content="hello")]},
        )

    assert adapter.responses_calls == 1
    assert adapter.chat_calls == 0


@pytest.mark.asyncio
async def test_legacy_stream_entrypoint_prepares_protocol_context_once() -> None:
    adapter = _LegacyStreamEntrypointAdapterStub()
    chunks: list[ChatChunk] = []

    async for chunk in execute_legacy_adapter_stream_entrypoint(
        adapter=adapter,
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4",
        temperature=0.2,
        max_tokens=128,
        top_p=0.9,
        tools=None,
        tool_choice=None,
        _runtime_force_wire_api="chat_completions",
        **{
            ProtocolGuardContract.RUNTIME_DISABLE_CROSS_PROTOCOL_FALLBACK: True,
        },
    ):
        chunks.append(chunk)

    assert [entry["stream"] for entry in adapter.request_builds] == [True, False]
    assert adapter.prepare_calls == 1
    assert adapter.stream_calls == 1
    assert adapter.sync_calls == 1
    assert adapter.sync_fallback_flags == [False]
    assert [chunk.delta for chunk in chunks] == ["rescued"]


@pytest.mark.asyncio
async def test_legacy_stream_entrypoint_skips_sync_rescue_when_runtime_guard_set() -> (
    None
):
    adapter = _LegacyStreamEntrypointAdapterStub()
    chunks = [
        chunk
        async for chunk in execute_legacy_adapter_stream_entrypoint(
            adapter=adapter,
            messages=[ChatMessage(role="user", content="hello")],
            model="gpt-5.4",
            temperature=0.2,
            max_tokens=128,
            top_p=0.9,
            tools=None,
            tool_choice=None,
            _runtime_force_wire_api="chat_completions",
            **{ProtocolGuardContract.RUNTIME_DISABLE_SYNC_RESCUE: True},
        )
    ]

    assert [chunk.delta for chunk in chunks] == []
    assert adapter.stream_calls == 1
    assert adapter.sync_calls == 0
    assert adapter.sync_fallback_flags == []


@dataclass
class _ExplicitHooks:
    calls: list[str]

    def truncate_tool_calls_after_navigation(self, tool_calls):
        self.calls.append("truncate")
        return list(tool_calls), False

    def should_retry_tool_contract_breach(self, **kwargs):
        _ = kwargs
        self.calls.append("retry")
        return False, None, "explicit"

    def should_retry_web_research_contract_breach(self, **kwargs):
        _ = kwargs
        self.calls.append("web-retry")
        return False, None, "explicit-web"

    def analyze_post_tool_contract_breach(self, **kwargs):
        _ = kwargs
        self.calls.append("analyze")
        return "explicit", None, {"source": "hooks"}

    def restrict_tools_to_names(self, tools, allowed_tool_names):
        self.calls.append("restrict")
        return [tools, allowed_tool_names]

    def log_tool_contract_diagnostics(self, **kwargs):
        _ = kwargs
        self.calls.append("log")

    async def finalize_partial_output(self, **kwargs):
        _ = kwargs
        self.calls.append("partial")
        return "partial", 1, 1

    async def finalize_completed_output(self, **kwargs):
        _ = kwargs
        self.calls.append("completed")
        return "completed", 2, 2


class _ExplicitEngineWithLegacyHooks:
    def __init__(self, calls: list[str]) -> None:
        self.stream_runtime_hooks = _ExplicitHooks(calls=calls)

        def _legacy_hook(*_args, **_kwargs):
            raise AssertionError("legacy hook should not be called")

        for name in (
            "truncate_tool_calls_after_navigation",
            "should_retry_tool_contract_breach",
            "should_retry_web_research_contract_breach",
            "analyze_post_tool_contract_breach",
            "restrict_tools_to_names",
            "log_tool_contract_diagnostics",
            "finalize_partial_output",
            "finalize_completed_output",
        ):
            setattr(self, name, _legacy_hook)


@pytest.mark.asyncio
async def test_stream_runtime_contract_prefers_explicit_hooks() -> None:
    hook_calls: list[str] = []

    class _EngineStub:
        stream_runtime_hooks = _ExplicitHooks(calls=hook_calls)

        @staticmethod
        def _should_retry_tool_contract_breach(**_kwargs):
            raise AssertionError("legacy helper should not be called")

    contract = build_stream_runtime_contract(_EngineStub())

    assert contract.should_retry_tool_contract_breach(
        response=None,
        current_policy=ToolUsePolicy(),
        tools=[],
        input_variables=None,
    ) == (False, None, "explicit")

    await contract.finalize_partial_output(
        agent=SimpleNamespace(id=1),
        request=SimpleNamespace(tenant_id=1, conversation_id=9),
        prep=SimpleNamespace(),
        messages=[ChatMessage(role="user", content="hello")],
        response=ChatResponse(message=ChatMessage(role="assistant", content="ok")),
        state=SimpleNamespace(
            intent_plan=[],
            preparation_diagnostics={},
            provider_failure_kind="none",
        ),
        tool_results=[],
        reason="partial",
        total_tokens=1,
        completion_tokens_used=1,
        selected_skill_names=[],
        context_sources=[],
    )

    assert hook_calls[:2] == ["retry", "partial"]


def test_sync_runtime_adapter_prefers_explicit_hooks() -> None:
    hook_calls: list[str] = []
    runtime_contract = build_stream_runtime_contract(
        SimpleNamespace(stream_runtime_hooks=_ExplicitHooks(calls=hook_calls))
    )
    adapter = _SyncIOAdapter(
        engine=SimpleNamespace(),
        agent=SimpleNamespace(id=1),
        request=SimpleNamespace(tenant_id=1, conversation_id=9),
        prep=SimpleNamespace(),
        selected_skill_names=[],
        context_sources=[],
        runtime_contract=runtime_contract,
    )

    assert adapter.should_retry_tool_contract_breach(
        response=None,
        current_policy=ToolUsePolicy(),
        tools=[],
        input_variables=None,
    ) == (False, None, "explicit")
    assert hook_calls == ["retry"]


@pytest.mark.asyncio
async def test_sync_runtime_adapter_uses_shared_tool_batch_runtime() -> None:
    class _Sandbox:
        async def execute(
            self,
            tool_call_id: str,
            name: str,
            arguments: dict[str, Any],
            definitions: list[ToolDefinition],
            conversation_id: int,
        ) -> ToolResult:
            _ = definitions, conversation_id
            return ToolResult(
                tool_call_id=tool_call_id,
                name=name,
                success=True,
                output=f"snapshot:{arguments.get('page_key')}",
            )

    async def _legacy_handle_tool_calls(**_kwargs: Any) -> None:
        raise AssertionError("legacy sync tool loop should not be used")

    adapter = _SyncIOAdapter(
        engine=SimpleNamespace(
            sandbox=_Sandbox(),
            _handle_tool_calls=_legacy_handle_tool_calls,
        ),
        agent=SimpleNamespace(id=1),
        request=SimpleNamespace(
            tenant_id=1,
            conversation_id=9,
            interaction_mode="confirm",
            interaction_updates=None,
        ),
        prep=SimpleNamespace(
            all_tools=[ToolDefinition(name="ui_get_snapshot", description="Read page")],
            tool_consent_modes={},
        ),
        selected_skill_names=[],
        context_sources=[],
        runtime_contract=build_stream_runtime_contract(SimpleNamespace()),
    )

    response = ChatResponse(
        message=ChatMessage(
            role="assistant",
            content="",
            tool_calls=[
                {
                    "id": "call_page",
                    "type": "function",
                    "function": {
                        "name": "ui_get_snapshot",
                        "arguments": '{"page_key":"admin.ai.conversations"}',
                    },
                }
            ],
        ),
        tool_calls=[
            {
                "id": "call_page",
                "type": "function",
                "function": {
                    "name": "ui_get_snapshot",
                    "arguments": '{"page_key":"admin.ai.conversations"}',
                },
            }
        ],
    )

    result = await adapter.handle_tool_calls(
        response=response,
        tools=[ToolDefinition(name="ui_get_snapshot", description="Read page")],
        messages=[ChatMessage(role="user", content="继续看页面")],
        starting_total_tokens=3,
        starting_completion_tokens=3,
    )

    assert result.response is None
    assert [tool_result.name for tool_result in result.tool_results] == [
        "ui_get_snapshot"
    ]
    assert result.tool_results[0].output == "snapshot:admin.ai.conversations"
    assert result.total_tokens == 3
    assert result.completion_tokens_used == 3


@pytest.mark.asyncio
async def test_stream_runtime_contract_prefers_explicit_hooks_over_legacy_helpers() -> (
    None
):
    hook_calls: list[str] = []
    engine = _ExplicitEngineWithLegacyHooks(calls=hook_calls)

    contract = build_stream_runtime_contract(engine)

    assert contract.restrict_tools_to_names(["tool-a"], ["tool-a"]) == [
        ["tool-a"],
        ["tool-a"],
    ]
    assert contract.truncate_tool_calls_after_navigation([{"name": "ui_get_snapshot"}]) == (
        [{"name": "ui_get_snapshot"}],
        False,
    )

    await contract.finalize_completed_output(
        agent=SimpleNamespace(id=1),
        request=SimpleNamespace(tenant_id=1, conversation_id=9),
        prep=SimpleNamespace(),
        messages=[ChatMessage(role="user", content="hello")],
        response=ChatResponse(message=ChatMessage(role="assistant", content="ok")),
        state=SimpleNamespace(
            intent_plan=[],
            preparation_diagnostics={},
            provider_failure_kind="none",
        ),
        tool_results=[],
        reason="completed",
        total_tokens=2,
        completion_tokens_used=2,
        selected_skill_names=[],
        context_sources=[],
    )

    assert hook_calls == ["restrict", "truncate", "completed"]


@pytest.mark.asyncio
async def test_context_engine_finalization_uses_capability_bridge_contract() -> None:
    class _PromptBridgeStub:
        @staticmethod
        def _build_system_message(agent, input_variables=None):
            _ = input_variables
            return ChatMessage(role="system", content=agent.system_prompt or "")

        @staticmethod
        def _build_web_research_continuation_context(*_args, **_kwargs):
            return None

    class _BridgeStub:
        def __init__(self) -> None:
            self.calls: list[str] = []

        async def resolve_runtime_model_capabilities(self, *, agent):
            _ = agent
            self.calls.append("resolve")
            return {"supports_audio": False}

        def build_provisional_bundle(self, *_, **__):
            self.calls.append("provisional")
            return CapabilityBundle()

        async def compute_awareness(self, **_kwargs):
            self.calls.append("awareness")
            return ContextCapabilityAwareness(enabled=False)

        async def finalize_capabilities(
            self,
            *,
            capability_injection_decision,
            **_kwargs,
        ):
            self.calls.append("finalize")
            return ContextCapabilityFinalization(
                capability_bundle=CapabilityBundle(),
                diagnostics={},
                capability_injection_decision=dict(capability_injection_decision or {}),
                runtime_manifest={
                    "manifest_version": "runtime-capability-manifest/v1",
                    "scope": "turn",
                },
                runtime_capability_summary={
                    "manifest_version": "runtime-capability-manifest/v1"
                },
            )

    engine = ConversationContextEngine(db=object(), base_engine=_PromptBridgeStub())
    engine.capability_bridge = _BridgeStub()
    agent = SimpleNamespace(
        id=1,
        name="Bridge Tester",
        system_prompt="System prompt.",
        rag_config=None,
        context_config=None,
        model=None,
    )
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        messages=[ChatMessage(role="user", content="hello")],
        input_variables={},
    )

    with (
        patch(
            "app.ai.rag_injector.load_agent_kb_bindings",
            new=AsyncMock(return_value=([], {})),
        ),
        patch(
            "app.ai.engine.intent_planner.IntentPlanner.plan_turn",
            return_value=[],
        ),
    ):
        assembly = await engine.assemble(agent, request, skill_result=None)

    assert "finalize" in engine.capability_bridge.calls
    assert assembly.diagnostics["runtime_capability_manifest"]["manifest_version"] == (
        "runtime-capability-manifest/v1"
    )
    assert assembly.diagnostics["runtime_capability_summary"]["manifest_version"] == (
        "runtime-capability-manifest/v1"
    )


def test_context_followup_helper_skips_short_followups_independently() -> None:
    assert ConversationContextEngine._should_run_memory_vector_recall("ok") is False
