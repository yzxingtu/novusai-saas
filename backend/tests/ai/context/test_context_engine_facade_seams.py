from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ai.context.engine import ConversationContextEngine
from app.ai.engine.types import ExecutionRequest, ResearchContinuationContext
from app.ai.runtime.contracts import (
    ContextCapabilityAwareness,
    ContextCapabilityFinalization,
)
from app.ai.runtime.types import CapabilityBundle
from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage


class _BaseEngineStub:
    @staticmethod
    def _build_system_message(agent, input_variables=None):
        _ = agent, input_variables
        return ChatMessage(role="system", content="system")

    @staticmethod
    def _build_web_research_continuation_context(
        messages, all_tools, input_variables=None
    ):
        _ = messages, all_tools, input_variables
        return ResearchContinuationContext()


def _build_context_engine() -> ConversationContextEngine:
    return ConversationContextEngine(
        db=MagicMock(),
        base_engine=_BaseEngineStub(),
    )


def test_append_budgeted_addition_uses_engine_trim_facade() -> None:
    engine = _build_context_engine()
    additions: list[str] = []
    budget_usage = {
        "used_tokens": 0,
        "trimmed_sections": [],
        "skipped_sections": [],
    }

    with patch.object(
        engine,
        "_trim_text_to_token_limit",
        return_value="trimmed by facade",
    ) as trim_text:
        engine._append_budgeted_addition(
            additions=additions,
            text="very long text " * 30,
            category="test_block",
            per_item_token_limit=12,
            total_token_limit=200,
            budget_usage=budget_usage,
        )

    trim_text.assert_called_once()
    assert additions == ["trimmed by facade"]


@pytest.mark.asyncio
async def test_compact_messages_if_needed_uses_engine_summary_facade() -> None:
    engine = _build_context_engine()
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        conversation_id=42,
        messages=[],
        input_variables={},
    )
    messages = [
        ChatMessage(role="system", content="system"),
        ChatMessage(role="user", content="第一轮用户消息，需要被压缩。"),
        ChatMessage(role="assistant", content="第一轮助手回复，也足够长。"),
        ChatMessage(role="user", content="第二轮继续追问。"),
        ChatMessage(role="assistant", content="最近一轮助手回复。"),
    ]

    with (
        patch.object(
            engine,
            "_build_compact_summary",
            return_value="Facade summary",
        ) as build_compact_summary,
        patch.object(
            engine,
            "_persist_compaction_snapshot",
            new=AsyncMock(),
        ) as persist_snapshot,
    ):
        await engine._compact_messages_if_needed(
            request=request,
            context_config={
                "compact_threshold_tokens": 10,
                "compact_keep_last_assistants": 1,
                "compact_max_summary_chars": 300,
            },
            messages=messages,
        )

    build_compact_summary.assert_called_once()
    persist_snapshot.assert_awaited_once()
    kwargs = persist_snapshot.await_args.kwargs
    assert kwargs["request"] == request
    assert kwargs["summary"] == "Facade summary"
    assert kwargs["source_message_count"] == 3
    assert kwargs["source_token_estimate"] > 0


@pytest.mark.asyncio
async def test_context_engine_uses_capability_bridge_provisional_bundle() -> None:
    provisional_bundle = CapabilityBundle(
        tools=[ToolDefinition(name="web_search", description="Search")]
    )
    finalization = ContextCapabilityFinalization(
        capability_bundle=CapabilityBundle(),
        diagnostics={},
        capability_injection_decision={},
        runtime_manifest={},
        runtime_capability_summary="",
    )
    bridge = SimpleNamespace(
        resolve_runtime_model_capabilities=AsyncMock(
            return_value={"supports_vision": True}
        ),
        build_provisional_bundle=MagicMock(return_value=provisional_bundle),
        compute_awareness=AsyncMock(
            return_value=ContextCapabilityAwareness(enabled=False)
        ),
        finalize_capabilities=AsyncMock(return_value=finalization),
    )
    agent = SimpleNamespace(id=1, rag_config=None, context_config=None)
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        messages=[ChatMessage(role="user", content="hi")],
        input_variables={},
    )
    captured: dict[str, object] = {}

    def _plan_turn(*, capability_bundle, **_kwargs):
        captured["capability_bundle"] = capability_bundle
        return []

    with (
        patch("app.ai.context.engine.get_context_capability_bridge", return_value=bridge),
        patch(
            "app.ai.rag_injector.load_agent_kb_bindings",
            new=AsyncMock(return_value=([], {})),
        ),
        patch("app.ai.engine.intent_planner.IntentPlanner.plan_turn", _plan_turn),
    ):
        engine = _build_context_engine()
        engine.rag_contributor.contribute = AsyncMock(
            return_value=SimpleNamespace(
                messages=None,
                rag_sources=[],
                rag_source_kinds=[],
                kb_injected=False,
            )
        )
        engine.memory_contributor.contribute = AsyncMock(
            return_value=SimpleNamespace(
                memory_recalled=False,
                memory_recall_slice=None,
                memory_injected=False,
            )
        )
        await engine.assemble(agent, request, skill_result=None)

    bridge.resolve_runtime_model_capabilities.assert_awaited_once()
    bridge.build_provisional_bundle.assert_called_once()
    assert captured["capability_bundle"] is provisional_bundle
    assert (
        bridge.build_provisional_bundle.call_args.kwargs["capability_inputs"].runtime_model_capabilities
        == {"supports_vision": True}
    )


