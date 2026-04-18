from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import pytest

from app.ai.engine.base import BaseEngine
from app.ai.engine.stream_runtime_contract import build_stream_runtime_contract
from app.ai.engine.stream_runtime_hooks import BaseEngineStreamRuntimeHooks
from app.ai.engine.types import ToolUsePolicy
from app.ai.tools.types import ToolResult
from app.ai.types import ChatMessage, ChatResponse


async def _unused_finalize(**kwargs):
    _ = kwargs
    raise AssertionError("fallback finalize should not be used in this test")


def _build_runtime_kwargs() -> dict[str, Any]:
    return {
        "agent": SimpleNamespace(id=1),
        "request": SimpleNamespace(tenant_id=1, conversation_id=9),
        "prep": SimpleNamespace(),
        "messages": [ChatMessage(role="user", content="hello")],
        "response": ChatResponse(message=ChatMessage(role="assistant", content="ok")),
        "state": SimpleNamespace(
            intent_plan=[],
            preparation_diagnostics={},
            provider_failure_kind="none",
        ),
        "tool_results": [ToolResult(tool_call_id="tc1", name="demo", success=True)],
        "reason": "completed",
        "total_tokens": 7,
        "completion_tokens_used": 7,
        "selected_skill_names": ["demo-skill"],
        "context_sources": [],
    }


@dataclass
class _ExplicitHooks:
    calls: list[str]

    def truncate_tool_calls_after_navigation(self, tool_calls):
        self.calls.append("truncate")
        return list(tool_calls), False

    def should_retry_tool_contract_breach(self, **kwargs):
        _ = kwargs
        self.calls.append("tool-retry")
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
        return "explicit partial", 11, 5

    async def finalize_completed_output(self, **kwargs):
        _ = kwargs
        self.calls.append("completed")
        return "explicit completed", 13, 7


class _BaseEngineStub(BaseEngine):
    def __init__(self) -> None:
        super().__init__(db=None, gateway=None, sandbox=None)
        self.logged_payload: dict[str, Any] | None = None

    async def execute(self, agent, request):  # pragma: no cover
        _ = agent, request
        raise NotImplementedError

    @classmethod
    def _truncate_tool_calls_after_navigation(cls, _tool_calls):
        return [{"id": "base"}], True

    @classmethod
    def _should_retry_tool_contract_breach(cls, **kwargs):
        _ = kwargs
        return True, ToolUsePolicy(reason="base"), "base-retry"

    @classmethod
    def _should_retry_web_research_contract_breach(cls, **kwargs):
        _ = kwargs
        return True, None, "base-web-retry"

    @classmethod
    def _analyze_post_tool_contract_breach(cls, **kwargs):
        _ = kwargs
        return "base-breach", None, {"source": "base-engine"}

    @classmethod
    def _restrict_tools_to_names(cls, tools, allowed_names):
        return [{"tools": list(tools), "allowed": allowed_names}]

    def _log_tool_contract_diagnostics(self, **kwargs):
        self.logged_payload = dict(kwargs)

    async def finalize_partial_output(self, **kwargs):
        _ = kwargs
        return "base partial", 19, 9

    async def finalize_completed_output(self, **kwargs):
        _ = kwargs
        return "base completed", 23, 10


@pytest.mark.asyncio
async def test_build_stream_runtime_contract_prefers_explicit_hooks_over_legacy_names() -> None:
    hook_calls: list[str] = []
    engine = SimpleNamespace(
        stream_runtime_hooks=_ExplicitHooks(calls=hook_calls),
        _should_retry_tool_contract_breach=lambda **kwargs: (
            (_ for _ in ()).throw(AssertionError(f"unexpected legacy path: {kwargs}"))
        ),
    )

    contract = build_stream_runtime_contract(engine)

    assert contract.should_retry_tool_contract_breach(
        response=None,
        current_policy=ToolUsePolicy(),
        tools=[],
        input_variables=None,
    ) == (False, None, "explicit")
    assert contract.analyze_post_tool_contract_breach(
        messages=[],
        response=ChatResponse(message=ChatMessage(role="assistant", content="ok")),
        current_policy=ToolUsePolicy(),
        tools=[],
        input_variables=None,
    ) == ("explicit", None, {"source": "hooks"})

    partial = await contract.finalize_partial_output(**_build_runtime_kwargs())
    completed = await contract.finalize_completed_output(**_build_runtime_kwargs())

    assert partial == ("explicit partial", 11, 5)
    assert completed == ("explicit completed", 13, 7)
    assert hook_calls == ["tool-retry", "analyze", "partial", "completed"]


