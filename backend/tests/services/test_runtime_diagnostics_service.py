"""Test type: behavioral
Scope: runtime diagnostics root-cause classification and invalid runtime metadata scrubbing
Real dependencies: RuntimeDiagnosticsService root-cause projector and diagnostics helpers
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


def test_runtime_diagnostics_query_selects_final_assistant_after_tool_round() -> None:
    from app.enums.agent import MessageRoleEnum
    from app.services.ai.runtime_diagnostics_query_service import (
        RuntimeDiagnosticsQueryService,
    )

    messages = [
        SimpleNamespace(
            id=9101,
            role=MessageRoleEnum.USER.value,
            content="帮我搜索一下2025年大模型使用token排行",
            metadata_={},
            tool_calls=[],
        ),
        SimpleNamespace(
            id=9102,
            role=MessageRoleEnum.ASSISTANT.value,
            content="",
            metadata_={
                "context_diagnostics": {
                    "turn_outcome": "success",
                    "termination_reason": "protocol_fallback",
                    "protocol_path": "responses",
                    "failure_kind": "provider_unavailable",
                    "selected_tool_names": ["web_search"],
                }
            },
            tool_calls=[{"function": {"name": "web_search"}}],
        ),
        SimpleNamespace(
            id=9103,
            role=MessageRoleEnum.TOOL.value,
            content="Search results for: 2025 大模型 token 使用量排行",
            metadata_={},
            tool_calls=[],
        ),
        SimpleNamespace(
            id=9104,
            role=MessageRoleEnum.ASSISTANT.value,
            content="OpenRouter 报告显示 2025 年大模型 token 调用达到 100 万亿。",
            metadata_={
                "context_diagnostics": {
                    "turn_outcome": "success",
                    "termination_reason": "completed",
                    "protocol_path": "responses",
                    "failure_kind": "none",
                    "final_output_source": "recovery_evidence",
                }
            },
            tool_calls=[],
        ),
    ]

    selected = RuntimeDiagnosticsQueryService._select_conversation_turn_message(
        messages,
        turn=1,
    )

    assert selected.id == 9104


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


def test_classify_root_cause_scrubs_invalid_ai_runtime_input_diagnostics(mock_db):
    from app.services.ai.runtime_diagnostics_service import RuntimeDiagnosticsService

    service = RuntimeDiagnosticsService(mock_db)
    failure_layer, cause_code, summary, first_fix, confidence = (
        service._classify_root_cause(
            call_log=_call_log(),
            diagnostics={
                "conversation_outcome": "failed",
                "continuation_source": "data_ops",
                "tool_planner": {
                    "intent": "page_search",
                    "family": "data_ops",
                },
                "candidate_tool_names": ["crm_lookup"],
                "selected_skill_names": ["runtime.crm_records", "Research Skill"],
            },
            conversation_turn={"message_id": 91},
        )
    )

    assert failure_layer == "post_processing"
    assert cause_code == "unknown_failure"
    assert "data_ops" not in summary
    assert first_fix is not None
    assert confidence == 0.6


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


def test_root_cause_keeps_trusted_completed_assistant_turn_success_over_stale_budget_evidence(
    mock_db,
):
    from app.services.ai.runtime_diagnostics_service import RuntimeDiagnosticsService

    service = RuntimeDiagnosticsService(mock_db)
    diagnostics = {
        "turn_outcome": "success",
        "conversation_outcome": "failed",
        "termination_reason": "completed",
        "budget_exit_reason": "elapsed_budget_exceeded",
        "failure_kind": "budget_exit",
        "final_output_source": "assistant",
        "selected_tool_names": ["web_search", "fetch_url"],
        "candidate_tool_names": ["web_search", "fetch_url"],
        "selected_skill_names": ["web_search"],
        "provider_events": [
            {"kind": "budget_exit", "reason": "elapsed_budget_exceeded"}
        ],
    }

    failure_layer, cause_code, summary, first_fix, confidence = (
        service._classify_root_cause(
            call_log=_call_log(),
            diagnostics=diagnostics,
            conversation_turn={"message_id": 2260},
        )
    )
    status = service._resolve_root_cause_status(
        call_log=_call_log(),
        diagnostics=diagnostics,
        conversation_turn={"message_id": 2260},
    )
    evidence = service._build_root_cause_evidence(
        _call_log(),
        diagnostics,
        conversation_turn={"message_id": 2260},
    )

    assert status == "success"
    assert failure_layer is None
    assert cause_code is None
    assert "completed successfully" in summary
    assert first_fix is None
    assert confidence == 0.98
    assert {"label": "conversation_outcome", "value": "success"} in evidence
    assert not any(item.get("label") == "failure_kind" for item in evidence)


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
                "selected_tool_names": ["crm_lookup"],
                "candidate_tool_names": ["crm_lookup"],
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
            "continuation_source": "data_ops",
            "tool_planner": {
                "intent": "direct_reply",
                "family": "none",
            },
            "candidate_tool_names": ["crm_lookup"],
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
async def test_build_root_cause_treats_recovered_protocol_fallback_as_success(
    mock_db,
):
    from app.services.ai.runtime_diagnostics_service import RuntimeDiagnosticsService

    service = RuntimeDiagnosticsService(mock_db)
    conversation_turn = {
        "message_id": 7542,
        "diagnostics": {
            "conversation_outcome": "success",
            "turn_outcome": "success",
            "termination_reason": "protocol_fallback",
            "protocol_path": "responses",
            "failure_kind": "provider_timeout",
            "provider_events": [
                {
                    "kind": "web_search_in_progress",
                    "protocol_path": "responses",
                }
            ],
            "fallback_history": [
                {
                    "from_protocol": "responses",
                    "to_protocol": "responses",
                    "reason": "hosted_web_search_unavailable:provider_timeout",
                    "recovered": True,
                    "metadata": {"recovery_path": "protocol_fallback"},
                }
            ],
        },
    }
    call_log = _call_log(
        status=CallStatusEnum.SUCCESS.value,
        request_metadata={
            "request": {
                "turn_record": {
                    "turn_outcome": "success",
                    "termination_reason": "protocol_fallback",
                    "protocol_path": "responses",
                    "failure_kind": "provider_timeout",
                    "fallback_history": [
                        {
                            "from_protocol": "responses",
                            "to_protocol": "responses",
                            "reason": "hosted_web_search_unavailable:provider_timeout",
                            "recovered": True,
                            "metadata": {"recovery_path": "protocol_fallback"},
                        }
                    ],
                    "metadata": {
                        "stream_failure_chunk_count": 3,
                        "stream_failure_has_meaningful_chunk": False,
                        "stream_failure_error_type": "ProviderTimeoutError",
                    },
                }
            },
        },
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
        report = await service.build_root_cause(conversation_id=1209, turn=1)

    assert report["status"] == "success"
    assert report["failure_layer"] is None
    assert report["cause_code"] is None
    assert report["summary"] == (
        "The call completed successfully and no blocking failure signal was found."
    )


@pytest.mark.asyncio
async def test_build_root_cause_keeps_recovery_evidence_output_success_over_trailing_failed_call_log(
    mock_db,
):
    from app.services.ai.runtime_diagnostics_service import RuntimeDiagnosticsService

    service = RuntimeDiagnosticsService(mock_db)
    conversation_turn = {
        "message_id": 13189,
        "assistant_content": (
            "2025 OpenRouter 大模型使用报告显示，100万亿 Token 调用来自多模型生态。"
        ),
        "diagnostics": {
            "conversation_outcome": "success",
            "turn_outcome": "success",
            "termination_reason": "completed",
            "protocol_path": "responses",
            "failure_kind": "none",
            "final_output_source": "recovery_evidence",
            "selected_tool_names": ["fetch_url"],
            "selected_skill_names": ["web_search"],
        },
        "metadata": {
            "turn_flow": {
                "timeline": [
                    {
                        "id": "terminal",
                        "type": "failed",
                        "status": "error",
                    }
                ],
                "error_surface": {"error_type": "provider_unavailable"},
            }
        },
    }
    failed_call_log = _call_log(
        status=CallStatusEnum.FAILED.value,
        error_message="Connection error.",
        request_metadata={
            "request": {
                "turn_record": {
                    "turn_outcome": "failed",
                    "termination_reason": "provider_unavailable",
                    "protocol_path": "responses",
                    "failure_kind": "provider_unavailable",
                    "selected_skill_names": ["web_search"],
                }
            },
        },
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
            new=AsyncMock(return_value=failed_call_log),
        ),
    ):
        report = await service.build_root_cause(conversation_id=2272, turn=1)

    assert report["status"] == "success"
    assert report["failure_layer"] is None
    assert report["cause_code"] is None
    assert report["related_ids"]["conversation_message_id"] == 13189
    evidence = {item["label"]: item["value"] for item in report["evidence"]}
    assert "turn_flow_terminal_stage_status" not in evidence
    assert "stream_failure_error_type" not in evidence


@pytest.mark.asyncio
async def test_build_root_cause_flags_raw_search_only_recovery_when_fetch_required(
    mock_db,
):
    from app.services.ai.runtime_diagnostics_service import RuntimeDiagnosticsService

    service = RuntimeDiagnosticsService(mock_db)
    conversation_turn = {
        "message_id": 13235,
        "assistant_content": (
            "日耗37万亿 Tokens ,千问稳居第一 - "
            "http://www.baidu.com/link?url=example-token-ranking"
        ),
        "diagnostics": {
            "conversation_outcome": "success",
            "turn_outcome": "success",
            "termination_reason": "protocol_fallback",
            "protocol_path": "responses",
            "failure_kind": "provider_timeout",
            "final_output_source": "recovery_evidence",
            "selected_tool_names": ["web_search", "fetch_url"],
            "candidate_tool_names": ["web_search", "fetch_url"],
            "selected_skill_names": ["web_search"],
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
            "tool_planner": {
                "intent": "web_research",
                "family": "web_research",
                "intent_plan": [
                    {
                        "intent_id": "intent-1",
                        "kind": "web_research",
                        "family": "web_research",
                        "status": "pending",
                        "allowed_tool_names": ["web_search", "fetch_url"],
                        "completed_by_tool_names": [],
                    }
                ],
            },
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
        },
        "metadata": {
            "turn_flow": {
                "timeline": [
                    {
                        "id": "answer_assembly",
                        "type": "failed",
                        "status": "error",
                    }
                ],
                "error_surface": {"failure_kind": "provider_timeout"},
            }
        },
    }
    call_log = _call_log(
        status=CallStatusEnum.SUCCESS.value,
        request_metadata={
            "request": {
                "turn_record": {
                    "turn_outcome": "success",
                    "termination_reason": "protocol_fallback",
                    "protocol_path": "responses",
                    "failure_kind": "provider_timeout",
                    "final_output_source": "recovery_evidence",
                    "selected_tool_names": ["web_search", "fetch_url"],
                }
            },
        },
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
        report = await service.build_root_cause(conversation_id=2276, turn=1)

    assert report["status"] == "failed"
    assert report["failure_layer"] == "research_contract"
    assert report["cause_code"] == "raw_search_only_recovery_finalized"
    assert "fetch_url evidence was still required" in report["summary"]
    evidence = {item["label"]: item["value"] for item in report["evidence"]}
    assert evidence["failure_kind"] == "raw_search_only_recovery_finalized"
    assert evidence["missing_required_tool_names"] == ["fetch_url"]
    assert evidence["final_output_source"] == "recovery_evidence"


@pytest.mark.asyncio
async def test_build_root_cause_scrubs_invalid_runtime_metadata_from_evidence(mock_db):
    from app.services.ai.runtime_diagnostics_service import RuntimeDiagnosticsService

    service = RuntimeDiagnosticsService(mock_db)
    call_log = _call_log(
        request_metadata={
            "turn_diagnostics": {
                "conversation_outcome": "failed",
                "continuation_source": "data_ops",
                "tool_planner": {
                    "intent": "page_search",
                    "family": "data_ops",
                },
                "candidate_tool_names": ["crm_read_record", "web_search"],
                "selected_tool_names": ["crm_lookup", "fetch_url"],
            }
        }
    )
    conversation_turn = {
        "message_id": 7660,
        "assistant_content": "检索失败，请稍后重试。",
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
                    "summary": "检索失败，请稍后重试。",
                    "sections": [],
                    "source_chip_ids": [],
                },
                "completion_reason": "error",
            },
            "context_diagnostics": {
                "conversation_outcome": "failed",
                "continuation_source": "data_ops",
                "tool_planner": {
                    "intent": "page_search",
                    "family": "data_ops",
                },
                "candidate_tool_names": ["crm_read_record", "web_search"],
                "selected_tool_names": ["crm_lookup", "fetch_url"],
            },
        },
        "diagnostics": {
            "conversation_outcome": "failed",
            "continuation_source": "data_ops",
            "tool_planner": {
                "intent": "page_search",
                "family": "data_ops",
            },
            "candidate_tool_names": ["crm_read_record", "web_search"],
            "selected_tool_names": ["crm_lookup", "fetch_url"],
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
    assert report["failure_layer"] == "tool_execution"
    assert report["cause_code"] == "error"
    evidence = {item["label"]: item["value"] for item in report["evidence"]}
    assert evidence["selected_tool_names"] == ["fetch_url"]
    assert evidence["candidate_tool_names"] == ["web_search"]
    assert "continuation_source" not in evidence
    assert "tool_planner" not in evidence
