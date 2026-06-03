"""
Test type: structural
中文: 覆盖 AI runtime helper 所有权与退役 import 面哨兵。
EN: Covers AI runtime helper ownership and retired import-surface sentinels.
Mock strategy: no runtime decision mocks; tests inspect import surfaces and pure
helpers.
"""

from __future__ import annotations

from importlib import import_module
from importlib.util import find_spec
from types import SimpleNamespace

from app.ai.engine.prepare_execution_runtime_helpers import (
    apply_runtime_capability_injection,
)
from app.ai.engine.tool_policy_selection_helpers import (
    allowed_tool_names_for_family,
    filter_tools_for_policy,
    restrict_tools_to_names,
)
from app.ai.tools.types import ToolDefinition


def test_apply_runtime_capability_injection_updates_diagnostics() -> None:
    diagnostics: dict[str, object] = {}
    injected_calls: list[dict[str, object]] = []

    decision = apply_runtime_capability_injection(
        diagnostics=diagnostics,
        intent_flags={
            "has_knowledge_intent": True,
            "has_page_intent": False,
            "has_memory_intent": True,
            "memory_context_enabled": True,
        },
        force_capability_summary=True,
        context_sources=[{"kind": "memory", "name": "profile"}],
        tools=[SimpleNamespace(name="save_memory")],
        runtime_capability_summary={"tool_count": 1},
        ordered_requested_families=["memory"],
        intent_plan=[],
        execution_path="normal",
        should_skip_capability_summary=lambda **_: False,
        inject_runtime_summary=lambda **kwargs: injected_calls.append(kwargs) or True,
        resolve_capability_injection_decision=lambda **kwargs: {
            "source_count": len(kwargs["context_sources"] or []),
            "capability_summary_injected": kwargs["capability_summary_injected"],
        },
    )

    assert diagnostics["capability_reporting_query"] is True
    assert diagnostics["capability_injection_decision"] == decision
    assert decision["source_count"] == 1
    assert decision["capability_summary_injected"] is True
    assert injected_calls[0]["tools"][0].name == "save_memory"
    assert injected_calls[0]["execution_path"] == "normal"
    assert "include_knowledge_base_hint" not in injected_calls[0]
    assert "include_memory_hint" not in injected_calls[0]


def test_tool_policy_family_selection_fails_closed_on_unknown_family() -> None:
    """Test type: behavioral; unknown skill family must not widen to all tools."""
    tools = [
        ToolDefinition(name="clock_now", description="Current time"),
        ToolDefinition(name="weather_lookup", description="Plugin weather"),
    ]

    assert allowed_tool_names_for_family("missing_family", tools) == []
    assert restrict_tools_to_names(tools, []) == []
    assert restrict_tools_to_names(tools, None) == tools
    assert (
        filter_tools_for_policy(
            tools,
            SimpleNamespace(
                family="weather",
                mode="required",
                allowed_tool_names=[],
            ),
        )
        == []
    )


def test_usage_metrics_uses_runtime_owner_module_only() -> None:
    runtime_module = import_module("app.ai.runtime.usage_metrics")

    assert find_spec("app.services.ai.usage_metrics") is None
    assert runtime_module.TokenCounter.__module__ == "app.ai.runtime.usage_metrics"
    assert runtime_module.CostCalculator.__module__ == "app.ai.runtime.usage_metrics"


def test_retired_ai_legacy_import_surfaces_are_not_resolvable() -> None:
    retired_modules = [
        "app.ai.agent_quota",
        "app.ai.engine.conversation_runtime_accounting",
        "app.ai.quota",
        "app.ai.usage_recorder",
        "app.ai.adapters.openai_compatible.usage_parser",
        "app.ai.adapters.openai_compatible.support.multimodal_runtime",
        "app.ai.adapters.openai_compatible.support.usage_parser",
        "app.cli_commands.legacy",
        "app.services.ai.recovery_evidence_read_model",
        "app.services.ai.usage_metrics",
    ]

    assert {module: find_spec(module) for module in retired_modules} == dict.fromkeys(
        retired_modules,
        None,
    )


def test_ai_service_package_does_not_export_retired_metrics_facade() -> None:
    services_ai = import_module("app.services.ai")

    assert "UsageMetrics" not in services_ai.__all__
    assert "TokenCounter" not in services_ai.__all__
    assert "CostCalculator" not in services_ai.__all__
