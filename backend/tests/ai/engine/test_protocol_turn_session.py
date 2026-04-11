from __future__ import annotations

from app.ai.runtime.contracts import ProtocolExecutionPlan
from app.ai.runtime.protocol_turn_session import ProtocolTurnSession
from app.ai.runtime.types import TurnRecord
from app.ai.types import ChatMessage, ChatResponse


class _PlannerStub:
    def __init__(self, plan: ProtocolExecutionPlan) -> None:
        self.plan = plan

    def plan_turn(self, *, tools, selected_skill_names=None, context_sources=None):
        _ = tools, selected_skill_names, context_sources
        return self.plan


def test_protocol_turn_session_create_initializes_turn_record() -> None:
    session = ProtocolTurnSession.create(
        planner=_PlannerStub(
            ProtocolExecutionPlan(
                preferred_protocol="responses",
                protocol_chain=["responses", "chat_completions"],
                selected_tool_names=["web_search"],
                selected_skill_names=["search"],
                context_sources=[],
            )
        ),
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4",
        temperature=0.7,
        max_tokens=None,
        top_p=1.0,
        tools=[{"type": "function", "function": {"name": "web_search"}}],
        tool_choice="auto",
        supports_vision=True,
        supports_audio=False,
        supports_video=False,
        selected_skill_names=["search"],
        context_sources=[],
        extra_kwargs={"timeout_seconds": 20},
    )

    assert session.command.model == "gpt-5.4"
    assert session.plan.protocol_chain == ["responses", "chat_completions"]
    assert session.turn_record.protocol_path == "responses"
    assert session.turn_record.selected_tool_names == ["web_search"]
    assert session.turn_record.selected_skill_names == ["search"]


def test_protocol_turn_session_append_fallback_uses_next_protocol() -> None:
    session = ProtocolTurnSession(
        command=None,  # type: ignore[arg-type]
        plan=ProtocolExecutionPlan(
            preferred_protocol="responses",
            protocol_chain=["responses", "chat_completions"],
        ),
        turn_record=TurnRecord(),
    )

    appended = session.append_fallback(
        0,
        from_protocol="responses",
        reason="stream_empty_no_output",
    )

    assert appended is True
    assert session.turn_record.fallback_history[0].from_protocol == "responses"
    assert session.turn_record.fallback_history[0].to_protocol == "chat_completions"
    assert session.turn_record.fallback_history[0].reason == "stream_empty_no_output"


def test_protocol_turn_session_finalize_sync_rescue_success_marks_recovery() -> None:
    session = ProtocolTurnSession(
        command=None,  # type: ignore[arg-type]
        plan=ProtocolExecutionPlan(
            preferred_protocol="responses",
            protocol_chain=["responses", "chat_completions"],
        ),
        turn_record=TurnRecord(),
    )
    session.append_fallback(
        0,
        from_protocol="responses",
        reason="stream_progress_only_no_meaningful_output",
    )

    session.finalize_sync_rescue_success(emitted_chunk_count=1)

    assert session.turn_record.turn_outcome == "success"
    assert session.turn_record.termination_reason == "protocol_fallback"
    assert session.turn_record.metadata["sync_rescue"] is True
    assert session.turn_record.metadata["stream_chunk_count"] == 2
    assert session.turn_record.fallback_history[0].recovered is True
    assert (
        session.turn_record.fallback_history[0].metadata["recovery_path"]
        == "sync_chat_completions"
    )


def test_protocol_turn_session_finalize_chat_success_attaches_turn_record() -> None:
    session = ProtocolTurnSession(
        command=None,  # type: ignore[arg-type]
        plan=ProtocolExecutionPlan(
            preferred_protocol="responses",
            protocol_chain=["responses"],
        ),
        turn_record=TurnRecord(),
    )
    response = ChatResponse(
        message=ChatMessage(role="assistant", content="done"),
        finish_reason="stop",
        model="gpt-5.4",
    )

    finalized = session.finalize_chat_success(response)

    assert finalized.metadata["runtime_turn_record"] is session.turn_record
    assert session.turn_record.turn_outcome == "success"
    assert session.turn_record.termination_reason == "completed"
