"""Agent chat interaction mode contract tests / 交互模式契约测试."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import AsyncMock

import pytest


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


def test_agent_chat_request_rejects_removed_interaction_modes():
    from pydantic import ValidationError

    from app.schemas.ai.agent_chat import AgentChatRequest

    with pytest.raises(ValidationError):
        AgentChatRequest(message="hello", interaction_mode="observe")

    with pytest.raises(ValidationError):
        AgentChatRequest(message="hello", interaction_mode="suggest")


def test_agent_chat_request_accepts_supported_interaction_modes():
    from app.schemas.ai.agent_chat import AgentChatRequest

    confirm_request = AgentChatRequest(message="hello", interaction_mode="confirm")
    trusted_request = AgentChatRequest(
        message="hello",
        interaction_mode="trusted_auto",
    )

    assert confirm_request.interaction_mode == "confirm"
    assert trusted_request.interaction_mode == "trusted_auto"


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
    assert payload["interaction_mode"] == "confirm"
    assert payload["interaction_mode_requested"] == "confirm"
    assert payload["interaction_mode_effective"] == "confirm"
    assert payload["downgraded_from"] == "confirm"


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
    assert payload["context_diagnostics"]["interaction_mode_effective"] == "confirm"
    assert payload["last_run_summary"]["interaction_mode_effective"] == "confirm"
    assert payload["last_run_summary"]["downgraded_from"] == "confirm"
    assert payload["tool_calls"][1]["interaction_mode_requested"] == "confirm"


@pytest.mark.asyncio
async def test_resolve_interaction_mode_downgrades_trusted_auto_without_policy(
    mock_db,
):
    from app.services.ai.agent_chat_service import AgentChatService

    service = AgentChatService(mock_db, tenant_id=1)
    service._resolve_runtime_trust_policy_ref = AsyncMock(return_value=None)

    effective_mode, trust_policy_ref, downgrade_reason = await service._resolve_interaction_mode(
        requested_mode="trusted_auto",
        conversation_id=100,
        agent_id=1,
        operator_id=10,
        operator_type="tenant_admin",
        explicit_trust_policy_ref=None,
    )

    assert effective_mode == "confirm"
    assert trust_policy_ref is None
    assert downgrade_reason == "missing_runtime_trust_policy"
