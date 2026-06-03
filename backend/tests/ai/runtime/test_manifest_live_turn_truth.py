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
    support_tools = [
        _tool(
            "crm_lookup",
            skill_id=202,
            skill_name="CRM Skill",
            package_name="pkg.crm",
            plugin_name="plugin-crm",
            family="data_ops",
        ),
        _tool(
            "query_records",
            skill_id=202,
            skill_name="CRM Skill",
            package_name="pkg.crm",
            plugin_name="plugin-crm",
            family="data_ops",
        ),
    ]
    descriptors = [
        _descriptor(
            "CRM Skill",
            skill_id=202,
            package_name="pkg.crm",
            plugin_name="plugin-crm",
            resolved_tool_names=["crm_lookup", "query_records"],
        ),
    ]
    return CapabilityBundle(
        tools=list(support_tools),
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

    assert payload["summary"]["selected_skill_names"] == ["CRM Skill"]
    assert payload["summary"]["selection_semantics"] == "inventory_snapshot"
    assert payload["summary"]["selection_live"] is False
    assert payload["summary"]["live_turn_bound"] is False
    assert payload["boundaries"]["selection_semantics"] == "inventory_snapshot"
    assert payload["boundaries"]["selection_live"] is False
    assert payload["boundaries"]["live_turn_bound"] is False
    assert [item["name"] for item in payload["skills"]] == ["CRM Skill"]
    assert (
        resolve_live_turn_selected_skill_names(
            runtime_capability_summary=payload["summary"]
        )
        == []
    )
