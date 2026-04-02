"""AI conversation CLI tests / AI 对话 CLI 测试。"""

from __future__ import annotations

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
            "title": "联网查询一下 小猫为什么 爱吃鱼",
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
                "content": "在本页面进行搜索  对象存储对帐计费",
                "tool_calls": None,
                "metadata": None,
            },
            {
                "id": 3235,
                "sequence": 18,
                "role": "assistant",
                "created_at": "2026-03-28T17:11:46+00:00",
                "content": "to=functions.get_page_context 天天中奖不json_string",
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
                "content": "在本页面进行搜索  对象存储对帐计费",
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
            "last_assistant_textual_tool_call_names": ["get_page_context"],
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


def test_ai_conversation_show_json_success(monkeypatch) -> None:
    from app.cli import cli

    monkeypatch.setattr("app.cli._run_async", _return_value(_sample_snapshot()))

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["ai", "conversation", "show", "563", "--keyword", "对象存储对帐计费", "--json"],
    )

    assert result.exit_code == 0
    assert '"id": 563' in result.output
    assert '"last_assistant_textual_tool_call_names": [' in result.output
    assert '"get_page_context"' in result.output


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
    assert "Diagnostic: last assistant message looks like leaked textual tool call" in result.output
    assert "type=main_chat" in result.output
    assert "get_page_context" in result.output
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
