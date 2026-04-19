from __future__ import annotations

from contextlib import ExitStack, contextmanager
from importlib import import_module
from importlib.util import find_spec
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.ai.engine.prepare_execution_runtime_helpers import (
    apply_runtime_capability_injection,
    resolve_runtime_execution_state,
)
from app.ai.types import ChatMessage

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
        raise AssertionError(
            "usage_metrics module not found at expected import paths"
        )
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
        input_variables={"locale": "zh-CN"},
        continuation_context=None,
        runtime_capability_summary={"tool_count": 1},
        ordered_requested_families=["memory"],
        intent_plan=[],
        execution_path="normal",
        execution_budget=None,
        should_skip_capability_summary=lambda **_: False,
        inject_runtime_summary=lambda *_args, **kwargs: injected_calls.append(kwargs)
        or True,
        resolve_capability_injection_decision=lambda **kwargs: {
            "source_count": len(kwargs["context_sources"] or []),
            "capability_summary_injected": kwargs["capability_summary_injected"],
        },
    )

    assert diagnostics["capability_reporting_query"] is True
    assert diagnostics["capability_injection_decision"] == decision
    assert decision["source_count"] == 1
    assert decision["capability_summary_injected"] is True
    assert injected_calls[0]["include_knowledge_base_hint"] is True
    assert injected_calls[0]["include_memory_hint"] is True


def test_usage_metrics_import_paths_are_compatible() -> None:
    modules = _resolve_usage_metrics_modules()
    legacy_module = modules.get("app.services.ai.usage_metrics")
    runtime_module = modules.get("app.ai.runtime.usage_metrics")

    assert legacy_module is not None
    if runtime_module is None:
        return

    assert runtime_module.TokenCounter is legacy_module.TokenCounter
    assert runtime_module.CostCalculator is legacy_module.CostCalculator


@pytest.mark.asyncio
async def test_resolve_runtime_execution_state_filters_consent_and_injects_runtime_caps() -> None:
    request = SimpleNamespace(
        input_variables={"page_key": "users.list"},
        trust_policy_ref={"mode": "trusted_auto"},
        interaction_mode="trusted_auto",
    )
    sandbox = SimpleNamespace(input_variables={"existing": True})
    tools = [SimpleNamespace(name="fetch_url")]
    skill_result = SimpleNamespace(
        tool_consent_modes={"fetch_url": "confirm", "unused": "confirm"}
    )
    route_result = SimpleNamespace(is_overridden=True, model_id=7)
    routed_model = SimpleNamespace(
        supports_audio=True,
        supports_video=False,
        supports_vision=True,
    )

    with (
        patch(
            "app.ai.routing.router.ModelRouter.route",
            new=AsyncMock(return_value=route_result),
        ),
        _patch_usage_metrics_attr(
            "TokenCounter.count_messages_tokens",
            return_value=88,
        ),
        patch(
            "app.repositories.ai.model_repository.AIModelRepository.get_active_with_provider",
            new=AsyncMock(return_value=routed_model),
        ),
    ):
        state = await resolve_runtime_execution_state(
            db=object(),
            agent=SimpleNamespace(model=None),
            request=request,
            tools=tools,
            skill_result=skill_result,
            messages=[ChatMessage(role="user", content="hello")],
            sandbox=sandbox,
            apply_execution_trust_policy=lambda **kwargs: {
                **kwargs["tool_consent_modes"],
                "fetch_url": "trusted_auto",
            },
        )

    assert state.route_result is route_result
    assert state.tool_consent_modes == {"fetch_url": "trusted_auto"}
    assert state.runtime_model_capabilities == {
        "supports_audio": True,
        "supports_video": False,
        "supports_vision": True,
    }
    assert request.input_variables["runtime_model_capabilities"]["supports_vision"] is True
    assert sandbox.input_variables["runtime_model_capabilities"]["supports_audio"] is True