@pytest.mark.asyncio
async def test_build_stream_runtime_contract_uses_base_engine_bridge_before_legacy_duck_typing() -> None:
    engine = _BaseEngineStub()
    engine.stream_runtime_hooks = BaseEngineStreamRuntimeHooks(
        engine=engine,
        finalize_partial_fallback=_unused_finalize,
        finalize_completed_fallback=_unused_finalize,
    )
    contract = build_stream_runtime_contract(engine)

    retry = contract.should_retry_tool_contract_breach(
        response=None,
        current_policy=ToolUsePolicy(),
        tools=[],
        input_variables=None,
    )
    analyze = contract.analyze_post_tool_contract_breach(
        messages=[],
        response=ChatResponse(message=ChatMessage(role="assistant", content="ok")),
        current_policy=ToolUsePolicy(),
        tools=[],
        input_variables=None,
    )
    restricted = contract.restrict_tools_to_names(["a", "b"], ["a"])
    contract.log_tool_contract_diagnostics(breach_type="tool_contract", retry_result="base")

    partial = await contract.finalize_partial_output(**_build_runtime_kwargs())
    completed = await contract.finalize_completed_output(**_build_runtime_kwargs())

    assert contract.truncate_tool_calls_after_navigation([{"id": "x"}]) == (
        [{"id": "base"}],
        True,
    )
    assert retry[0] is True
    assert retry[2] == "base-retry"
    assert analyze == ("base-breach", None, {"source": "base-engine"})
    assert restricted == [{"tools": ["a", "b"], "allowed": ["a"]}]
    assert engine.logged_payload == {
        "breach_type": "tool_contract",
        "retry_result": "base",
    }
    assert partial == ("base partial", 19, 9)
    assert completed == ("base completed", 23, 10)


@pytest.mark.asyncio
async def test_build_stream_runtime_contract_uses_default_helpers_without_implicit_hook_probe() -> (
    None
):
    class _ImplicitHelperStub:
        @staticmethod
        def _truncate_tool_calls_after_navigation(tool_calls):
            return list(tool_calls), False

        @staticmethod
        def _should_retry_tool_contract_breach(**kwargs):
            _ = kwargs
            return True, None, "implicit"

    contract = build_stream_runtime_contract(_ImplicitHelperStub())

    assert contract.should_retry_tool_contract_breach(
        response=ChatResponse(message=ChatMessage(role="assistant", content="")),
        current_policy=ToolUsePolicy(),
        tools=[],
        input_variables=None,
    ) == (False, None, "")
    assert contract.analyze_post_tool_contract_breach(
        messages=[],
        response=ChatResponse(message=ChatMessage(role="assistant", content="ok")),
        current_policy=ToolUsePolicy(),
        tools=[],
        input_variables=None,
    ) == (
        None,
        None,
        {
            "tool_leak_detected": False,
            "assistant_claimed_tool_call_without_tool_event": False,
            "leaked_tool_names": [],
            "requested_intents": [],
            "completed_intents": [],
            "unfinished_intents": [],
            "native_web_search_evidence": False,
        },
    )
    contract.log_tool_contract_diagnostics(test=True)

    partial = await contract.finalize_partial_output(**_build_runtime_kwargs())
    completed = await contract.finalize_completed_output(**_build_runtime_kwargs())

    assert partial == ("ok", 7, 7)
    assert completed == ("ok", 7, 7)
    assert contract.truncate_tool_calls_after_navigation([{"id": "x"}]) == (
        [{"id": "x"}],
        False,
    )


def test_build_stream_runtime_contract_uses_default_helpers_when_engine_is_empty() -> None:
    class _EmptyEngine:
        pass

    contract = build_stream_runtime_contract(_EmptyEngine())

    response = ChatResponse(message=ChatMessage(role="assistant", content=""))

    assert contract.should_retry_tool_contract_breach(
        response=response,
        current_policy=ToolUsePolicy(),
        tools=[],
        input_variables=None,
    ) == (False, None, "")
