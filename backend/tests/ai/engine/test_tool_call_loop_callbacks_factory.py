from app.ai.engine.tool_call_loop_callbacks_factory import (
    build_tool_call_loop_callbacks,
)
from app.ai.engine.tool_call_loop_policy import ToolCallLoopPolicy
from app.ai.engine.types import ToolUsePolicy
from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage, ChatResponse


def test_build_tool_call_loop_callbacks_keeps_callables() -> None:
    def _ordered_requested_families_from_intents(**_kwargs):
        return ["time"]

    def _truncate_tool_calls_after_navigation(tool_calls):
        return tool_calls, False

    def _mark_multi_family_progress(**_kwargs):
        return None

    def _budget_exit_response(total_tokens: int) -> ChatResponse:
        return ChatResponse(
            message=ChatMessage(role="assistant", content=str(total_tokens)),
            total_tokens=total_tokens,
        )

    def _build_page_no_progress_recovery(**_kwargs):
        return None, [], {}

    def _messages_have_blocking_pending_interaction(_messages):
        return False

    def _first_incomplete_requested_family(_ordered, _completed):
        return None

    def _allowed_tool_names_for_family(_family, _tools, _input):
        return []

    def _build_ordered_capability_hint(_families, _tools, _input):
        return None

    def _needs_fetch_url_before_summary(_messages):
        return False

    def _apply_fetch_url_only_gate(_messages, tools, _all_tools):
        return tools

    def _restrict_tools_to_names(tools, _allowed):
        return tools

    async def _call_followup_llm(_tools: list[ToolDefinition], _policy: ToolUsePolicy):
        return ChatResponse(message=ChatMessage(role="assistant", content="ok"))

    policy = ToolCallLoopPolicy(
        build_page_no_progress_recovery=_build_page_no_progress_recovery,
        messages_have_blocking_pending_interaction=_messages_have_blocking_pending_interaction,
        first_incomplete_requested_family=_first_incomplete_requested_family,
        allowed_tool_names_for_family=_allowed_tool_names_for_family,
        build_ordered_capability_hint=_build_ordered_capability_hint,
        needs_fetch_url_before_summary=_needs_fetch_url_before_summary,
        apply_fetch_url_only_gate=_apply_fetch_url_only_gate,
        restrict_tools_to_names=_restrict_tools_to_names,
    )

    callbacks = build_tool_call_loop_callbacks(
        policy=policy,
        ordered_requested_families_from_intents=_ordered_requested_families_from_intents,
        truncate_tool_calls_after_navigation=_truncate_tool_calls_after_navigation,
        mark_multi_family_progress=_mark_multi_family_progress,
        budget_exit_response=_budget_exit_response,
        call_followup_llm=_call_followup_llm,
    )

    assert (
        callbacks.ordered_requested_families_from_intents
        is _ordered_requested_families_from_intents
    )
    assert (
        callbacks.truncate_tool_calls_after_navigation
        is _truncate_tool_calls_after_navigation
    )
    assert callbacks.mark_multi_family_progress is _mark_multi_family_progress
    assert callbacks.budget_exit_response is _budget_exit_response
    assert callbacks.build_page_no_progress_recovery is _build_page_no_progress_recovery
    assert (
        callbacks.messages_have_blocking_pending_interaction
        is _messages_have_blocking_pending_interaction
    )
    assert (
        callbacks.first_incomplete_requested_family is _first_incomplete_requested_family
    )
    assert callbacks.allowed_tool_names_for_family is _allowed_tool_names_for_family
    assert callbacks.build_ordered_capability_hint is _build_ordered_capability_hint
    assert callbacks.needs_fetch_url_before_summary is _needs_fetch_url_before_summary
    assert callbacks.apply_fetch_url_only_gate is _apply_fetch_url_only_gate
    assert callbacks.restrict_tools_to_names is _restrict_tools_to_names
    assert callbacks.call_followup_llm is _call_followup_llm
