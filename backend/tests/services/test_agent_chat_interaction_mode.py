"""Agent chat interaction mode contract tests / 交互模式契约测试."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_migration_module():
    migration_path = (
        Path(__file__).resolve().parents[2]
        / "migrations"
        / "versions"
        / "20260401_0012_collapse_interaction_modes.py"
    )
    spec = importlib.util.spec_from_file_location(
        "collapse_interaction_modes_migration",
        migration_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_agent_chat_request_ignores_removed_interaction_mode_field():
    from app.schemas.ai.agent_chat import AgentChatRequest

    request = AgentChatRequest(message="hello", interaction_mode="confirm")

    payload = request.model_dump(exclude_none=True)

    assert payload["message"] == "hello"
    assert "interaction_mode" not in payload


def test_interaction_mode_migration_normalizes_removed_values():
    migration = _load_migration_module()

    payload, changed = migration._normalize_dict_payload(  # noqa: SLF001
        {
            "interaction_mode": "observe",
            "interaction_mode_requested": "suggest",
            "interaction_mode_effective": "observe",
            "downgraded_from": "suggest",
        }
    )

    assert changed is True
    assert payload["interaction_mode"] == "trusted_auto"
    assert payload["interaction_mode_requested"] == "trusted_auto"
    assert payload["interaction_mode_effective"] == "trusted_auto"
    assert payload["downgraded_from"] == "trusted_auto"


def test_interaction_mode_migration_normalizes_confirm_to_trusted_auto():
    migration = _load_migration_module()

    payload, changed = migration._normalize_dict_payload(  # noqa: SLF001
        {
            "interaction_mode": "confirm",
            "interaction_mode_requested": "confirm",
            "interaction_mode_effective": "confirm",
            "downgraded_from": "confirm",
        }
    )

    assert changed is True
    assert payload["interaction_mode"] == "trusted_auto"
    assert payload["interaction_mode_requested"] == "trusted_auto"
    assert payload["interaction_mode_effective"] == "trusted_auto"
    assert payload["downgraded_from"] == "trusted_auto"


def test_interaction_mode_migration_keeps_trusted_auto():
    migration = _load_migration_module()

    payload, changed = migration._normalize_dict_payload(  # noqa: SLF001
        {
            "interaction_mode": "trusted_auto",
            "interaction_mode_requested": "trusted_auto",
            "interaction_mode_effective": "trusted_auto",
        }
    )

    assert changed is False
    assert payload["interaction_mode_effective"] == "trusted_auto"


def test_interaction_mode_migration_normalizes_nested_metadata_payloads():
    migration = _load_migration_module()

    payload, changed = migration._normalize_json_payload(  # noqa: SLF001
        {
            "context_diagnostics": {"interaction_mode_effective": "suggest"},
            "last_run_summary": {
                "interaction_mode_effective": "observe",
                "downgraded_from": "suggest",
            },
            "tool_calls": [
                {"pending_consent": {"tool_name": "web_search"}},
                {"interaction_mode_requested": "observe"},
            ],
        }
    )

    assert changed is True
    assert (
        payload["context_diagnostics"]["interaction_mode_effective"]
        == "trusted_auto"
    )
    assert payload["last_run_summary"]["interaction_mode_effective"] == "trusted_auto"
    assert payload["last_run_summary"]["downgraded_from"] == "trusted_auto"
    assert payload["tool_calls"][1]["interaction_mode_requested"] == "trusted_auto"
