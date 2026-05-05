from __future__ import annotations

from contextlib import ExitStack, contextmanager
from importlib import import_module
from importlib.util import find_spec
from types import SimpleNamespace
from unittest.mock import patch

from app.ai.engine.prepare_execution_runtime_helpers import (
    apply_runtime_capability_injection,
)

_USAGE_METRICS_MODULES = (
    "app.ai.runtime.usage_metrics",
    "app.services.ai.usage_metrics",
)


def _resolve_usage_metrics_modules() -> dict[str, object]:
    modules: dict[str, object] = {}
    for module_path in _USAGE_METRICS_MODULES:
        if find_spec(module_path) is None:
            continue
        modules[module_path] = import_module(module_path)
    return modules


@contextmanager
def _patch_usage_metrics_attr(attr_path: str, **kwargs):
    module_paths = [
        module_path
        for module_path in _USAGE_METRICS_MODULES
        if find_spec(module_path) is not None
    ]
    if not module_paths:
        raise AssertionError("usage_metrics module not found at expected import paths")
    with ExitStack() as stack:
        for module_path in module_paths:
            stack.enter_context(patch(f"{module_path}.{attr_path}", **kwargs))
        yield


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


def test_usage_metrics_import_paths_are_compatible() -> None:
    modules = _resolve_usage_metrics_modules()
    legacy_module = modules.get("app.services.ai.usage_metrics")
    runtime_module = modules.get("app.ai.runtime.usage_metrics")

    assert legacy_module is not None
    if runtime_module is None:
        return

    assert runtime_module.TokenCounter is legacy_module.TokenCounter
    assert runtime_module.CostCalculator is legacy_module.CostCalculator
