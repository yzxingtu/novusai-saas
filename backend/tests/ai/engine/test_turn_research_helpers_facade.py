from app.ai.engine import (
    turn_research_continuation,
    turn_research_evidence,
    turn_research_extraction,
    turn_research_gating,
    turn_research_helpers,
)


def test_turn_research_helpers_exports_companion_helpers() -> None:
    assert (
        turn_research_helpers.collect_web_research_evidence
        is turn_research_evidence.collect_web_research_evidence
    )
    assert (
        turn_research_helpers.extract_recent_successful_tool_names
        is turn_research_evidence.extract_recent_successful_tool_names
    )
    assert (
        turn_research_helpers.needs_fetch_url_before_summary
        is turn_research_gating.needs_fetch_url_before_summary
    )
    assert (
        turn_research_helpers.build_web_research_continuation_context
        is turn_research_continuation.build_web_research_continuation_context
    )
    assert (
        turn_research_helpers.extract_fetch_title_from_output
        is turn_research_extraction.extract_fetch_title_from_output
    )
