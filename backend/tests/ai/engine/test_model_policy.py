"""
Test type: structural
Scope: model request override policy for text, tool, and native-search turns.
Mocked dependencies: local runtime-context namespaces only; policy code runs real.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.ai.engine.model_policy import build_model_request_overrides
from app.ai.engine.types import ToolUsePolicy
from app.ai.tools.types import ToolDefinition


def _tool(name: str) -> ToolDefinition:
    return ToolDefinition(name=name, description=name)


def test_build_model_request_overrides_fast_text_turn_uses_low_reasoning() -> None:
    assert build_model_request_overrides(execution_path="fast", tools=None) == {
        "_runtime_reasoning_effort_override": "low",
    }


def test_build_model_request_overrides_data_tool_turn_keeps_default_reasoning() -> None:
    overrides = build_model_request_overrides(
        execution_path="deep",
        tools=[_tool("crm_update_record"), _tool("crm_lookup")],
    )

    assert overrides == {}


def test_build_model_request_overrides_mixed_tool_turn_keeps_default_reasoning() -> (
    None
):
    assert (
        build_model_request_overrides(
            execution_path="deep",
            tools=[_tool("crm_update_record"), _tool("web_search")],
        )
        == {}
    )


def test_build_model_request_overrides_supports_openai_tool_dict_shape() -> None:
    overrides = build_model_request_overrides(
        execution_path="normal",
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "crm_open_record",
                    "parameters": {},
                },
            }
        ],
    )

    assert overrides == {}


def test_build_model_request_overrides_forces_responses_hosted_search_when_available() -> (
    None
):
    runtime_context = SimpleNamespace(
        provider=SimpleNamespace(
            type="openai_compatible",
            config={
                "wire_api": "chat_completions",
                "protocol_capabilities": {
                    "allowed_wire_apis": ["chat_completions", "responses"],
                },
                "web_search": {"enabled": True},
            },
        ),
        ai_model=SimpleNamespace(config={}),
        model_code="gpt-5.4-xhigh",
    )

    overrides = build_model_request_overrides(
        execution_path="normal",
        tools=[_tool("web_search"), _tool("fetch_url")],
        tool_use_policy=ToolUsePolicy(
            family="web_research",
            mode="required",
            allowed_tool_names=["web_search", "fetch_url"],
            retry_on_contract_breach=True,
            reason="native_web_search_first:web_research",
        ),
        runtime_context=runtime_context,
    )

    assert overrides == {
        "_runtime_force_protocol_path": "responses",
        "_runtime_hosted_web_search_required": True,
        "_runtime_hosted_web_search_context_size": "medium",
    }


def test_build_model_request_overrides_does_not_force_hosted_search_for_fetch_only_retry() -> (
    None
):
    runtime_context = SimpleNamespace(
        provider=SimpleNamespace(
            type="openai_compatible",
            config={
                "wire_api": "chat_completions",
                "protocol_capabilities": {
                    "allowed_wire_apis": ["chat_completions", "responses"],
                },
                "web_search": {"enabled": True},
            },
        ),
        ai_model=SimpleNamespace(config={}),
        model_code="gpt-5.4-xhigh",
    )

    overrides = build_model_request_overrides(
        execution_path="normal",
        tools=[_tool("fetch_url")],
        tool_use_policy=ToolUsePolicy(
            family="web_research",
            mode="required",
            allowed_tool_names=["fetch_url"],
            retry_on_contract_breach=True,
            reason="native_web_search_first:web_research",
        ),
        runtime_context=runtime_context,
    )

    assert overrides == {}


def test_build_model_request_overrides_keeps_builtin_fallback_when_native_unavailable() -> (
    None
):
    runtime_context = SimpleNamespace(
        provider=SimpleNamespace(
            type="openai_compatible",
            config={
                "wire_api": "chat_completions",
                "web_search": {"enabled": True},
            },
        ),
        ai_model=SimpleNamespace(config={}),
        model_code="gpt-5.4",
    )

    overrides = build_model_request_overrides(
        execution_path="normal",
        tools=[_tool("web_search"), _tool("fetch_url")],
        tool_use_policy=ToolUsePolicy(
            family="web_research",
            mode="required",
            allowed_tool_names=["web_search", "fetch_url"],
            retry_on_contract_breach=True,
            reason="native_web_search_first:web_research",
        ),
        runtime_context=runtime_context,
    )

    assert overrides == {}
