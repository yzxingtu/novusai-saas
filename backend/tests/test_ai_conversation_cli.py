"""AI conversation CLI tests / AI 对话 CLI 测试。

Test type: behavioral
Scope: CLI conversation detail and diagnostics read-model projection.
Mocked dependencies: CLI async loaders return stable stored snapshots; the
diagnostic hydration and turn-flow projection logic runs real code.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from click.testing import CliRunner


def _return_value(value):
    def _inner(coro):
        coro.close()
        return value

    return _inner


def _sample_snapshot() -> dict:
    return {
        "conversation": {
            "id": 563,
            "tenant_id": 0,
            "agent_id": 59,
            "agent_name": "猫娘智能体",
            "user_id": 1,
            "owner_type": "platform_admin",
            "status": "active",
            "title": "诊断查询一下 小猫为什么 爱吃鱼",
            "message_count": 18,
            "token_count": 61750,
            "cost": 0.0,
            "created_at": "2026-03-28T16:06:37+00:00",
            "updated_at": "2026-03-28T17:11:46+00:00",
        },
        "recent_messages": [
            {
                "id": 3234,
                "sequence": 17,
                "role": "user",
                "created_at": "2026-03-28T17:11:46+00:00",
                "content": "查询对象存储对帐计费",
                "tool_calls": None,
                "metadata": None,
            },
            {
                "id": 3235,
                "sequence": 18,
                "role": "assistant",
                "created_at": "2026-03-28T17:11:46+00:00",
                "content": "to=functions.crm_lookup 天天中奖不json_string",
                "tool_calls": None,
                "metadata": {
                    "model_name": "gpt-5.4-xhigh",
                    "provider_name": "响应云",
                },
            },
        ],
        "keyword": "对象存储对帐计费",
        "keyword_hits": [
            {
                "id": 3234,
                "sequence": 17,
                "role": "user",
                "created_at": "2026-03-28T17:11:46+00:00",
                "content": "查询对象存储对帐计费",
            }
        ],
        "recent_call_logs": [
            {
                "id": 815,
                "created_at": "2026-03-28T17:11:46+00:00",
                "status": "success",
                "call_type": "main_chat",
                "provider_name": "响应云",
                "model_name": "gpt-5.4-xhigh",
                "total_tokens": 6061,
                "latency_ms": 4931,
                "error_message": None,
            }
        ],
        "diagnostics": {
            "last_assistant_looks_like_textual_tool_call": True,
            "last_assistant_textual_tool_call_names": ["crm_lookup"],
            "contract_breach_type": "leaked_textual_tool_call",
            "unfinished_intents": ["rail_ticket_research", "workflow_summary"],
            "recovered_via_retry": True,
            "last_assistant_message_id": 3235,
            "last_assistant_sequence": 18,
        },
    }


def _sample_snapshot_with_datetimes() -> dict:
    snapshot = _sample_snapshot()
    ts = datetime(2026, 3, 28, 17, 11, 46, tzinfo=timezone.utc)
    snapshot["recent_messages"][0]["created_at"] = ts
    snapshot["recent_messages"][1]["metadata"]["seen_at"] = ts
    snapshot["recent_call_logs"][0]["created_at"] = ts
    return snapshot


def _sample_snapshot_with_nested_assistant_diagnostics() -> dict:
    snapshot = _sample_snapshot()
    snapshot["recent_messages"][1]["metadata"]["context_diagnostics"] = {
        "execution_path": "fast",
        "intent_plan": [
            {
                "intent_id": "intent-1",
                "family": "weather",
                "status": "pending",
                "allowed_tool_names": ["get_current_weather"],
            }
        ],
        "budget": {
            "status": "exited",
            "exit_reason": "completion_budget_exceeded",
        },
        "budget_exit_reason": "completion_budget_exceeded",
        "partial_exit_reason": "completion_budget_exceeded",
        "tool_loop_progress": {"budget_exit_reason": "completion_budget_exceeded"},
    }
    snapshot["recent_messages"][1]["metadata"]["last_run_summary"] = {
        "execution_path": "fast",
        "turn_outcome": "partial",
        "termination_reason": "completion_budget_exceeded",
    }
    return snapshot


def _sample_snapshot_with_historical_budget_exit_metadata() -> dict:
    snapshot = _sample_snapshot()
    snapshot["recent_messages"][1]["metadata"]["context_diagnostics"] = {
        "turn_outcome": "partial",
        "termination_reason": "completion_budget_exceeded",
        "tool_loop_progress": {"budget_exit_reason": "completion_budget_exceeded"},
        "tool_planner": {
            "execution_path": "fast",
            "intent_plan": [
                {
                    "intent_id": "intent-1",
                    "family": "weather",
                    "status": "pending",
                    "allowed_tool_names": ["get_current_weather"],
                }
            ],
        },
    }
    snapshot["recent_messages"][1]["metadata"]["last_run_summary"] = {
        "turn_outcome": "partial",
        "termination_reason": "completion_budget_exceeded",
        "tool_loop_progress": {"budget_exit_reason": "completion_budget_exceeded"},
        "tool_planner": {
            "execution_path": "fast",
            "intent_plan": [
                {
                    "intent_id": "intent-1",
                    "family": "weather",
                    "status": "pending",
                    "allowed_tool_names": ["get_current_weather"],
                }
            ],
        },
    }
    return snapshot


def _sample_snapshot_with_call_log_turn_record_fallback() -> dict:
    snapshot = _sample_snapshot()
    snapshot["recent_messages"][1]["metadata"] = {
        "model_name": "gpt-5.4-xhigh",
        "provider_name": "响应云",
    }
    snapshot["recent_call_logs"][0].update(
        {
            "turn_outcome": "partial",
            "termination_reason": "elapsed_budget_exceeded",
            "execution_path": "fast",
            "budget_exit_reason": "elapsed_budget_exceeded",
            "tool_loop_progress": {
                "budget_exit_reason": "elapsed_budget_exceeded",
                "marker": "None",
            },
            "contract_breach_type": "None",
            "tool_leak_detected": True,
            "unfinished_intents": ["intent-1", "None"],
            "leaked_tool_names": ["get_current_weather", "None"],
            "recovered_via_retry": "true",
            "fallback_history": [
                {
                    "from_protocol": "None",
                    "to_protocol": "fast",
                    "reason": "None",
                    "metadata": {"marker": "None"},
                }
            ],
            "turn_record": {
                "execution_path": "fast",
                "budget_status": "exited",
                "budget_exit_reason": "elapsed_budget_exceeded",
                "budget": {
                    "status": "exited",
                    "exit_reason": "elapsed_budget_exceeded",
                    "note": "None",
                },
                "intent_plan": [
                    {
                        "intent_id": "intent-1",
                        "family": "weather",
                        "status": "completed",
                        "user_visible_label": "None",
                        "allowed_tool_names": ["get_current_weather"],
                    }
                ],
                "tool_loop_progress": {
                    "budget_exit_reason": "elapsed_budget_exceeded",
                    "marker": "None",
                },
                "metadata": {
                    "tool_leak_detected": True,
                    "unfinished_intents": ["intent-1", "None"],
                    "leaked_tool_names": ["get_current_weather", "None"],
                    "recovered_via_retry": "true",
                },
            },
        }
    )
    snapshot["diagnostics"] = {
        "last_assistant_message_id": 3235,
        "last_assistant_sequence": 18,
    }
    return snapshot


def _sample_snapshot_with_call_log_provider_failure_metadata() -> dict:
    snapshot = _sample_snapshot()
    snapshot["recent_messages"][1]["metadata"] = {
        "model_name": "gpt-5.4-xhigh",
        "provider_name": "响应云",
    }
    snapshot["recent_call_logs"][0].update(
        {
            "status": "failed",
            "error_message": "Connection error.",
            "turn_outcome": "failed",
            "termination_reason": "error",
            "protocol_path": "responses",
            "turn_record": {
                "turn_outcome": "failed",
                "termination_reason": "error",
                "protocol_path": "responses",
                "metadata": {
                    "protocol_fallback_blocked_reason": "provider_connection_error",
                    "stream_failure_error_type": "ProviderConnectionError",
                },
            },
        }
    )
    snapshot["diagnostics"] = {
        "last_assistant_message_id": 3235,
        "last_assistant_sequence": 18,
    }
    return snapshot


def _sample_snapshot_with_completed_turn_and_stale_budget_failure_projection() -> dict:
    snapshot = _sample_snapshot()
    snapshot["conversation"].update(
        {
            "id": 2260,
            "title": "帮我搜索一下2025年中国新能源汽车销量排行",
            "message_count": 2,
            "token_count": 779,
        }
    )
    snapshot["recent_messages"] = [
        {
            "id": 9101,
            "sequence": 1,
            "role": "user",
            "created_at": "2026-05-02T05:31:00+00:00",
            "content": "帮我搜索一下2025年中国新能源汽车销量排行",
            "tool_calls": None,
            "metadata": None,
        },
        {
            "id": 9102,
            "sequence": 2,
            "role": "assistant",
            "created_at": "2026-05-02T05:34:28+00:00",
            "content": "2025年中国新能源汽车销量排行：比亚迪、特斯拉中国、吉利汽车。",
            "tool_calls": None,
            "metadata": {},
        },
    ]
    budget = {
        "status": "exited",
        "exit_reason": "elapsed_budget_exceeded",
        "usage": {
            "elapsed_ms_used": 207985,
            "elapsed_limit_ms": 60000,
            "elapsed_over_limit": True,
        },
    }
    turn_flow = {
        "timeline": [
            {
                "id": "terminal",
                "type": "failed",
                "status": "error",
                "summary": "completed",
            }
        ],
        "completion_reason": "completed",
        "answer_card": {"summary": "2025年中国新能源汽车销量排行"},
        "error_surface": {
            "error_type": "budget_exit",
            "message": "The request ended before a final answer was produced.",
        },
    }
    turn_record = {
        "turn_outcome": "success",
        "termination_reason": "completed",
        "protocol_path": "responses",
        "execution_path": "normal",
        "selected_tool_names": ["crm_lookup", "query_records"],
        "selected_skill_names": ["CRM Lookup Skill"],
        "candidate_tool_names": ["crm_lookup", "query_records"],
        "final_output_source": "assistant",
        "budget": budget,
        "failure_kind": "budget_exit",
        "provider_events": [
            {"kind": "budget_exit", "reason": "elapsed_budget_exceeded"}
        ],
        "turn_flow": turn_flow,
    }
    stale_failure_projection = {
        "conversation_outcome": "failed",
        "turn_outcome": "success",
        "termination_reason": "completed",
        "protocol_path": "responses",
        "execution_path": "normal",
        "selected_tool_names": ["crm_lookup", "query_records"],
        "selected_skill_names": ["CRM Lookup Skill"],
        "candidate_tool_names": ["crm_lookup", "query_records"],
        "final_output_source": "assistant",
        "budget": budget,
        "budget_exit_reason": "elapsed_budget_exceeded",
        "failure_kind": "budget_exit",
        "provider_events": [
            {"kind": "budget_exit", "reason": "elapsed_budget_exceeded"}
        ],
    }
    snapshot["recent_messages"][1]["metadata"] = {
        "turn_record": turn_record,
        "context_diagnostics": dict(stale_failure_projection),
        "last_run_summary": {
            **stale_failure_projection,
            "success": True,
        },
        "turn_flow": turn_flow,
    }
    snapshot["recent_call_logs"] = [
        {
            "id": 9901,
            "created_at": "2026-05-02T05:34:28+00:00",
            "status": "success",
            "call_type": "main_chat",
            "provider_name": "响应云",
            "model_name": "gpt-5.5",
            "total_tokens": 779,
            "latency_ms": 207985,
            "error_message": None,
            "turn_outcome": "success",
            "termination_reason": "completed",
            "protocol_path": "responses",
            "turn_record": turn_record,
        }
    ]
    snapshot["diagnostics"] = {
        "last_assistant_message_id": 9102,
        "last_assistant_sequence": 2,
    }
    return snapshot


def _sample_snapshot_with_context_source_polluted_turn_flow() -> dict:
    snapshot = _sample_snapshot()
    snapshot["conversation"].update(
        {
            "id": 2340,
            "title": "帮我搜索一下2026年中国新能源汽车销量排行",
            "message_count": 2,
        }
    )
    polluted_turn_flow = {
        "timeline": [
            {
                "id": "retrieval",
                "type": "retrieval",
                "status": "completed",
                "summary": "Retrieved 3 sources",
                "metrics": {"source_count": 3},
                "source_refs": ["evidence_1", "evidence_2", "evidence_3"],
            },
            {
                "id": "failed",
                "type": "failed",
                "status": "error",
                "summary": "provider_unavailable",
            },
        ],
        "evidence": [
            {"id": "evidence_1", "kind": "knowledge_base", "title": "skill_resolver"},
            {"id": "evidence_2", "kind": "memory", "title": "long_term_memory"},
            {"id": "evidence_3", "kind": "knowledge_base", "title": "gpt-5.5"},
        ],
        "answer_card": {
            "summary": "Connection error.",
            "source_chip_ids": ["evidence_1", "evidence_2", "evidence_3"],
        },
        "completion_reason": "provider_unavailable",
        "error_surface": {
            "message": "Connection error.",
            "failure_kind": "provider_unavailable",
            "error_type": "untrusted_final_output_source",
        },
    }
    turn_record = {
        "turn_outcome": "partial",
        "termination_reason": "provider_unavailable",
        "protocol_path": "responses",
        "failure_kind": "provider_unavailable",
        "final_output_source": "partial_output",
        "selected_tool_names": [],
        "candidate_tool_names": [],
        "turn_flow": polluted_turn_flow,
    }
    snapshot["recent_messages"] = [
        {
            "id": 13_412,
            "sequence": 1,
            "role": "user",
            "created_at": "2026-05-05T18:45:05+00:00",
            "content": "帮我搜索一下2026年中国新能源汽车销量排行",
            "tool_calls": None,
            "metadata": None,
        },
        {
            "id": 13_413,
            "sequence": 2,
            "role": "assistant",
            "created_at": "2026-05-05T18:45:11+00:00",
            "content": "我先把已完成部分整理给你：direct_reply。",
            "tool_calls": None,
            "metadata": {
                "completion_reason": "provider_unavailable",
                "turn_record": turn_record,
                "turn_flow": polluted_turn_flow,
            },
        },
    ]
    snapshot["recent_call_logs"] = []
    snapshot["diagnostics"] = {
        "source": "assistant_turn_record",
        "turn_record": turn_record,
        "turn_outcome": "failed",
        "termination_reason": "provider_unavailable",
        "failure_kind": "provider_unavailable",
    }
    return snapshot


def test_ai_conversation_show_json_success(monkeypatch) -> None:
    from app.cli import cli

    monkeypatch.setattr("app.cli._run_async", _return_value(_sample_snapshot()))

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "ai",
            "conversation",
            "show",
            "563",
            "--keyword",
            "对象存储对帐计费",
            "--json",
        ],
    )

    assert result.exit_code == 0
    assert '"id": 563' in result.output
    assert '"last_assistant_textual_tool_call_names": [' in result.output
    assert '"crm_lookup"' in result.output


def test_ai_conversation_show_json_suppresses_runtime_logs(monkeypatch) -> None:
    from app.cli import cli
    from app.core.logging import get_logger

    def _fake_run_async(coro):
        coro.close()
        get_logger("tests.ai_conversation_cli").info("runtime noise should stay hidden")
        return _sample_snapshot()

    monkeypatch.setattr("app.cli._run_async", _fake_run_async)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["ai", "conversation", "show", "563", "--json"],
    )

    assert result.exit_code == 0
    assert result.output.lstrip().startswith("{")
    assert "runtime noise should stay hidden" not in result.output


def test_ai_conversation_show_json_accepts_trace_id_reference(monkeypatch) -> None:
    from app.cli import cli

    async def _fake_resolve(conversation_ref: str) -> int:
        assert conversation_ref == "9d819b44-f831-4e42-b550-6520d192ae54"
        return 563

    async def _fake_load(
        conversation_id: int,
        *,
        tail: int,
        keyword: str | None,
        keyword_limit: int,
    ) -> dict:
        assert conversation_id == 563
        assert tail == 8
        assert keyword is None
        assert keyword_limit == 20
        return _sample_snapshot()

    monkeypatch.setattr("app.cli._resolve_ai_conversation_reference", _fake_resolve)
    monkeypatch.setattr("app.cli._load_ai_conversation_snapshot", _fake_load)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "ai",
            "conversation",
            "show",
            "9d819b44-f831-4e42-b550-6520d192ae54",
            "--json",
        ],
    )

    assert result.exit_code == 0
    assert '"id": 563' in result.output


def test_ai_conversation_show_json_reports_non_conversation_trace_hint(
    monkeypatch,
) -> None:
    from app.cli import cli
    from app.exceptions import BusinessException

    async def _fake_resolve(conversation_ref: str) -> int:
        raise BusinessException(
            message="Trace exists but is not linked to an AI conversation. Use `novusai trace show <trace_id>` instead.",
            data={
                "code": "trace_not_linked_to_conversation",
                "trace_id": conversation_ref,
                "suggested_command": f"novusai trace show {conversation_ref}",
                "operation": "POST /admin/ai/agents/63/publish",
            },
        )

    monkeypatch.setattr("app.cli._resolve_ai_conversation_reference", _fake_resolve)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "ai",
            "conversation",
            "show",
            "ae80b0c3-d043-4c09-8aff-1b8533b5b1c3",
            "--json",
        ],
    )

    assert result.exit_code == 1
    assert '"code": "trace_not_linked_to_conversation"' in result.output
    assert '"operation": "POST /admin/ai/agents/63/publish"' in result.output
    assert (
        '"suggested_command": "novusai trace show ae80b0c3-d043-4c09-8aff-1b8533b5b1c3"'
        in result.output
    )


def test_ai_conversation_show_json_surfaces_nested_assistant_diagnostics(
    monkeypatch,
) -> None:
    from app.cli import cli

    monkeypatch.setattr(
        "app.cli._run_async",
        _return_value(_sample_snapshot_with_nested_assistant_diagnostics()),
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["ai", "conversation", "show", "563", "--json"],
    )

    assert result.exit_code == 0
    assert '"execution_path": "fast"' in result.output
    assert '"budget_exit_reason": "completion_budget_exceeded"' in result.output
    assert '"intent_id": "intent-1"' in result.output
    assert '"turn_outcome": "partial"' in result.output


def test_ai_conversation_show_json_infers_budget_exit_from_historical_assistant_metadata(
    monkeypatch,
) -> None:
    from app.cli import cli

    monkeypatch.setattr(
        "app.cli._run_async",
        _return_value(_sample_snapshot_with_historical_budget_exit_metadata()),
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["ai", "conversation", "show", "563", "--json"],
    )

    assert result.exit_code == 0
    assert '"execution_path": "fast"' in result.output
    assert '"budget_exit_reason": "completion_budget_exceeded"' in result.output
    assert '"partial_exit_reason": "completion_budget_exceeded"' in result.output
    assert '"intent_id": "intent-1"' in result.output


def test_ai_conversation_show_json_prefers_completed_turn_record_over_stale_budget_failure_projection(
    monkeypatch,
) -> None:
    from app.cli import cli

    monkeypatch.setattr(
        "app.cli._run_async",
        _return_value(
            _sample_snapshot_with_completed_turn_and_stale_budget_failure_projection()
        ),
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["ai", "conversation", "show", "2260", "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    diagnostics = payload["data"]["diagnostics"]
    assert diagnostics["source"] == "assistant_turn_record"
    assert diagnostics["turn_outcome"] == "success"
    assert diagnostics["conversation_outcome"] == "success"
    assert diagnostics["termination_reason"] == "completed"
    assert diagnostics["final_output_source"] == "assistant"
    assert diagnostics["budget_status"] == "exited"
    assert diagnostics["budget_exit_reason"] == "elapsed_budget_exceeded"
    assert diagnostics.get("failure_kind") is None


def test_ai_conversation_show_json_scrubs_context_source_polluted_turn_flow(
    monkeypatch,
) -> None:
    from app.cli import cli

    monkeypatch.setattr(
        "app.cli._run_async",
        _return_value(_sample_snapshot_with_context_source_polluted_turn_flow()),
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["ai", "conversation", "show", "2340", "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assistant = payload["data"]["recent_messages"][1]
    diagnostics = payload["data"]["diagnostics"]
    assert assistant["turn_flow"]["evidence"] == []
    assert assistant["turn_flow"]["answer_card"]["source_chip_ids"] == []
    assert assistant["metadata"]["turn_flow"]["evidence"] == []
    assert assistant["metadata"]["turn_flow"]["answer_card"]["source_chip_ids"] == []
    assert assistant["metadata"]["turn_record"]["turn_flow"]["evidence"] == []
    assert (
        assistant["metadata"]["turn_record"]["turn_flow"]["answer_card"][
            "source_chip_ids"
        ]
        == []
    )
    assert diagnostics["turn_record"]["turn_flow"]["evidence"] == []
    assert (
        diagnostics["turn_record"]["turn_flow"]["answer_card"]["source_chip_ids"] == []
    )
    output = json.dumps(payload, ensure_ascii=False)
    assert "Retrieved 3 sources" not in output
    assert '"source_count": 3' not in output


def test_ai_conversation_show_diagnostics_text_prefers_completed_turn_record_over_stale_budget_failure_projection(
    monkeypatch,
) -> None:
    from app.cli import cli

    monkeypatch.setattr(
        "app.cli._run_async",
        _return_value(
            _sample_snapshot_with_completed_turn_and_stale_budget_failure_projection()
        ),
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["ai", "conversation", "show", "2260", "--diagnostics-only"],
    )

    assert result.exit_code == 0
    assert (
        "source=assistant_turn_record outcome=success termination_reason=completed"
        in result.output
    )
    assert (
        "failure_kind=- budget_status=exited budget_exit_reason=elapsed_budget_exceeded"
        in result.output
    )
    assert (
        "outcome=failed termination_reason=elapsed_budget_exceeded" not in result.output
    )


def test_ai_conversation_show_json_falls_back_to_call_log_turn_record(
    monkeypatch,
) -> None:
    from app.cli import cli

    monkeypatch.setattr(
        "app.cli._run_async",
        _return_value(_sample_snapshot_with_call_log_turn_record_fallback()),
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["ai", "conversation", "show", "563", "--json"],
    )

    assert result.exit_code == 0
    assert '"source": "call_log_turn_record"' in result.output
    assert '"budget_exit_reason": "elapsed_budget_exceeded"' in result.output
    assert '"turn_record": {' in result.output
    assert '"budget_status": "exited"' in result.output
    assert '"tool_leak_detected": true' in result.output
    assert '"unfinished_intents": [' in result.output
    assert '"get_current_weather"' in result.output
    assert '"recovered_via_retry": true' in result.output
    assert '"contract_breach_type": "None"' not in result.output
    assert '"user_visible_label": "None"' not in result.output
    assert '"marker": "None"' not in result.output


def test_ai_conversation_show_text_omits_none_contract_breach_type(monkeypatch) -> None:
    from app.cli import cli

    monkeypatch.setattr(
        "app.cli._run_async",
        _return_value(_sample_snapshot_with_call_log_turn_record_fallback()),
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["ai", "conversation", "show", "563"],
    )

    assert result.exit_code == 0
    assert "Diagnostic: contract_breach_type=None" not in result.output
    assert "Turn diagnostics source: call_log_turn_record" in result.output
    assert (
        "Diagnostic: last assistant message looks like leaked textual tool call"
        in result.output
    )
    assert "Diagnostic: unfinished_intents=intent-1" in result.output
    assert "Diagnostic: recovered_via_retry=True" in result.output
    assert "None" not in result.output


def test_ai_conversation_show_text_normalizes_call_log_provider_failure_summary(
    monkeypatch,
) -> None:
    from app.cli import cli

    monkeypatch.setattr(
        "app.cli._run_async",
        _return_value(_sample_snapshot_with_call_log_provider_failure_metadata()),
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["ai", "conversation", "show", "563"],
    )

    assert result.exit_code == 0
    assert (
        "summary: outcome=failed termination_reason=provider_unavailable protocol_path=responses"
        in result.output
    )
    assert (
        "summary: outcome=failed termination_reason=error protocol_path=responses"
        not in result.output
    )


def test_ai_conversation_show_text_renders_diagnostic(monkeypatch) -> None:
    from app.cli import cli

    monkeypatch.setattr("app.cli._run_async", _return_value(_sample_snapshot()))

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["ai", "conversation", "show", "563", "--keyword", "对象存储对帐计费"],
    )

    assert result.exit_code == 0
    assert "Conversation #563" in result.output
    assert (
        "Diagnostic: last assistant message looks like leaked textual tool call"
        in result.output
    )
    assert "Diagnostic: contract_breach_type=leaked_textual_tool_call" in result.output
    assert (
        "Diagnostic: unfinished_intents=rail_ticket_research, workflow_summary"
        in result.output
    )
    assert "Diagnostic: recovered_via_retry=True" in result.output
    assert "type=main_chat" in result.output
    assert "crm_lookup" in result.output
    assert "对象存储对帐计费" in result.output


def test_ai_conversation_show_json_serializes_nested_datetimes(monkeypatch) -> None:
    from app.cli import cli

    monkeypatch.setattr(
        "app.cli._run_async",
        _return_value(_sample_snapshot_with_datetimes()),
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["ai", "conversation", "show", "563", "--json"],
    )

    assert result.exit_code == 0
    assert "2026-03-28T17:11:46+00:00" in result.output


def test_ai_conversation_show_text_handles_nested_datetimes(monkeypatch) -> None:
    from app.cli import cli

    monkeypatch.setattr(
        "app.cli._run_async",
        _return_value(_sample_snapshot_with_datetimes()),
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["ai", "conversation", "show", "563"],
    )

    assert result.exit_code == 0
    assert "seen_at" in result.output


def test_ai_root_cause_json_handles_missing_call_log(monkeypatch) -> None:
    from app.cli import cli
    from app.exceptions import NotFoundException

    async def _fake_operation(*args, **kwargs):
        raise NotFoundException(message="AI call log not found")

    monkeypatch.setattr("app.cli._run_ai_runtime_cli_operation", _fake_operation)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "ai",
            "root-cause",
            "--trace-id",
            "ae80b0c3-d043-4c09-8aff-1b8533b5b1c3",
            "--json",
        ],
    )

    assert result.exit_code == 1
    assert '"code": "ai_root_cause_not_found"' in result.output
    assert '"message": "AI call log not found"' in result.output


def test_ai_root_cause_enables_utf8_stdio(monkeypatch) -> None:
    from app.cli import cli

    events: list[str] = []

    async def _fake_operation(*args, **kwargs):
        assert events and events[0] == "utf8"
        events.append("operation")
        return {
            "status": "failed",
            "failure_layer": "post_processing",
            "cause_code": "incomplete_promissory_reply",
        }

    monkeypatch.setattr("app.cli._run_ai_runtime_cli_operation", _fake_operation)
    monkeypatch.setattr(
        "app.cli._ensure_utf8_stdio",
        lambda: events.append("utf8"),
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["ai", "root-cause", "--call-log-id", "3665", "--json"],
    )

    assert result.exit_code == 0
    assert events[0] == "utf8"
    assert "operation" in events
    assert '"cause_code": "incomplete_promissory_reply"' in result.output
