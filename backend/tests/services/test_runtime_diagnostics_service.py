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


def test_runtime_diagnostics_manifest_checks_ignore_unknown_manifest_sections() -> None:
    from app.services.ai.runtime_diagnostics_support import (
        RuntimeDiagnosticsCheckSupport,
    )

    support = RuntimeDiagnosticsCheckSupport()
    checks = support.build_manifest_checks(
        {
            "summary": {"tool_count": 0, "skill_count": 0},
            "provider": {"status": "available"},
            "model": {"status": "available"},
            "legacy_section": [
                {
                    "name": "legacy_capability",
                    "status": "available",
                }
            ],
            "knowledge_bases": [],
            "memory": [],
        },
        require_agent=False,
    )

    assert "legacy_section_contract" not in {item["name"] for item in checks}


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
