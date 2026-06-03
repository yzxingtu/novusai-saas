"""
Test type: structural
Scope: model request override policy for text, tool, and web-research turns.
Mocked dependencies: local runtime-context namespaces only; policy code runs real.
"""

from __future__ import annotations

from app.ai.engine.model_policy import build_model_request_overrides
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
