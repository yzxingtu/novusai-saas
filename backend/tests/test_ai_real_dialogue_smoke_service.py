"""中文: AI 真对话 smoke 服务结构契约测试。

EN: Structural contract tests for the AI real-dialogue smoke service.

Test type: structural
Scope: RuntimeRealDialogueSmokeService report schema and AgentChatService plumbing.
Mocked dependencies: Agent resolution, AgentChatService transport, and call-log lookup.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.services.ai import runtime_real_dialogue_smoke_service as smoke_module
from app.services.ai.runtime_inventory_service import RuntimeInventoryService
from app.services.ai.runtime_real_dialogue_smoke_service import (
    AI_REAL_DIALOGUE_SMOKE_EXECUTION_KIND,
    RuntimeRealDialogueSmokeService,
)


def _write_ledger(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "# AI Real-Dialogue Smoke Scenarios",
                "scenario_id: `SCENARIO-002-short-answer-real-turn`",
                "priority: `must-pass`",
                "user_input: `用两句话介绍 NovusAI SaaS 当前适合企业使用的能力。`",
                "required_capabilities: provider",
                "expected_observable_outcome: concise enterprise SaaS answer",
            ]
        ),
        encoding="utf-8",
    )


@pytest.mark.asyncio
async def test_real_dialogue_smoke_service_calls_agent_chat_with_smoke_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    async def fake_resolve_agent(
        self,
        *,
        tenant_id: int | None,
        agent_id: int | None,
        agent_code: str | None,
    ):
        del self, tenant_id, agent_code
        return SimpleNamespace(id=agent_id, name="Smoke Agent")

    class FakeAgentChatService:
        def __init__(self, db: Any, tenant_id: int) -> None:
            captured["db"] = db
            captured["tenant_id"] = tenant_id

        async def chat(self, **kwargs: Any):
            captured["chat_kwargs"] = kwargs
            return SimpleNamespace(
                conversation_id=101,
                message="NovusAI SaaS 支持企业知识管理。它适合企业使用。",
                context_diagnostics={
                    "selected_tool_names": [],
                    "selected_skill_names": [],
                },
                total_tokens=12,
                duration_ms=34,
                last_run_summary={"finish": "ok"},
            )

    async def fake_latest_call_log(self, **kwargs: Any):
        captured["call_log_lookup"] = kwargs
        return SimpleNamespace(
            id=202,
            status="success",
            provider_name_snapshot="provider",
            model_name_snapshot="model",
            request_type="chat",
            call_type="main_chat",
        )

    monkeypatch.setattr(RuntimeInventoryService, "_resolve_agent", fake_resolve_agent)
    monkeypatch.setattr(smoke_module, "AgentChatService", FakeAgentChatService)
    monkeypatch.setattr(
        RuntimeRealDialogueSmokeService,
        "_latest_call_log",
        fake_latest_call_log,
    )

    ledger = tmp_path / "smoke-scenarios.md"
    _write_ledger(ledger)
    service = RuntimeRealDialogueSmokeService(db=object())

    report = await service.run(
        tenant_id=7,
        agent_id=59,
        agent_code=None,
        ledger_path=str(ledger),
        scenario_ids=["SCENARIO-002-short-answer-real-turn"],
        message=None,
        user_id=3,
        user_role="platform_admin",
        user_role_id=None,
        repo_root=None,
    )

    chat_kwargs = captured["chat_kwargs"]
    assert report["overall_status"] == "passed"
    assert report["provider"]["live_provider_call_count"] == 1
    assert report["provider"]["call_logs"][0]["call_type"] == "main_chat"
    assert chat_kwargs["agent_id"] == 59
    assert chat_kwargs["conversation_id"] is None
    assert chat_kwargs["variables"] == {
        "smoke_scenario_id": "SCENARIO-002-short-answer-real-turn",
        "smoke_execution_kind": AI_REAL_DIALOGUE_SMOKE_EXECUTION_KIND,
    }
    assert chat_kwargs["memory_source"] == "real_dialogue_smoke"
    assert chat_kwargs["interaction_mode"] == "trusted_auto"
    assert report["scenario_results"][0]["observable_checks"][
        "answer_enterprise_saas_relevant"
    ]
