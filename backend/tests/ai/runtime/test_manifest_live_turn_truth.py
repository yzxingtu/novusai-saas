"""
Test type: structural
Scope: WS1-PKG-03 manifest/live-turn truth ownership contract.
Real dependencies: AIRuntimeInventoryService, project_capability_bundle_to_tools,
and runtime_inventory_service_support run their real contract shaping logic.
Mocked dependencies: none; the tests use lightweight runtime payload objects.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.ai.engine.system_prompt_capability_hints import (
    resolve_live_turn_selected_skill_names,
)
from app.ai.runtime.context_assembler import ContextAssemblerState
from app.ai.runtime.manifest import AIRuntimeInventoryService
from app.ai.runtime.types import (
    CapabilityBundle,
    CapabilityDescriptor,
    ContextSource,
    project_capability_bundle_to_tools,
)
from app.ai.skills.resolver import SkillResolveResult
from app.ai.tools.types import ToolDefinition
from app.services.ai.runtime_inventory_service_support import shape_manifest_payload


def _tool(
    name: str,
    *,
    skill_id: int,
    skill_name: str,
    package_name: str,
    plugin_name: str,
    family: str,
) -> ToolDefinition:
    return ToolDefinition(
        name=name,
        description=f"{name} tool",
        source_skill_id=skill_id,
        source_skill_name=skill_name,
        source_skill_type="toolkit",
        source_package_name=package_name,
        source_plugin=plugin_name,
        semantic_family=family,
    )


def _descriptor(
    name: str,
    *,
    skill_id: int,
    package_name: str,
    plugin_name: str,
    resolved_tool_names: list[str],
) -> CapabilityDescriptor:
    return CapabilityDescriptor(
        name=name,
        kind="capability_pack",
        source=f"skill_package:{package_name}",
        metadata={
            "skill_id": skill_id,
            "skill_type": "toolkit",
            "package_name": package_name,
            "source_plugin": plugin_name,
            "resolved_tool_names": list(resolved_tool_names),
            "resolved_tool_count": len(resolved_tool_names),
            "has_execution_tools": True,
            "startup_preview_tool_names": list(resolved_tool_names),
        },
    )


def _inventory_bundle(*, activation_reason: str) -> CapabilityBundle:
    research_tools = [
        _tool(
            "web_search",
            skill_id=202,
            skill_name="Research Skill",
            package_name="pkg.research",
            plugin_name="plugin-research",
            family="web_research",
        ),
        _tool(
            "fetch_url",
            skill_id=202,
            skill_name="Research Skill",
            package_name="pkg.research",
            plugin_name="plugin-research",
            family="web_research",
        ),
    ]
    descriptors = [
        _descriptor(
            "Research Skill",
            skill_id=202,
            package_name="pkg.research",
            plugin_name="plugin-research",
            resolved_tool_names=["web_search", "fetch_url"],
        ),
    ]
    return CapabilityBundle(
        tools=list(research_tools),
        capability_descriptors=descriptors,
        context_sources=[
            ContextSource(
                kind="skill",
                name="skill_resolver",
                metadata={
                    "turn_skill_activation_applied": True,
                    "turn_skill_activation_reason": activation_reason,
                },
            ),
        ],
    )


def _turn_request() -> SimpleNamespace:
    return SimpleNamespace(
        tenant_id=9,
        input_variables={},
    )


def _turn_state() -> ContextAssemblerState:
    return ContextAssemblerState(
        knowledge_base_ids=[],
        requested_knowledge_base_ids=[],
        dropped_knowledge_base_ids=[],
        rag_sources=[],
        rag_source_kinds=[],
        memory_recalled=False,
        session_memory_injected=False,
        memory_recall_slice={},
        runtime_model_capabilities={},
    )


def _agent() -> SimpleNamespace:
    return SimpleNamespace(
        id=7,
        name="Support Agent",
        owner_tenant_id=9,
        model=None,
    )


def test_build_manifest_projects_live_subset_from_projected_bundle() -> None:
    inventory_bundle = _inventory_bundle(activation_reason="runtime_policy")
    live_bundle = project_capability_bundle_to_tools(
        inventory_bundle,
        [inventory_bundle.tools[0]],
    )
    assert live_bundle.selected_tool_names == ["web_search"]
    assert live_bundle.selected_skill_names == ["Research Skill"]
    assert live_bundle.inventory_selected_tool_names == [
        "web_search",
        "fetch_url",
    ]
    assert live_bundle.inventory_selected_skill_names == [
        "Research Skill",
    ]

    manifest = AIRuntimeInventoryService.build_manifest(
        agent=_agent(),
        request=_turn_request(),
        bundle=live_bundle,
        state=_turn_state(),
        capability_injection_decision={},
    )
    summary = AIRuntimeInventoryService.build_compact_summary(manifest)

    assert [item.name for item in manifest.tools] == ["web_search"]
    assert [item.name for item in manifest.skills] == ["Research Skill"]
    assert manifest.boundaries["selection_semantics"] == "turn_selected_subset"
    assert manifest.boundaries["selection_live"] is True
    assert manifest.boundaries["live_turn_bound"] is True
    assert summary["selected_skill_names"] == ["Research Skill"]
    assert summary.get("page_context_attached", False) is False
    assert summary.get("page_operation_names", []) == []
    assert "page_ops" not in summary["tool_families"]
    assert "page_ops" not in summary["continuation_capable_families"]
    assert summary["selection_semantics"] == "turn_selected_subset"
    assert summary["selection_live"] is True
    assert summary["live_turn_bound"] is True
    assert resolve_live_turn_selected_skill_names(
        runtime_capability_summary=summary
    ) == ["Research Skill"]


def test_build_manifest_marks_capability_reporting_inventory_as_non_live() -> None:
    inventory_bundle = _inventory_bundle(
        activation_reason="capability_reporting_query"
    )
    assert inventory_bundle.selected_skill_names == []
    assert inventory_bundle.inventory_selected_tool_names == [
        "web_search",
        "fetch_url",
    ]
    assert inventory_bundle.inventory_selected_skill_names == [
        "Research Skill",
    ]

    manifest = AIRuntimeInventoryService.build_manifest(
        agent=_agent(),
        request=_turn_request(),
        bundle=inventory_bundle,
        state=_turn_state(),
        capability_injection_decision={},
    )
    summary = AIRuntimeInventoryService.build_compact_summary(manifest)

    assert [item.name for item in manifest.tools] == [
        "web_search",
        "fetch_url",
    ]
    assert [item.name for item in manifest.skills] == []
    assert manifest.boundaries["selection_semantics"] == (
        "capability_reporting_inventory"
    )
    assert manifest.boundaries["selection_live"] is False
    assert manifest.boundaries["live_turn_bound"] is False
    assert summary["selected_skill_names"] == []
    assert summary.get("page_context_attached", False) is False
    assert summary.get("page_operation_names", []) == []
    assert "page_ops" not in summary["tool_families"]
    assert "page_ops" not in summary["continuation_capable_families"]
    assert summary["selection_semantics"] == "capability_reporting_inventory"
    assert summary["selection_live"] is False
    assert summary["live_turn_bound"] is False
    assert resolve_live_turn_selected_skill_names(
        runtime_capability_summary=summary
    ) == []


def test_shape_manifest_payload_rewrites_live_manifest_as_inventory_snapshot() -> None:
    inventory_bundle = _inventory_bundle(activation_reason="runtime_policy")
    live_bundle = project_capability_bundle_to_tools(
        inventory_bundle,
        [inventory_bundle.tools[0]],
    )
    manifest = AIRuntimeInventoryService.build_manifest(
        agent=_agent(),
        request=_turn_request(),
        bundle=live_bundle,
        state=_turn_state(),
        capability_injection_decision={},
    )
    skill_result = SkillResolveResult(
        tools=list(inventory_bundle.tools),
        capability_descriptors=list(inventory_bundle.capability_descriptors),
    )

    payload = shape_manifest_payload(
        scope="runtime",
        tenant_id=9,
        agent=_agent(),
        manifest=manifest,
        kb_bindings=[],
        skill_result=skill_result,
        tools=list(inventory_bundle.tools),
    )

    assert payload["summary"]["selected_skill_names"] == ["Research Skill"]
    assert payload["summary"]["selection_semantics"] == "inventory_snapshot"
    assert payload["summary"]["selection_live"] is False
    assert payload["summary"]["live_turn_bound"] is False
    assert payload["boundaries"]["selection_semantics"] == "inventory_snapshot"
    assert payload["boundaries"]["selection_live"] is False
    assert payload["boundaries"]["live_turn_bound"] is False
    assert [item["name"] for item in payload["skills"]] == ["Research Skill"]
    assert resolve_live_turn_selected_skill_names(
        runtime_capability_summary=payload["summary"]
    ) == []