@pytest.mark.asyncio
async def test_context_engine_uses_local_kb_binding_loader_seam() -> None:
    bridge = SimpleNamespace(
        resolve_runtime_model_capabilities=AsyncMock(return_value={}),
        build_provisional_bundle=MagicMock(return_value=CapabilityBundle()),
        compute_awareness=AsyncMock(
            return_value=ContextCapabilityAwareness(enabled=False)
        ),
        finalize_capabilities=AsyncMock(
            return_value=ContextCapabilityFinalization(
                capability_bundle=CapabilityBundle(),
                diagnostics={},
                capability_injection_decision={},
                runtime_manifest={},
                runtime_capability_summary="",
            )
        ),
    )
    agent = SimpleNamespace(id=11, rag_config=None, context_config=None)
    request = ExecutionRequest(
        agent_id=11,
        tenant_id=7,
        user_id=5,
        messages=[ChatMessage(role="user", content="hi")],
        input_variables={},
    )

    with (
        patch("app.ai.context.engine.get_context_capability_bridge", return_value=bridge),
        patch(
            "app.ai.context.engine.load_agent_kb_bindings",
            new=AsyncMock(return_value=([], {})),
        ) as kb_loader,
        patch("app.ai.engine.intent_planner.IntentPlanner.plan_turn", return_value=[]),
    ):
        engine = _build_context_engine()
        engine.rag_contributor.contribute = AsyncMock(
            return_value=SimpleNamespace(
                messages=None,
                rag_sources=[],
                rag_source_kinds=[],
                kb_injected=False,
            )
        )
        engine.memory_contributor.contribute = AsyncMock(
            return_value=SimpleNamespace(
                memory_recalled=False,
                memory_recall_slice=None,
                memory_injected=False,
            )
        )
        await engine.assemble(agent, request, skill_result=None)

    kb_loader.assert_awaited_once()
    assert kb_loader.await_args.args == (engine.db, agent.id, request.tenant_id)


@pytest.mark.asyncio
async def test_context_engine_prefers_capability_bridge_finalization_outputs() -> None:
    final_bundle = CapabilityBundle(
        tools=[ToolDefinition(name="fetch_url", description="Fetch")]
    )
    finalization = ContextCapabilityFinalization(
        capability_bundle=final_bundle,
        diagnostics={"selected_skill_names": ["Bridge Skill"]},
        capability_injection_decision={"skills_injected": True},
        runtime_manifest={"manifest": "bridge"},
        runtime_capability_summary="bridge-summary",
    )
    bridge = SimpleNamespace(
        resolve_runtime_model_capabilities=AsyncMock(return_value={}),
        build_provisional_bundle=MagicMock(return_value=CapabilityBundle()),
        compute_awareness=AsyncMock(
            return_value=ContextCapabilityAwareness(enabled=True, categories=["skills"])
        ),
        finalize_capabilities=AsyncMock(return_value=finalization),
    )
    agent = SimpleNamespace(id=1, rag_config=None, context_config=None)
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        messages=[ChatMessage(role="user", content="hi")],
        input_variables={},
    )

    with (
        patch("app.ai.context.engine.get_context_capability_bridge", return_value=bridge),
        patch(
            "app.ai.rag_injector.load_agent_kb_bindings",
            new=AsyncMock(return_value=([], {})),
        ),
        patch("app.ai.engine.intent_planner.IntentPlanner.plan_turn", return_value=[]),
    ):
        engine = _build_context_engine()
        engine.rag_contributor.contribute = AsyncMock(
            return_value=SimpleNamespace(
                messages=None,
                rag_sources=[],
                rag_source_kinds=[],
                kb_injected=False,
            )
        )
        engine.memory_contributor.contribute = AsyncMock(
            return_value=SimpleNamespace(
                memory_recalled=False,
                memory_recall_slice=None,
                memory_injected=False,
            )
        )
        assembly = await engine.assemble(agent, request, skill_result=None)

    bridge.compute_awareness.assert_awaited_once()
    bridge.finalize_capabilities.assert_awaited_once()
    assert assembly.capability_bundle is final_bundle
    assert assembly.diagnostics["selected_skill_names"] == ["Bridge Skill"]
    assert assembly.diagnostics["runtime_capability_manifest"] == {"manifest": "bridge"}
    assert assembly.diagnostics["runtime_capability_summary"] == "bridge-summary"
    assert assembly.diagnostics["capability_injection_decision"] == {
        "skills_injected": True
    }
    assert assembly.diagnostics["dynamic_capability_awareness_enabled"] is True
