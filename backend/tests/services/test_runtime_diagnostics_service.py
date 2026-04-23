"""Test type: behavioral
Scope: runtime diagnostics root-cause classification and page-workflow evidence normalization
Real dependencies: RuntimeDiagnosticsService root-cause projector and page-workflow diagnostics helpers
Mocked dependencies: call-log and conversation-turn loaders only
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.enums.ai import CallStatusEnum


def _call_log(
    *,
    status: str = CallStatusEnum.SUCCESS.value,
    request_metadata: dict | None = None,
    error_message: str | None = None,
):
    return SimpleNamespace(
        id=501,
        trace_id="trace-1",
        conversation_id=1062,
        agent_id=9,
        provider_id=3,
        model_id=4,
        status=status,
        error_message=error_message,
        request_metadata=request_metadata or {},
    )


def test_runtime_diagnostics_query_groups_same_trace_logs_into_one_turn() -> None:
    from app.services.ai.runtime_diagnostics_query_service import (
        RuntimeDiagnosticsQueryService,
    )

    logs = [
        SimpleNamespace(id=3661, trace_id="trace-a"),
        SimpleNamespace(id=3662, trace_id="trace-b"),
        SimpleNamespace(id=3663, trace_id="trace-b"),
        SimpleNamespace(id=3664, trace_id="trace-c"),
        SimpleNamespace(id=3665, trace_id="trace-c"),
        SimpleNamespace(id=3666, trace_id=None),
    ]

    groups = RuntimeDiagnosticsQueryService._group_logs_by_turn(logs)

    assert [[item.id for item in group] for group in groups] == [
        [3661],
        [3662, 3663],
        [3664, 3665],
        [3666],
    ]


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
                "candidate_tool_names": ["ui_get_snapshot"],
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


def test_classify_root_cause_marks_page_continuation_miss_from_page_workflow_metadata(
    mock_db,
):
    from app.services.ai.runtime_diagnostics_service import RuntimeDiagnosticsService

    service = RuntimeDiagnosticsService(mock_db)
    failure_layer, cause_code, summary, first_fix, confidence = (
        service._classify_root_cause(
            call_log=_call_log(),
            diagnostics={
                "conversation_outcome": "failed",
                "continuation_source": "page_ops",
                "tool_planner": {
                    "intent": "page_workflow",
                    "family": "page_ops",
                },
                "intent_plan": [
                    {
                        "intent_id": "intent-1",
                        "kind": "page_workflow",
                        "family": "page_ops",
                        "status": "pending",
                        "metadata": {
                            "page_workflow_kind": "page_workflow",
                            "page_workflow_goal": "search",
                            "page_workflow_phase": "read",
                            "page_workflow_stage": "run_page_search",
                        },
                    }
                ],
                "selected_tool_names": [],
            },
            conversation_turn={"message_id": 115},
        )
    )

    assert failure_layer == "post_processing"
    assert cause_code == "page_continuation_missed"
    assert "page_ops family" in summary
    assert first_fix is not None
    assert confidence == 0.9


def test_classify_root_cause_skips_summary_like_page_workflow_missed_continuation(
    mock_db,
):
    from app.services.ai.runtime_diagnostics_service import RuntimeDiagnosticsService

    service = RuntimeDiagnosticsService(mock_db)
    _failure_layer, cause_code, _summary, _first_fix, _confidence = (
        service._classify_root_cause(
            call_log=_call_log(),
            diagnostics={
                "conversation_outcome": "failed",
                "continuation_source": "page_ops",
                "tool_planner": {
                    "intent": "page_workflow",
                    "family": "page_ops",
                },
                "intent_plan": [
                    {
                        "intent_id": "intent-1",
                        "kind": "page_workflow",
                        "family": "page_ops",
                        "status": "pending",
                        "metadata": {
                            "page_workflow_kind": "page_workflow",
                            "page_workflow_goal": "table_summary",
                            "page_workflow_phase": "read",
                            "page_workflow_stage": "read_table_summary",
                        },
                    }
                ],
                "selected_tool_names": [],
            },
            conversation_turn={"message_id": 116},
        )
    )

    assert cause_code != "page_continuation_missed"


def test_classify_root_cause_blocks_success_shortcut_on_budget_exit_reason(mock_db):
    from app.services.ai.runtime_diagnostics_service import RuntimeDiagnosticsService

    service = RuntimeDiagnosticsService(mock_db)
    failure_layer, cause_code, summary, first_fix, confidence = (
        service._classify_root_cause(
            call_log=_call_log(),
            diagnostics={
                "turn_outcome": "success",
                "termination_reason": "completed",
                "budget_exit_reason": "elapsed_budget_exceeded",
                "failure_kind": None,
            },
            conversation_turn={"message_id": 201},
        )
    )

    assert failure_layer == "post_processing"
    assert cause_code == "elapsed_budget_exceeded"
    assert "runtime budget" in summary.lower()
    assert first_fix is not None
    assert confidence == 0.8


def test_classify_root_cause_prefers_budget_exit_over_untrusted_final_output_source(
    mock_db,
):
    from app.services.ai.runtime_diagnostics_service import RuntimeDiagnosticsService

    service = RuntimeDiagnosticsService(mock_db)
    failure_layer, cause_code, summary, first_fix, confidence = (
        service._classify_root_cause(
            call_log=_call_log(),
            diagnostics={
                "turn_outcome": "partial",
                "conversation_outcome": "partial",
                "termination_reason": "elapsed_budget_exceeded",
                "budget_exit_reason": "elapsed_budget_exceeded",
                "partial_exit_reason": "elapsed_budget_exceeded",
                "failure_kind": "budget_exit",
                "final_output_source": "budget_fallback",
                "selected_tool_names": ["ui_get_snapshot"],
                "candidate_tool_names": ["ui_get_snapshot"],
                "provider_events": [
                    {"kind": "budget_exit", "reason": "elapsed_budget_exceeded"}
                ],
            },
            conversation_turn={"message_id": 202},
        )
    )

    assert failure_layer == "post_processing"
    assert cause_code == "elapsed_budget_exceeded"
    assert "runtime budget" in summary.lower()
    assert first_fix is not None
    assert confidence == 0.8


def test_classify_root_cause_prefers_provider_gateway_over_untrusted_final_output_source(
    mock_db,
):
    from app.services.ai.runtime_diagnostics_service import RuntimeDiagnosticsService

    service = RuntimeDiagnosticsService(mock_db)
    failure_layer, cause_code, summary, first_fix, confidence = (
        service._classify_root_cause(
            call_log=_call_log(status=CallStatusEnum.FAILED.value),
            diagnostics={
                "turn_outcome": "partial",
                "conversation_outcome": "failed",
                "termination_reason": "provider_error",
                "failure_kind": "provider_http_5xx",
                "final_output_source": "partial_output",
                "unfinished_intents": ["intent-1"],
                "provider_events": [{"kind": "provider_http_5xx", "status_code": 503}],
            },
            conversation_turn={"message_id": 203},
        )
    )

    assert failure_layer == "provider_gateway"
    assert cause_code == "provider_http_5xx"
    assert "provider gateway" in summary.lower()
    assert first_fix is not None
    assert confidence == 0.84


def test_classify_root_cause_normalizes_generic_provider_error_to_provider_gateway(
    mock_db,
):
    from app.services.ai.runtime_diagnostics_service import RuntimeDiagnosticsService

    service = RuntimeDiagnosticsService(mock_db)
    failure_layer, cause_code, summary, first_fix, confidence = (
        service._classify_root_cause(
            call_log=_call_log(
                status=CallStatusEnum.FAILED.value,
                error_message="AI 供应商服务端错误",
                request_metadata={
                    "turn_record": {
                        "metadata": {
                            "stream_failure_error_type": "ProviderError",
                            "stream_failure_chunk_count": 0,
                            "stream_failure_has_meaningful_chunk": False,
                        }
                    }
                },
            ),
            diagnostics={
                "turn_outcome": "failed",
                "conversation_outcome": "failed",
                "termination_reason": "error",
                "failure_kind": "ProviderError",
            },
            conversation_turn={"message_id": 204},
        )
    )

    assert failure_layer == "provider_gateway"
    assert cause_code == "provider_http_5xx"
    assert "provider gateway" in summary.lower()
    assert first_fix is not None
    assert confidence == 0.84


def test_resolve_root_cause_status_marks_non_trusted_final_output_source_failed(
    mock_db,
):
    from app.services.ai.runtime_diagnostics_service import RuntimeDiagnosticsService

    service = RuntimeDiagnosticsService(mock_db)
    status = service._resolve_root_cause_status(
        call_log=_call_log(),
        diagnostics={
            "turn_outcome": "success",
            "termination_reason": "completed",
            "final_output_source": "tool_evidence_completed",
            "failure_kind": None,
        },
        conversation_turn={"message_id": 202},
    )

    assert status == "failed"


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
            "candidate_tool_names": ["ui_get_snapshot"],
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
    conversation_service = SimpleNamespace(
        get_messages_for_conversation=AsyncMock(return_value=messages)
    )

    with patch.object(
        __import__(
            "app.services.ai.runtime_diagnostics_query_service",
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


@pytest.mark.asyncio
async def test_build_root_cause_classifies_provider_timeout_before_first_chunk(mock_db):
    from app.services.ai.runtime_diagnostics_service import RuntimeDiagnosticsService

    service = RuntimeDiagnosticsService(mock_db)
    conversation_turn = {
        "message_id": 7541,
        "diagnostics": {
            "conversation_outcome": "success",
            "turn_outcome": "partial",
            "termination_reason": "error",
            "protocol_path": "chat_completions",
        },
    }
    call_log = _call_log(
        status=CallStatusEnum.FAILED.value,
        request_metadata={
            "request": {
                "turn_record": {
                    "turn_outcome": "failed",
                    "termination_reason": "error",
                    "protocol_path": "responses",
                    "metadata": {
                        "protocol_fallback_blocked_reason": "provider_timeout",
                        "stream_failure_chunk_count": 0,
                        "stream_failure_has_meaningful_chunk": False,
                        "stream_failure_error_type": "ProviderTimeoutError",
                    },
                }
            },
        },
    )
    call_log.error_message = "Request timed out."

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
        report = await service.build_root_cause(conversation_id=1208, turn=1)

    assert report["status"] == "failed"
    assert report["failure_layer"] == "provider_gateway"
    assert report["cause_code"] == "provider_timeout_before_first_meaningful_chunk"
    evidence = {item["label"]: item["value"] for item in report["evidence"]}
    assert evidence["protocol_fallback_blocked_reason"] == "provider_timeout"
    assert evidence["turn_record_protocol_path"] == "responses"


@pytest.mark.asyncio
async def test_build_root_cause_loads_conversation_turn_for_call_log_and_flags_incomplete_page_reply(
    mock_db,
):
    from app.services.ai.runtime_diagnostics_service import RuntimeDiagnosticsService

    service = RuntimeDiagnosticsService(mock_db)
    call_log = _call_log(
        request_metadata={
            "turn_diagnostics": {
                "conversation_outcome": "success",
                "turn_outcome": "success",
                "continuation_source": "page_ops",
                "tool_planner": {
                    "intent": "page_search",
                    "family": "page_ops",
                },
                "candidate_tool_names": [
                    "ui_read_region",
                    "ui_list_interactables",
                    "ui_click",
                ],
                "selected_tool_names": [],
            }
        }
    )
    conversation_turn = {
        "message_id": 7659,
        "assistant_content": "我先帮你检查一下页面上有没有可用的搜索区域或关键词“发票”的相关内容喵~",
        "metadata": {
            "turn_flow": {
                "timeline": [
                    {
                        "id": "answer_assembly",
                        "type": "answer_assembly",
                        "status": "completed",
                        "title": "答案生成",
                        "summary": "已生成最终答复",
                    },
                    {
                        "id": "terminal",
                        "type": "completed",
                        "status": "completed",
                        "title": "本轮结束",
                        "summary": "completed",
                    },
                ],
                "evidence": [],
                "answer_card": {
                    "summary": "我先帮你检查一下页面上有没有可用的搜索区域或关键词“发票”的相关内容喵~",
                    "sections": [],
                    "source_chip_ids": [],
                },
                "completion_reason": "completed",
            },
            "context_diagnostics": {
                "conversation_outcome": "success",
                "turn_outcome": "success",
                "continuation_source": "page_ops",
                "tool_planner": {
                    "intent": "page_search",
                    "family": "page_ops",
                },
                "intent_plan": [
                    {
                        "intent_id": "intent-1",
                        "kind": "page_search",
                        "family": "page_ops",
                        "status": "completed",
                        "completed_by_tool_names": ["ui_list_interactables"],
                    }
                ],
                "candidate_tool_names": [
                    "ui_read_region",
                    "ui_list_interactables",
                    "ui_click",
                ],
                "selected_tool_names": [],
            },
        },
        "diagnostics": {
            "conversation_outcome": "success",
            "turn_outcome": "success",
            "continuation_source": "page_ops",
            "tool_planner": {
                "intent": "page_search",
                "family": "page_ops",
            },
            "intent_plan": [
                {
                    "intent_id": "intent-1",
                    "kind": "page_search",
                    "family": "page_ops",
                    "status": "completed",
                    "completed_by_tool_names": ["ui_list_interactables"],
                }
            ],
            "candidate_tool_names": [
                "ui_read_region",
                "ui_list_interactables",
                "ui_click",
            ],
            "selected_tool_names": [],
        },
    }

    with (
        patch.object(
            service,
            "_resolve_call_log",
            new=AsyncMock(return_value=call_log),
        ),
        patch.object(
            service,
            "_resolve_conversation_turn_for_call_log",
            new=AsyncMock(return_value=conversation_turn),
        ) as resolve_turn,
    ):
        report = await service.build_root_cause(call_log_id=3665)

    resolve_turn.assert_awaited_once_with(call_log=call_log)
    assert report["status"] == "failed"
    assert report["failure_layer"] == "post_processing"
    assert report["cause_code"] == "incomplete_promissory_reply"
    assert report["related_ids"]["conversation_message_id"] == 7659


@pytest.mark.asyncio
async def test_build_root_cause_flags_incomplete_page_reply_from_canonical_page_workflow(
    mock_db,
):
    from app.services.ai.runtime_diagnostics_service import RuntimeDiagnosticsService

    service = RuntimeDiagnosticsService(mock_db)
    call_log = _call_log(
        request_metadata={
            "turn_diagnostics": {
                "conversation_outcome": "success",
                "turn_outcome": "success",
                "continuation_source": "page_ops",
                "tool_planner": {
                    "intent": "page_workflow",
                    "family": "page_ops",
                },
                "intent_plan": [
                    {
                        "intent_id": "intent-1",
                        "kind": "page_workflow",
                        "family": "page_ops",
                        "status": "completed",
                        "completed_by_tool_names": ["ui_list_interactables"],
                        "metadata": {
                            "page_workflow_kind": "page_workflow",
                            "page_workflow_goal": "search",
                            "page_workflow_phase": "read",
                        },
                    }
                ],
                "candidate_tool_names": [
                    "ui_read_region",
                    "ui_list_interactables",
                    "ui_click",
                ],
                "selected_tool_names": [],
            }
        }
    )
    conversation_turn = {
        "message_id": 7660,
        "assistant_content": "我先帮你检查一下页面上有没有可用的搜索区域或关键词“发票”的相关内容喵~",
        "metadata": {
            "turn_flow": {
                "timeline": [
                    {
                        "id": "answer_assembly",
                        "type": "answer_assembly",
                        "status": "completed",
                        "title": "答案生成",
                        "summary": "已生成最终答复",
                    },
                    {
                        "id": "terminal",
                        "type": "completed",
                        "status": "completed",
                        "title": "本轮结束",
                        "summary": "completed",
                    },
                ],
                "evidence": [],
                "answer_card": {
                    "summary": "我先帮你检查一下页面上有没有可用的搜索区域或关键词“发票”的相关内容喵~",
                    "sections": [],
                    "source_chip_ids": [],
                },
                "completion_reason": "completed",
            },
            "context_diagnostics": {
                "conversation_outcome": "success",
                "turn_outcome": "success",
                "continuation_source": "page_ops",
                "tool_planner": {
                    "intent": "page_workflow",
                    "family": "page_ops",
                },
                "intent_plan": [
                    {
                        "intent_id": "intent-1",
                        "kind": "page_workflow",
                        "family": "page_ops",
                        "status": "completed",
                        "completed_by_tool_names": ["ui_list_interactables"],
                        "metadata": {
                            "page_workflow_kind": "page_workflow",
                            "page_workflow_goal": "search",
                            "page_workflow_phase": "read",
                        },
                    }
                ],
                "candidate_tool_names": [
                    "ui_read_region",
                    "ui_list_interactables",
                    "ui_click",
                ],
                "selected_tool_names": [],
            },
        },
        "diagnostics": {
            "conversation_outcome": "success",
            "turn_outcome": "success",
            "continuation_source": "page_ops",
            "tool_planner": {
                "intent": "page_workflow",
                "family": "page_ops",
            },
            "intent_plan": [
                {
                    "intent_id": "intent-1",
                    "kind": "page_workflow",
                    "family": "page_ops",
                    "status": "completed",
                    "completed_by_tool_names": ["ui_list_interactables"],
                    "metadata": {
                        "page_workflow_kind": "page_workflow",
                        "page_workflow_goal": "search",
                        "page_workflow_phase": "read",
                    },
                }
            ],
            "candidate_tool_names": [
                "ui_read_region",
                "ui_list_interactables",
                "ui_click",
            ],
            "selected_tool_names": [],
        },
    }

    with (
        patch.object(
            service,
            "_resolve_call_log",
            new=AsyncMock(return_value=call_log),
        ),
        patch.object(
            service,
            "_resolve_conversation_turn_for_call_log",
            new=AsyncMock(return_value=conversation_turn),
        ),
    ):
        report = await service.build_root_cause(call_log_id=3666)

    assert report["status"] == "failed"
    assert report["failure_layer"] == "post_processing"
    assert report["cause_code"] == "incomplete_promissory_reply"
    evidence = {item["label"]: item["value"] for item in report["evidence"]}
    assert evidence["page_workflow"]["goal"] == "search"
