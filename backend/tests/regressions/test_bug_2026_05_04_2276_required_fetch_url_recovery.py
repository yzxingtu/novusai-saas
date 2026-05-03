"""
Test type: behavioral
Regression for: BUG-2026-05-04-2276
Original symptom: required web research finalized raw web_search result titles
and Baidu redirect URLs as recovery_evidence while fetch_url was still missing.
Scope: recovery evidence qualification and read-time diagnostics projection.
Mock strategy: no LLM/provider/tool executor mocks; inputs are recorded-shaped
turn diagnostics and deterministic ToolResult evidence from conversation 2276.
"""

from __future__ import annotations

from app.ai.engine.recovery_manager import RecoveryManager
from app.ai.engine.types import IntentPlan
from app.ai.tools.types import ToolResult
from app.services.ai.turn_failure_normalizer import resolve_failure_projection


def _required_fetch_url_intent() -> IntentPlan:
    return IntentPlan(
        intent_id="intent-1",
        kind="web_research",
        family="web_research",
        order=1,
        user_visible_label="web_research",
        source_text="帮我搜索一下2025年大模型使用token排行 可以吗？",
        status="pending",
        requires_tools=True,
        allowed_tool_names=["fetch_url"],
        completion_signals=["fetch_url"],
        metadata={
            "requires_fetch_url": True,
            "auto_fetch_gate_reason": "candidate_urls_ready",
            "fetch_url_candidate_urls": [
                "http://www.baidu.com/link?url=example-token-ranking"
            ],
        },
    )


def _search_only_result() -> ToolResult:
    return ToolResult(
        tool_call_id="call-search",
        name="web_search",
        success=True,
        summary="baidu_public: 1 result(s)",
        summary_payload={
            "status": "success",
            "result_count": 1,
            "items": [
                {
                    "title": "日耗37万亿 Tokens ,千问稳居第一",
                    "url": "http://www.baidu.com/link?url=example-token-ranking",
                    "snippet": "沙利文报告显示，中国企业级大模型日均调用量为37万亿Tokens。",
                }
            ],
        },
    )


def test_bug_2026_05_04_2276_does_not_promote_search_only_recovery() -> None:
    recovered_intents, recovered_output = (
        RecoveryManager.recover_web_search_output_from_evidence(
            [_required_fetch_url_intent()],
            tool_results=[_search_only_result()],
            reason="retry_budget_exhausted",
        )
    )

    assert recovered_output == ""
    assert recovered_intents[0].status == "pending"
    assert recovered_intents[0].completed_by_tool_names == []
    assert recovered_intents[0].metadata["requires_fetch_url"] is True


def test_bug_2026_05_04_2276_projects_historical_raw_recovery_as_failed() -> None:
    projection = resolve_failure_projection(
        diagnostics={
            "turn_outcome": "success",
            "conversation_outcome": "success",
            "termination_reason": "protocol_fallback",
            "failure_kind": "provider_timeout",
            "final_output_source": "recovery_evidence",
            "selected_tool_names": ["web_search", "fetch_url"],
            "candidate_tool_names": ["web_search", "fetch_url"],
            "intent_plan": [
                {
                    "intent_id": "intent-1",
                    "kind": "web_research",
                    "family": "web_research",
                    "status": "completed",
                    "allowed_tool_names": ["fetch_url"],
                    "completed_by_tool_names": ["web_search"],
                }
            ],
            "retry_events": [
                {
                    "action": "retry_intent",
                    "target_intent_id": "intent-1",
                    "allowed_tool_names": ["fetch_url"],
                    "unfinished_intent_ids": ["intent-1"],
                }
            ],
            "fallback_history": [
                {
                    "from_protocol": "responses",
                    "to_protocol": "responses",
                    "reason": "hosted_web_search_unavailable:provider_timeout",
                    "recovered": True,
                }
            ],
        }
    )

    assert projection["turn_outcome"] == "failed"
    assert projection["conversation_outcome"] == "failed"
    assert projection["failure_kind"] == "raw_search_only_recovery_finalized"
    assert projection["missing_required_tool_names"] == ["fetch_url"]
    assert projection["authoritative_completed_success"] is False
