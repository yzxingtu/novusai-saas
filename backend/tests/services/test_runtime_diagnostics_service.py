"""Runtime diagnostics service unit tests / 运行时诊断服务单元测试。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.enums.ai import CallStatusEnum


def _call_log(
    *,
    status: str = CallStatusEnum.SUCCESS.value,
    request_metadata: dict | None = None,
):
    return SimpleNamespace(
        id=501,
        trace_id="trace-1",
        conversation_id=1062,
        agent_id=9,
        provider_id=3,
        model_id=4,
        status=status,
        error_message=None,
        request_metadata=request_metadata or {},
    )


@pytest.mark.asyncio
async def test_build_root_cause_prefers_conversation_partial_over_successful_call_log(
    mock_db,
):
    from app.services.ai.runtime_diagnostics_service import RuntimeDiagnosticsService

    service = RuntimeDiagnosticsService(mock_db)
    conversation_turn = {
        "message_id": 77,
        "diagnostics": {
            "conversation_outcome": "partial",
            "tool_planner": {
                "intent": "web_research",
                "family": "web_research",
            },
            "unfinished_intents": ["web_research"],
            "candidate_tool_names": ["web_search", "fetch_url"],
            "selected_tool_names": ["web_search"],
        },
    }
    call_log = _call_log(
        request_metadata={
            "turn_diagnostics": {
                "turn_outcome": "success",
                "tool_planner": {
                    "intent": "web_research",
                    "family": "web_research",
                },
                "selected_tool_names": ["web_search", "fetch_url"],
            }
        }
    )

    with (
        patch.object(
            service,
            "_resolve_conversation_turn",
            new=AsyncMock(return_value=conversation_turn),
        ),
        patch.object(
            service,
            "_resolve_related_call_log_for_conversation_turn",
            new=AsyncMock(return_value=call_log),
        ),
    ):
        report = await service.build_root_cause(conversation_id=1062, turn=1)

    assert report["status"] == "failed"
    assert report["failure_layer"] == "research_contract"
    assert report["cause_code"] == "research_partial_finalized_by_orchestrator"
    assert report["related_ids"]["conversation_message_id"] == 77


def test_classify_root_cause_marks_page_continuation_false_direct_reply(mock_db):
    from app.services.ai.runtime_diagnostics_service import RuntimeDiagnosticsService

    service = RuntimeDiagnosticsService(mock_db)
    failure_layer, cause_code, summary, first_fix, confidence = (
        service._classify_root_cause(
            call_log=_call_log(),
            diagnostics={
                "conversation_outcome": "failed",
                "continuation_source": "page_ops",
                "tool_planner": {
                    "intent": "direct_reply",
                    "family": "none",
                },
                "candidate_tool_names": ["get_page_context"],
            },
            conversation_turn={"message_id": 91},
        )
    )

    assert failure_layer == "post_processing"
    assert cause_code == "planner_false_direct_reply"
    assert "direct_reply" in summary
    assert first_fix is not None
    assert confidence == 0.94


def test_classify_root_cause_marks_time_query_false_direct_reply(mock_db):
    from app.services.ai.runtime_diagnostics_service import RuntimeDiagnosticsService

    service = RuntimeDiagnosticsService(mock_db)
    failure_layer, cause_code, summary, first_fix, confidence = (
        service._classify_root_cause(
            call_log=_call_log(),
            diagnostics={
                "conversation_outcome": "success",
                "tool_planner": {
                    "intent": "direct_reply",
                    "family": "none",
                    "intent_plan": [
                        {
                            "intent_id": "intent-1",
                            "kind": "direct_reply",
                            "family": "none",
                            "source_text": "现在是几点",
                            "status": "completed",
                        }
                    ],
                },
                "selected_tool_names": [],
                "candidate_tool_names": [],
                "selected_skill_names": ["get_current_time", "web_search"],
            },
            conversation_turn={"message_id": 109},
        )
    )

    assert failure_layer == "post_processing"
    assert cause_code == "planner_false_direct_reply"
    assert "direct_reply" in summary
    assert first_fix is not None
    assert confidence == 0.93


@pytest.mark.asyncio
async def test_build_root_cause_reports_fake_tool_call_contract_breach(mock_db):
    from app.services.ai.runtime_diagnostics_service import RuntimeDiagnosticsService

    service = RuntimeDiagnosticsService(mock_db)
    conversation_turn = {
        "message_id": 88,
        "diagnostics": {
            "conversation_outcome": "failed",
            "continuation_source": "page_ops",
            "tool_planner": {
                "intent": "direct_reply",
                "family": "none",
            },
            "candidate_tool_names": ["get_page_context"],
            "assistant_claimed_tool_call_without_tool_event": True,
            "contract_breach_type": "assistant_claimed_tool_call_without_tool_event",
        },
    }

    with (
        patch.object(
            service,
            "_resolve_conversation_turn",
            new=AsyncMock(return_value=conversation_turn),
        ),
        patch.object(
            service,
            "_resolve_related_call_log_for_conversation_turn",
            new=AsyncMock(return_value=_call_log()),
        ),
    ):
        report = await service.build_root_cause(conversation_id=1064, turn=1)

    assert report["status"] == "failed"
    assert report["failure_layer"] == "stream_output_contract"
    assert report["cause_code"] == "assistant_claimed_tool_call_without_tool_event"
    assert report["related_ids"]["conversation_message_id"] == 88


@pytest.mark.asyncio
async def test_resolve_conversation_turn_prefers_turn_anchor_assistant_message(mock_db):
    from app.enums.agent import MessageRoleEnum
    from app.services.ai.runtime_diagnostics_service import RuntimeDiagnosticsService

    service = RuntimeDiagnosticsService(mock_db)
    conversation = SimpleNamespace(id=1067)
    messages = [
        SimpleNamespace(
            id=6401,
            role=MessageRoleEnum.USER.value,
            content="联网查一下今日AI 最新要闻",
            metadata_={},
            tool_calls=[],
        ),
        SimpleNamespace(
            id=6410,
            role=MessageRoleEnum.ASSISTANT.value,
            content="先搜索一下",
            metadata_={},
            tool_calls=[{"id": "call-1"}],
        ),
        SimpleNamespace(
            id=6420,
            role=MessageRoleEnum.ASSISTANT.value,
            content="这次搜索没有完成。",
            metadata_={
                "turn_record": {
                    "turn_outcome": "partial",
                    "termination_reason": "retry_budget_exhausted",
                },
                "last_run_summary": {
                    "conversation_outcome": "partial",
                    "failure_kind": "tool_execution_error",
                    "selected_tool_names": ["web_search", "fetch_url"],
                    "unfinished_intents": ["intent-1"],
                },
            },
            tool_calls=[],
        ),
    ]
    message_repo = SimpleNamespace(get_by_conversation=AsyncMock(return_value=messages))
    conversation_service = SimpleNamespace(message_repo=message_repo)

    with patch.object(
        service_module := __import__(
            "app.services.ai.runtime_diagnostics_service",
            fromlist=["ConversationService"],
        ).ConversationService,
        "get_service_for_conversation",
        new=AsyncMock(return_value=(conversation_service, conversation)),
    ):
        resolved = await service._resolve_conversation_turn(
            conversation_id=1067,
            turn=1,
        )

    assert resolved["message_id"] == 6420
    assert resolved["diagnostics"]["conversation_outcome"] == "partial"
    assert resolved["diagnostics"]["termination_reason"] == "retry_budget_exhausted"
