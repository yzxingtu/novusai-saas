from __future__ import annotations

from types import SimpleNamespace

from app.ai.context.assembly_result_support import (
    ContextDiagnosticsInputs,
    build_context_assembly_payload,
    build_context_diagnostics,
    merge_capability_finalization,
)
from app.ai.runtime.contracts import ContextCapabilityFinalization
from app.ai.runtime.types import CapabilityBundle
from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage


def test_merge_capability_finalization_diagnostics_includes_runtime_fields() -> None:
    base_diagnostics = {
        "context_budget": {"prompt_budget_exceeded": False},
        "capability_injection_decision": {"kb_injected": True},
    }
    finalization = ContextCapabilityFinalization(
        capability_bundle=CapabilityBundle(
            tools=[ToolDefinition(name="fetch_url", description="Fetch")]
        ),
        diagnostics={"selected_skill_names": ["Bridge Skill"]},
        capability_injection_decision={"skills_injected": True},
        runtime_manifest={"manifest": "bridge"},
        runtime_capability_summary="bridge-summary",
    )

    result = merge_capability_finalization(
        diagnostics=base_diagnostics,
        capability_finalization=finalization,
    )

    assert result.capability_bundle is finalization.capability_bundle
    assert result.capability_injection_decision == {"skills_injected": True}
    assert result.diagnostics["selected_skill_names"] == ["Bridge Skill"]
    assert result.diagnostics["runtime_capability_manifest"] == {
        "manifest": "bridge"
    }
    assert result.diagnostics["runtime_capability_summary"] == "bridge-summary"
    assert result.diagnostics["capability_injection_decision"] == {
        "skills_injected": True
    }


def test_build_context_assembly_payload_closes_fields() -> None:
    class _PruneStats:
        pruned_message_count = 2

        @staticmethod
        def to_dict() -> dict[str, int]:
            return {"pruned_message_count": 2}

    diagnostics = build_context_diagnostics(
        ContextDiagnosticsInputs(
            prune_stats=_PruneStats(),
            compaction_source_tokens=123,
            estimated_tokens_before_prune=220,
            estimated_tokens_after_prune=180,
            context_compacted=True,
            memory_recalled=True,
            web_research_date_anchor="2026-04-12",
            intent_plan=[SimpleNamespace(to_dict=lambda: {"kind": "web_research"})],
            intent_flags={"allow_memory_even_if_shortcircuit": True},
            dynamic_capability_awareness_enabled=True,
            capability_awareness_categories=["skills"],
            capability_awareness_error=None,
            requested_knowledge_base_ids=[1],
            effective_knowledge_base_ids=[1],
            dropped_knowledge_base_ids=[],
            context_budget={"prompt_target_tokens": 150},
            budget_usage={
                "used_tokens": 10,
                "trimmed_sections": ["memory"],
                "skipped_sections": [],
            },
            capability_injection_decision={"memory_injected": True},
        )
    )
    payload = build_context_assembly_payload(
        messages=[ChatMessage(role="assistant", content="done")],
        estimated_tokens=180,
        system_prompt_additions=["[MEMORY] ..."],
        diagnostics=diagnostics,
        rag_sources=[{"id": 1}],
        rag_source_kinds=["knowledge_base"],
        compact_summary="summary",
        prune_stats=_PruneStats(),
        memory_recall_slice={"count": 1},
        context_compacted=True,
        memory_recalled=True,
        capability_bundle=CapabilityBundle(),
    )

    assert payload.messages[0].content == "done"
    assert payload.estimated_tokens == 180
    assert payload.system_prompt_additions == ["[MEMORY] ..."]
    assert payload.diagnostics["context_budget"]["system_additions_used_tokens"] == 10
    assert payload.diagnostics["capability_injection_decision"] == {
        "memory_injected": True
    }
    assert payload.rag_sources == [{"id": 1}]
    assert payload.compact_summary == "summary"
    assert payload.prune_stats == {"pruned_message_count": 2}
    assert payload.memory_recall_slice == {"count": 1}
    assert payload.context_compacted is True
    assert payload.memory_recalled is True
