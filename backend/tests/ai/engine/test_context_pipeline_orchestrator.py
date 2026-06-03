"""Test type: behavioral
Scope: ContextPipelineOrchestrator intent flags and memory policy gating behavior
Real dependencies: ContextPipelineOrchestrator, resolve_memory_runtime_policy, intent_plan_gating_flags
Mocked dependencies: None
"""

from types import SimpleNamespace

from app.ai.context.orchestrator import ContextPipelineOrchestrator


def _intent(kind: str, *, shortcircuit: bool = False):
    return SimpleNamespace(kind=kind, shortcircuit=shortcircuit, family="none")


def _request(
    *,
    memory_enabled: bool = False,
    long_term_memory_enabled: bool = False,
    memory_runtime_policy: dict | None = None,
):
    return SimpleNamespace(
        user_id=7,
        memory_enabled=memory_enabled,
        long_term_memory_enabled=long_term_memory_enabled,
        memory_runtime_policy=memory_runtime_policy or {},
    )


def test_context_pipeline_orchestrator_enables_runtime_memory_for_generic_turns() -> (
    None
):
    flags = ContextPipelineOrchestrator.compute_intent_flags(
        [_intent("assistant_response", shortcircuit=False)],
        request=_request(memory_enabled=True, long_term_memory_enabled=True),
    )

    assert flags.has_memory_intent is False
    assert flags.memory_context_enabled is True
    assert flags.allow_memory_even_if_shortcircuit is False
    assert flags.session_memory_runtime_enabled is True
    assert flags.long_term_memory_runtime_enabled is True
    assert flags.should_run_memory_profile is False
    assert flags.should_run_memory_vector_recall is True


def test_context_pipeline_orchestrator_keeps_session_memory_without_long_term_recall() -> (
    None
):
    flags = ContextPipelineOrchestrator.compute_intent_flags(
        [_intent("assistant_response", shortcircuit=False)],
        request=_request(memory_enabled=True, long_term_memory_enabled=False),
    )

    assert flags.has_memory_intent is False
    assert flags.memory_context_enabled is True
    assert flags.allow_memory_even_if_shortcircuit is False
    assert flags.session_memory_runtime_enabled is True
    assert flags.long_term_memory_runtime_enabled is False
    assert flags.should_run_memory_profile is False
    assert flags.should_run_memory_vector_recall is False


def test_context_pipeline_orchestrator_runs_profile_and_recall_for_memory_recall() -> (
    None
):
    flags = ContextPipelineOrchestrator.compute_intent_flags(
        [_intent("memory_recall", shortcircuit=True)],
        request=_request(memory_enabled=True, long_term_memory_enabled=True),
    )

    assert flags.has_memory_intent is True
    assert flags.memory_context_enabled is True
    assert flags.has_memory_recall_intent is True
    assert flags.allow_memory_even_if_shortcircuit is True
    assert flags.should_run_memory_profile is True
    assert flags.should_run_memory_vector_recall is True


def test_context_pipeline_orchestrator_keeps_memory_save_write_only() -> None:
    flags = ContextPipelineOrchestrator.compute_intent_flags(
        [_intent("memory_save", shortcircuit=True)],
        request=_request(memory_enabled=True, long_term_memory_enabled=True),
    )

    assert flags.has_memory_intent is True
    assert flags.memory_context_enabled is True
    assert flags.has_memory_save_intent is True
    assert flags.should_run_memory_profile is False
    assert flags.should_run_memory_vector_recall is False
