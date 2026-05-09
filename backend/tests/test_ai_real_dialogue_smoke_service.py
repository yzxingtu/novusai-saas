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

from app.exceptions import BusinessException
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


def _write_capability_ledger(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "# AI Real-Dialogue Smoke Scenarios",
                "scenario_id: `SCENARIO-001-runtime-capability-smoke`",
                "priority: `must-pass`",
                "user_input: `说明一下这个系统的核心能力，并保持回答简洁。`",
                "required_capabilities: runtime smoke",
                "expected_observable_outcome: no blocking checks",
            ]
        ),
        encoding="utf-8",
    )


def _manifest_without_optional_skills_or_kb() -> dict[str, Any]:
    return {
        "summary": {
            "agent_name": "Smoke Agent",
            "tool_count": 1,
            "inventory_tool_count": 1,
            "skill_count": 0,
            "inventory_skill_count": 0,
            "selection_live": False,
        },
        "provider": {
            "id": 10,
            "code": "provider",
            "status": "available",
            "reason": None,
        },
        "model": {
            "id": 20,
            "code": "model",
            "status": "available",
            "reason": None,
        },
        "knowledge_bases": [],
        "memory": [{"name": "memory", "status": "available", "reason": None}],
    }


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


@pytest.mark.asyncio
async def test_real_dialogue_smoke_retries_retryable_provider_auth_block(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """中文: provider-backed smoke 的瞬时鉴权阻塞会重试并在报告留痕。

    EN: Provider-backed smoke retries transient auth blocks and records evidence.
    """
    call_count = 0

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
            _ = db, tenant_id

        async def chat(self, **kwargs: Any):
            nonlocal call_count
            _ = kwargs
            call_count += 1
            if call_count == 1:
                raise BusinessException(
                    message="认证失败，请检查 API Key 或登录状态",
                )
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
        _ = self, kwargs
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
    monkeypatch.setattr(smoke_module, "_SCENARIO_RETRY_DELAY_SECONDS", 0)

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

    result = report["scenario_results"][0]
    assert report["overall_status"] == "passed"
    assert result["status"] == "passed"
    assert result["retry_count"] == 1
    assert result["attempts"][0]["status"] == "blocked"
    assert result["attempts"][0]["error_type"] == "BusinessException"
    assert result["attempts"][1]["status"] == "passed"
    assert result["attempts"][1]["provider_call_log_id"] == 202


@pytest.mark.asyncio
async def test_real_dialogue_smoke_waits_for_async_call_log_visibility(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """中文: provider 已成功但异步 call log 稍后可见时，smoke 等待证据落库。

    EN: Smoke waits for durable evidence when async call logs become visible later.
    """
    lookup_count = 0

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
            _ = db, tenant_id

        async def chat(self, **kwargs: Any):
            _ = kwargs
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
        nonlocal lookup_count
        _ = self, kwargs
        lookup_count += 1
        if lookup_count == 1:
            return None
        return SimpleNamespace(
            id=303,
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
    monkeypatch.setattr(smoke_module, "_CALL_LOG_LOOKUP_DELAY_SECONDS", 0)

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

    result = report["scenario_results"][0]
    assert report["overall_status"] == "passed"
    assert result["provider_call_log_id"] == 303
    assert result["provider_call_log_lookup_attempts"] == 2


@pytest.mark.asyncio
async def test_real_dialogue_smoke_accepts_nonblocking_capability_degradation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_resolve_agent(
        self,
        *,
        tenant_id: int | None,
        agent_id: int | None,
        agent_code: str | None,
    ):
        del self, tenant_id, agent_code
        return SimpleNamespace(id=agent_id, name="Smoke Agent")

    async def fake_get_manifest(self, **kwargs: Any):
        del self, kwargs
        return _manifest_without_optional_skills_or_kb()

    class FakeAgentChatService:
        def __init__(self, db: Any, tenant_id: int) -> None:
            _ = db, tenant_id

        async def chat(self, **kwargs: Any):
            _ = kwargs
            return SimpleNamespace(
                conversation_id=101,
                message="系统核心能力包括企业级 AI 对话、权限治理和运行监控。",
                context_diagnostics={
                    "selected_tool_names": [],
                    "selected_skill_names": [],
                },
                total_tokens=12,
                duration_ms=34,
                last_run_summary={"finish": "ok"},
            )

    async def fake_latest_call_log(self, **kwargs: Any):
        _ = self, kwargs
        return SimpleNamespace(
            id=202,
            status="success",
            provider_name_snapshot="provider",
            model_name_snapshot="model",
            request_type="chat",
            call_type="main_chat",
        )

    monkeypatch.setattr(RuntimeInventoryService, "_resolve_agent", fake_resolve_agent)
    monkeypatch.setattr(RuntimeInventoryService, "get_manifest", fake_get_manifest)
    monkeypatch.setattr(smoke_module, "AgentChatService", FakeAgentChatService)
    monkeypatch.setattr(
        RuntimeRealDialogueSmokeService,
        "_latest_call_log",
        fake_latest_call_log,
    )

    ledger = tmp_path / "smoke-scenarios.md"
    _write_capability_ledger(ledger)
    service = RuntimeRealDialogueSmokeService(db=object())

    report = await service.run(
        tenant_id=7,
        agent_id=59,
        agent_code=None,
        ledger_path=str(ledger),
        scenario_ids=["SCENARIO-001-runtime-capability-smoke"],
        message=None,
        user_id=3,
        user_role="platform_admin",
        user_role_id=None,
        repo_root=None,
    )

    result = report["scenario_results"][0]
    assert report["overall_status"] == "passed"
    assert result["status"] == "passed"
    assert result["capability_smoke"]["overall_status"] == "yellow"
    assert result["capability_smoke"]["passed"] is True
    assert result["observable_checks"]["capability_smoke_green_or_passed"] is True
    nonblocking_reasons = {
        check["reason"]
        for check in result["capability_smoke"]["checks"]
        if not check["blocking"]
    }
    assert "no_runtime_skills_selected" in nonblocking_reasons
    assert "no_effective_knowledge_base_binding" in nonblocking_reasons


@pytest.mark.asyncio
async def test_real_dialogue_smoke_fails_on_retired_provider_search_diagnostics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
            _ = db, tenant_id

        async def chat(self, **kwargs: Any):
            _ = kwargs
            return SimpleNamespace(
                conversation_id=101,
                message="我不能联网搜索，请提供资料后我可以分析。",
                context_diagnostics={
                    "selected_tool_names": ["crm_lookup"],
                    "selected_skill_names": ["CRM Lookup"],
                    "candidate_tool_names": ["crm_lookup", "web_search"],
                    "provider_events": [{"kind": "response.web_search_call.completed"}],
                },
                total_tokens=12,
                duration_ms=34,
                last_run_summary={
                    "provider_events": [{"kind": "response.web_search_call.completed"}]
                },
            )

    async def fake_latest_call_log(self, **kwargs: Any):
        _ = self, kwargs
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

    result = report["scenario_results"][0]
    assert report["overall_status"] == "failed"
    assert result["status"] == "failed"
    assert result["observable_checks"]["retired_current_page_or_online_search_exposed"]
    assert result["retired_capability_probe_values"]["context_diagnostics"][
        "provider_events"
    ] == [{"kind": "response.web_search_call.completed"}]
