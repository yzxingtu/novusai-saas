"""中文: AI 真对话 smoke 服务结构与行为契约测试。

EN: Structural and behavioral contract tests for the AI real-dialogue smoke service.

Test type: structural / behavioral
Scope: RuntimeRealDialogueSmokeService report schema and AgentChatService plumbing.
Mocked dependencies: Agent resolution, AgentChatService transport, and call-log lookup.
Mock boundary: tests exercise smoke-service validation/report mapping; they do not
claim real-dialogue smoke acceptance or mock LLM output as a production pass.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.exceptions import BusinessException
from app.services.ai import runtime_real_dialogue_smoke_service as smoke_module
from app.services.ai.runtime_inventory_service import RuntimeInventoryService
from app.services.ai.runtime_real_dialogue_smoke_evidence import (
    build_required_tool_completion_evidence,
)
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


def _write_required_tool_ledger(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "# AI Real-Dialogue Smoke Scenarios",
                "scenario_id: `SCENARIO-003-required-tool-completion`",
                "priority: `must-pass`",
                "user_input: `查询 CRM 客户 Acme 的续费状态。`",
                "required_capabilities:",
                "  - CRM skill tool",
                "expected_observable_outcome: completed tool evidence",
            ]
        ),
        encoding="utf-8",
    )


def _required_tool_planner(*, completed: bool) -> dict[str, Any]:
    completed_names = ["get_customer_renewal_status"] if completed else []
    return {
        "intent": "crm_lookup",
        "family": "crm",
        "intent_plan": [
            {
                "intent_id": "intent-crm-1",
                "kind": "crm_lookup",
                "family": "crm",
                "status": "completed" if completed else "pending",
                "requires_tools": True,
                "allowed_tool_names": ["get_customer_renewal_status"],
                "completed_by_tool_names": completed_names,
            }
        ],
    }


def _write_secondary_required_tool_ledger(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "# AI Real-Dialogue Smoke Scenarios",
                "scenario_id: `SCENARIO-003-secondary-tool-required`",
                "priority: `must-pass`",
                "user_input: `查询 SKU-001 当前可售库存。`",
                "required_capabilities:",
                "  - inventory skill tool",
                "expected_observable_outcome: completed inventory tool evidence",
            ]
        ),
        encoding="utf-8",
    )


def _secondary_required_tool_planner(*, completed: bool) -> dict[str, Any]:
    completed_names = ["lookup_inventory_quantity"] if completed else []
    return {
        "intent": "inventory_lookup",
        "family": "inventory",
        "intent_plan": [
            {
                "intent_id": "intent-inventory-1",
                "kind": "inventory_lookup",
                "family": "inventory",
                "status": "completed" if completed else "pending",
                "requires_tools": True,
                "allowed_tool_names": ["lookup_inventory_quantity"],
                "completed_by_tool_names": completed_names,
            }
        ],
    }


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


def test_parse_smoke_ledger_keeps_wrapped_required_capabilities_scoped(
    tmp_path: Path,
) -> None:
    """Test type: behavioral.

    中文: 多行 required_capabilities 只解析自身列表，并拼接缩进续行。
    EN: Multiline required_capabilities parsing stays scoped to its own list and
    joins indented continuation lines.
    """

    ledger_path = tmp_path / "smoke-scenarios.md"
    ledger_path.write_text(
        "\n".join(
            [
                "# AI Real-Dialogue Smoke Scenarios",
                "- scenario_id: `SCENARIO-001-runtime-capability-smoke`",
                "- priority: `must-pass`",
                "- user_input: `说明一下这个系统的核心能力，并保持回答简洁。`",
                "- required_capabilities:",
                "  - Real provider credential configured for the selected agent.",
                "  - `python -m app.cli ai smoke --agent-id <id> --json` or",
                "    `python -m app.cli ai smoke --agent-code <code> --json` can resolve the",
                "    agent.",
                "- expected_observable_outcome:",
                "  - CLI exits with code `0`.",
                "  - Runtime diagnostics do not expose retired current-page tools.",
            ]
        ),
        encoding="utf-8",
    )

    ledger = smoke_module._parse_smoke_ledger(ledger_path)

    assert ledger.valid is True
    assert ledger.scenario_ids == ["SCENARIO-001-runtime-capability-smoke"]
    assert ledger.scenarios[0].required_capabilities == (
        "Real provider credential configured for the selected agent.",
        "python -m app.cli ai smoke --agent-id <id> --json` or "
        "python -m app.cli ai smoke --agent-code <code> --json` can resolve the agent.",
    )


def test_required_tool_completion_evidence_accepts_turn_completed_event() -> None:
    """Test type: behavioral.

    中文: requires_tools 意图可用 turn.tool_completed 诊断作为完成证据。
    EN: requires_tools intents can use turn.tool_completed diagnostics as
    completion evidence.
    """

    evidence = build_required_tool_completion_evidence(
        {
            "intent_plan": [
                {
                    "intent_id": "intent-inventory-1",
                    "kind": "inventory_lookup",
                    "requires_tools": True,
                    "allowed_tool_names": ["lookup_inventory_quantity"],
                    "completed_by_tool_names": [],
                }
            ],
        },
        {
            "events": [
                {
                    "kind": "turn.tool_completed",
                    "data": {"tool_name": "lookup_inventory_quantity", "success": True},
                }
            ]
        },
    )

    assert evidence["required"] is True
    assert evidence["passed"] is True
    assert evidence["matched_tool_names"] == ["lookup_inventory_quantity"]


def test_required_tool_completion_evidence_rejects_unrelated_tool_name() -> None:
    """Test type: behavioral.

    中文: 完成证据必须匹配 requires_tools 意图声明的工具名。
    EN: Completion evidence must match the tool names declared by the
    requires_tools intent.
    """

    evidence = build_required_tool_completion_evidence(
        {
            "intent_plan": [
                {
                    "intent_id": "intent-inventory-1",
                    "kind": "inventory_lookup",
                    "requires_tools": True,
                    "allowed_tool_names": ["lookup_inventory_quantity"],
                    "completed_by_tool_names": ["crm_lookup"],
                }
            ],
        }
    )

    assert evidence["required"] is True
    assert evidence["passed"] is False
    assert evidence["matched_tool_names"] == []
    assert evidence["completed_tool_names"] == ["crm_lookup"]


def test_required_tool_completion_evidence_rejects_global_completion_without_declared_name() -> (
    None
):
    """Test type: behavioral.

    中文: requires_tools 意图未声明工具名时，不能用全局任意完成事件假绿。
    EN: A requires_tools intent without declared tool names cannot pass via an
    arbitrary global completion event.
    """

    evidence = build_required_tool_completion_evidence(
        {
            "intent_plan": [
                {
                    "intent_id": "intent-crm-1",
                    "kind": "crm_lookup",
                    "requires_tools": True,
                    "completed_by_tool_names": [],
                }
            ],
        },
        {
            "events": [
                {
                    "kind": "turn.tool_completed",
                    "data": {"tool_name": "unrelated_tool", "success": True},
                }
            ]
        },
    )

    assert evidence["required"] is True
    assert evidence["passed"] is False
    assert evidence["matched_tool_names"] == []
    assert evidence["completed_tool_names"] == ["unrelated_tool"]


def test_required_tool_completion_evidence_rejects_intent_completion_without_declared_name() -> (
    None
):
    """Test type: behavioral.

    中文: requires_tools 意图未声明工具名时，不能用 intent 内任意完成工具自证通过。
    EN: A requires_tools intent without declared tool names cannot pass via an
    arbitrary intent-local completed tool name.
    """

    evidence = build_required_tool_completion_evidence(
        {
            "intent_plan": [
                {
                    "intent_id": "intent-crm-1",
                    "kind": "crm_lookup",
                    "requires_tools": True,
                    "completed_by_tool_names": ["arbitrary_tool"],
                }
            ],
        },
    )

    assert evidence["required"] is True
    assert evidence["passed"] is False
    assert evidence["matched_tool_names"] == []
    assert evidence["completed_tool_names"] == ["arbitrary_tool"]
    assert evidence["required_intents"][0]["missing_required_tool_names"] is True


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
async def test_real_dialogue_smoke_waits_past_old_short_call_log_window(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """中文: provider call log 在旧 10 次窗口后才可见时，smoke 仍等待到证据。

    EN: Smoke still waits for evidence when the provider call log appears after
    the former ten-attempt lookup window.
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
        if lookup_count <= 10:
            return None
        return SimpleNamespace(
            id=404,
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
    assert result["provider_call_log_id"] == 404
    assert result["provider_call_log_lookup_attempts"] == 11


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
async def test_real_dialogue_smoke_requires_tool_completion_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test type: behavioral.

    中文: requires_tools 意图需要工具时，非空回答不能替代工具完成证据。
    EN: When an intent requires tools, non-empty text cannot replace tool
    completion evidence.
    """

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
            tool_planner = _required_tool_planner(completed=False)
            return SimpleNamespace(
                conversation_id=101,
                message="Acme 的续费状态良好。",
                context_diagnostics={
                    "selected_tool_names": ["get_customer_renewal_status"],
                    "selected_skill_names": ["CRM Lookup"],
                    "tool_planner": tool_planner,
                },
                total_tokens=12,
                duration_ms=34,
                last_run_summary={"tool_planner": tool_planner},
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
    _write_required_tool_ledger(ledger)
    service = RuntimeRealDialogueSmokeService(db=object())

    report = await service.run(
        tenant_id=7,
        agent_id=59,
        agent_code=None,
        ledger_path=str(ledger),
        scenario_ids=["SCENARIO-003-required-tool-completion"],
        message=None,
        user_id=3,
        user_role="platform_admin",
        user_role_id=None,
        repo_root=None,
    )

    result = report["scenario_results"][0]
    assert report["overall_status"] == "failed"
    assert result["status"] == "failed"
    assert result["observable_checks"]["assistant_text_non_empty"] is True
    assert result["observable_checks"]["provider_call_succeeded"] is True
    assert result["observable_checks"]["required_tool_completion_evidence"] is False
    assert result["required_tool_completion_evidence"]["required"] is True
    assert result["required_tool_completion_evidence"]["matched_tool_names"] == []


@pytest.mark.asyncio
async def test_real_dialogue_smoke_fails_ledger_required_tool_without_planner_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test type: behavioral.

    中文: ledger 声明需要工具时，runtime 未产出 requires_tools 诊断也必须失败。
    EN: When the ledger declares a required tool capability, missing runtime
    requires_tools diagnostics must fail closed.
    """

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
                message="Acme 的续费状态良好。",
                context_diagnostics={
                    "selected_tool_names": ["get_customer_renewal_status"],
                    "selected_skill_names": ["CRM Lookup"],
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

    ledger = tmp_path / "smoke-scenarios.md"
    _write_required_tool_ledger(ledger)
    service = RuntimeRealDialogueSmokeService(db=object())

    report = await service.run(
        tenant_id=7,
        agent_id=59,
        agent_code=None,
        ledger_path=str(ledger),
        scenario_ids=["SCENARIO-003-required-tool-completion"],
        message=None,
        user_id=3,
        user_role="platform_admin",
        user_role_id=None,
        repo_root=None,
    )

    result = report["scenario_results"][0]
    assert report["overall_status"] == "failed"
    assert result["observable_checks"]["required_tool_completion_evidence"] is False
    assert result["required_tool_completion_evidence"]["required"] is True
    assert result["required_tool_completion_evidence"]["required_by_ledger"] is True


@pytest.mark.asyncio
async def test_real_dialogue_smoke_accepts_completed_by_tool_names(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test type: behavioral.

    中文: completed_by_tool_names 是 requires_tools smoke 的可接受完成证据。
    EN: completed_by_tool_names is acceptable completion evidence for
    requires_tools smoke.
    """

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
            tool_planner = _required_tool_planner(completed=True)
            return SimpleNamespace(
                conversation_id=101,
                message="Acme 的续费状态已通过 CRM 工具查询完成。",
                context_diagnostics={
                    "selected_tool_names": ["get_customer_renewal_status"],
                    "selected_skill_names": ["CRM Lookup"],
                    "tool_planner": tool_planner,
                },
                total_tokens=12,
                duration_ms=34,
                last_run_summary={"tool_planner": tool_planner},
            )

    async def fake_latest_call_log(self, **kwargs: Any):
        _ = self, kwargs
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

    ledger = tmp_path / "smoke-scenarios.md"
    _write_required_tool_ledger(ledger)
    service = RuntimeRealDialogueSmokeService(db=object())

    report = await service.run(
        tenant_id=7,
        agent_id=59,
        agent_code=None,
        ledger_path=str(ledger),
        scenario_ids=["SCENARIO-003-required-tool-completion"],
        message=None,
        user_id=3,
        user_role="platform_admin",
        user_role_id=None,
        repo_root=None,
    )

    result = report["scenario_results"][0]
    assert report["overall_status"] == "passed"
    assert result["status"] == "passed"
    assert result["observable_checks"]["required_tool_completion_evidence"] is True
    assert result["required_tool_completion_evidence"]["matched_tool_names"] == [
        "get_customer_renewal_status"
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("completed", "expected_status", "expected_passed", "expected_matched"),
    [
        (False, "failed", False, []),
        (True, "passed", True, ["lookup_inventory_quantity"]),
    ],
)
async def test_real_dialogue_smoke_generic_tool_intent_requires_completion_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    completed: bool,
    expected_status: str,
    expected_passed: bool,
    expected_matched: list[str],
) -> None:
    """Test type: behavioral.

    中文: requires_tools=true 的任意工具意图必须以工具完成证据判定。
    EN: Any tool intent with requires_tools=true must be judged by tool
    completion evidence.
    """

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
            tool_planner = _secondary_required_tool_planner(completed=completed)
            return SimpleNamespace(
                conversation_id=101,
                message="SKU-001 当前可售库存已通过工具查询完成。",
                context_diagnostics={
                    "selected_tool_names": ["lookup_inventory_quantity"],
                    "selected_skill_names": ["Inventory"],
                    "tool_planner": tool_planner,
                },
                total_tokens=12,
                duration_ms=34,
                last_run_summary={"tool_planner": tool_planner},
            )

    async def fake_latest_call_log(self, **kwargs: Any):
        _ = self, kwargs
        return SimpleNamespace(
            id=404,
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
    _write_secondary_required_tool_ledger(ledger)
    service = RuntimeRealDialogueSmokeService(db=object())

    report = await service.run(
        tenant_id=7,
        agent_id=59,
        agent_code=None,
        ledger_path=str(ledger),
        scenario_ids=["SCENARIO-003-secondary-tool-required"],
        message=None,
        user_id=3,
        user_role="platform_admin",
        user_role_id=None,
        repo_root=None,
    )

    result = report["scenario_results"][0]
    assert report["overall_status"] == expected_status
    assert result["observable_checks"]["required_tool_completion_evidence"] is (
        expected_passed
    )
    assert (
        result["required_tool_completion_evidence"]["matched_tool_names"]
        == expected_matched
    )


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
    assert report["command"]["exit_code"] == 2
    assert result["status"] == "failed"
    assert result["observable_checks"]["retired_current_page_or_online_search_exposed"]
    assert result["retired_capability_probe_values"]["context_diagnostics"][
        "provider_events"
    ] == [{"kind": "response.web_search_call.completed"}]


@pytest.mark.asyncio
async def test_real_dialogue_smoke_fails_required_tool_intent_without_completion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test type: behavioral.

    中文: 任意 requires_tools 意图都必须有工具完成证据。
    EN: Any requires_tools intent must have tool completion evidence.
    """

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
                message="我已经处理了这个企业查询请求。",
                context_diagnostics={
                    "selected_tool_names": ["crm_lookup"],
                    "selected_skill_names": ["CRM Lookup"],
                    "intent_plan": [
                        {
                            "intent_id": "intent-1",
                            "kind": "crm_lookup",
                            "requires_tools": True,
                            "allowed_tool_names": ["crm_lookup"],
                            "completed_by_tool_names": [],
                        }
                    ],
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
    assert result["observable_checks"]["required_tool_completion_evidence"] is False
    evidence = result["required_tool_completion_evidence"]
    assert evidence["required"] is True
    assert evidence["passed"] is False
    assert evidence["required_tool_names"] == ["crm_lookup"]
