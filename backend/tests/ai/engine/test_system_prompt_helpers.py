from __future__ import annotations

from app.ai.engine.base import BaseEngine
from app.ai.engine.budget_helpers import budget_exit_response
from app.ai.engine.contract_diagnostics_helpers import (
    build_contract_recovery_system_message,
    merge_contract_diagnostics_into_turn_record,
)
from app.ai.engine.system_prompt_helpers import (
    build_system_message,
    inject_runtime_summary,
    is_capability_reporting_query,
)
from app.ai.engine.types import ExecutionBudget, IntentPlan
from app.ai.runtime.types import TurnRecord
from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage


def _sample_budget() -> ExecutionBudget:
    return ExecutionBudget(
        max_prompt_tokens=2000,
        max_completion_tokens=800,
        max_tool_rounds=4,
        max_elapsed_ms=20000,
        max_retry_per_intent=1,
        max_candidate_tools=8,
        max_tool_result_bytes=16000,
    )


def test_build_system_message_renders_identity_and_variables() -> None:
    class _Agent:
        id = 123
        name = "KernelTestAgent"
        system_prompt = "Locale={{ locale }} Agent={{ agent_name }}"

    message = build_system_message(
        agent=_Agent(),
        input_variables={"locale": "zh-CN"},
    )
    assert message.role == "system"
    assert "KernelTestAgent" in message.content
    assert "Locale=zh-CN" in message.content


def test_base_engine_build_system_message_keeps_positional_facade() -> None:
    class _Agent:
        id = 456
        name = "FacadeAgent"
        system_prompt = "Locale={{ locale }} Agent={{ agent_name }}"

    message = BaseEngine._build_system_message(_Agent(), {"locale": "en-US"})

    assert message.role == "system"
    assert "FacadeAgent" in message.content
    assert "Locale=en-US" in message.content


def test_inject_runtime_summary_is_idempotent_for_same_signature() -> None:
    messages = [ChatMessage(role="system", content="SYS")]
    tools = [ToolDefinition(name="web_search")]
    intents = [
        IntentPlan(
            intent_id="intent-1",
            kind="web_research",
            family="web_research",
            order=1,
            user_visible_label="web_research",
            source_text="latest ai news",
        )
    ]

    injected_first = inject_runtime_summary(
        messages=messages,
        tools=tools,
        intent_plan=intents,
        execution_path="normal",
        execution_budget=_sample_budget(),
    )
    first_content = messages[0].content
    first_signature = (messages[0].metadata or {}).get("runtime_summary_signature")

    injected_second = inject_runtime_summary(
        messages=messages,
        tools=tools,
        intent_plan=intents,
        execution_path="normal",
        execution_budget=_sample_budget(),
    )

    assert injected_first is False
    assert injected_second is False
    assert messages[0].content == first_content
    assert (messages[0].metadata or {}).get("runtime_summary_signature") == first_signature


def test_contract_diagnostics_helpers_populate_turn_record_metadata() -> None:
    turn_record = TurnRecord()
    merged = merge_contract_diagnostics_into_turn_record(
        turn_record,
        breach_type="assistant_claimed_tool_call_without_tool_event",
        diagnostics={
            "tool_leak_detected": True,
            "assistant_claimed_tool_call_without_tool_event": True,
            "unfinished_intents": ["web_research"],
            "leaked_tool_names": ["fetch_url"],
        },
        recovered_via_retry=True,
    )
    assert isinstance(merged, TurnRecord)
    assert merged.metadata["contract_breach_type"] == "assistant_claimed_tool_call_without_tool_event"
    assert merged.metadata["tool_leak_detected"] is True
    assert merged.metadata["recovered_via_retry"] is True
    assert merged.metadata["leaked_tool_names"] == ["fetch_url"]


def test_base_engine_wrappers_delegate_to_extracted_helpers() -> None:
    message = build_contract_recovery_system_message(
        breach_type="assistant_claimed_tool_call_without_tool_event",
        diagnostics={
            "unfinished_intents": ["web_research"],
            "completed_intents": [],
            "leaked_tool_names": ["web_search"],
        },
    )
    assert message.role == "system"
    assert BaseEngine._is_capability_reporting_query("你能做什么")
    assert is_capability_reporting_query("what can you do this turn")
    assert BaseEngine._intent_completion_signals(
        "web_research",
        allowed_tool_names=["fetch_url", "web_search"],
        preferred_tool_names=[],
    ) == ["fetch_url"]
    response = BaseEngine._budget_exit_response(total_tokens=42)
    helper_response = budget_exit_response(total_tokens=42)
    assert response.total_tokens == 42
    assert response.message.role == "assistant"
    assert helper_response.message.content == ""
