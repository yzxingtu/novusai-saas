from types import SimpleNamespace

from app.ai.context.orchestrator import ContextPipelineOrchestrator
from app.ai.engine.system_prompt_intent_helpers import intent_plan_gating_flags
from app.ai.memory_policy import resolve_memory_runtime_policy


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


def test_context_pipeline_orchestrator_suppresses_long_term_recall_for_polluted_turns() -> (
    None
):
    request = _request(
        memory_enabled=False,
        long_term_memory_enabled=True,
        memory_runtime_policy={
            "external_context_polluted": True,
            "external_context_reason": "tool:web_search",
        },
    )
    flags = ContextPipelineOrchestrator.compute_intent_flags(
        [_intent("assistant_response", shortcircuit=False)],
        request=request,
    )
    policy = resolve_memory_runtime_policy(request)

    assert flags.long_term_memory_runtime_enabled is True
    assert flags.memory_context_enabled is False
    assert flags.should_run_memory_profile is False
    assert flags.should_run_memory_vector_recall is False
    assert policy.thread_memory_owner_state == "polluted"
    assert policy.long_term_memory_recall_state == "suppressed_external_context"
    assert policy.long_term_memory_capture_state == "suppressed_external_context"


def test_resolve_memory_runtime_policy_allows_clean_turn_to_clear_seeded_pollution() -> (
    None
):
    request = _request(
        memory_enabled=True,
        long_term_memory_enabled=True,
        memory_runtime_policy={
            "external_context_polluted": True,
            "external_context_reason": "tool:web_search",
        },
    )

    policy = resolve_memory_runtime_policy(
        request,
        result=SimpleNamespace(tool_results=[], intent_plan=[]),
    )

    assert policy.external_context_polluted is False
    assert policy.thread_memory_owner_state == "active"
    assert policy.long_term_memory_recall_state == "enabled"
    assert (
        policy.long_term_memory_capture_state == "disabled_missing_conversation_scope"
    )


def test_intent_plan_gating_flags_keeps_web_research_signal() -> None:
    flags = intent_plan_gating_flags(
        [_intent("web_research", shortcircuit=False)],
        request=_request(),
    )

    assert flags["has_web_research_intent"] is True
