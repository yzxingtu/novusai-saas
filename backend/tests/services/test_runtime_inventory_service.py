"""Test type: behavioral
Scope: Runtime inventory shaping from resolver-produced skill/tool facts.
Real dependencies: RuntimeCapabilityManifest DTOs and inventory support helpers.
Mocked dependencies: resolve_for_agent is patched only in the service-load sentinel.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ai.runtime.manifest import RuntimeCapabilityItem, RuntimeCapabilityManifest
from app.ai.runtime.types import CapabilityDescriptor
from app.ai.skills.resolver import SkillResolveIssue, SkillResolveResult
from app.ai.tools.types import ToolDefinition
from app.services.ai.runtime_diagnostics_support import RuntimeDiagnosticsCheckSupport
from app.services.ai.runtime_inventory_service_support import (
    build_empty_manifest,
    shape_manifest_payload,
)


@pytest.mark.asyncio
async def test_runtime_inventory_service_load_skill_result_reuses_resolve_for_agent():
    from app.services.ai.runtime_inventory_service import RuntimeInventoryService

    service = RuntimeInventoryService(MagicMock())
    agent = SimpleNamespace(id=7, owner_tenant_id=9)
    expected = SkillResolveResult()

    with patch(
        "app.services.ai.runtime_inventory_service.resolve_for_agent",
        new=AsyncMock(return_value=expected),
    ) as resolve_mock:
        result = await service._load_skill_result(agent=agent, tenant_id=9)

    assert result is expected
    resolve_mock.assert_awaited_once_with(
        db=service.db,
        agent=agent,
        tenant_id=9,
        request=None,
    )


def test_shape_manifest_payload_projects_skill_catalog_preview_metadata() -> None:
    manifest = RuntimeCapabilityManifest(
        scope="turn",
        tenant_id=9,
        agent_id=1,
        provider=None,
        model=None,
        tools=[
            RuntimeCapabilityItem(
                name="crm_lookup",
                kind="execution_tool",
                status="available",
                source="skill_resolver",
                metadata={"family": "data_ops"},
            )
        ],
        skills=[
            RuntimeCapabilityItem(
                name="Assistant Extension",
                kind="capability_pack",
                status="available",
                source="skill_resolver",
            )
        ],
        sources=[
            {
                "kind": "skill",
                "name": "skill_resolver",
                "active": True,
                "metadata": {
                    "turn_skill_activation_applied": True,
                    "turn_skill_activation_reason": "runtime_policy",
                },
            }
        ],
    )
    tool = ToolDefinition(
        name="crm_lookup",
        source_skill_id=901,
        source_skill_name="Assistant Extension",
        source_skill_type="toolkit",
        source_package_name="neutral.package",
        source_plugin="neutral-plugin",
    )
    skill_result = SkillResolveResult(
        tools=[tool],
        capability_descriptors=[
            CapabilityDescriptor(
                name="Assistant Extension",
                kind="capability_pack",
                source="skill_package:neutral.package",
                metadata={
                    "skill_id": 901,
                    "skill_type": "toolkit",
                    "package_name": "neutral.package",
                    "source_plugin": "neutral-plugin",
                    "resolved_tool_names": ["crm_lookup"],
                    "resolved_tool_count": 1,
                    "has_execution_tools": True,
                    "startup_preview_tool_names": ["crm_lookup"],
                    "startup_preview_semantic_families": ["data_ops"],
                },
            )
        ],
    )
    agent = SimpleNamespace(name="Support Agent", owner_tenant_id=9, model=None)

    payload = shape_manifest_payload(
        scope="runtime",
        tenant_id=9,
        agent=agent,
        manifest=manifest,
        kb_bindings=[],
        skill_result=skill_result,
        tools=[tool],
    )

    assert payload["skills"] == [
        {
            "name": "Assistant Extension",
            "kind": "capability_pack",
            "status": "available",
            "reason": None,
            "metadata": {
                "skill_id": 901,
                "skill_type": "toolkit",
                "package_name": "neutral.package",
                "source_plugin": "neutral-plugin",
                "resolved_tool_names": ["crm_lookup"],
                "resolved_tool_count": 1,
                "has_execution_tools": True,
                "startup_preview_tool_names": ["crm_lookup"],
                "startup_preview_semantic_families": ["data_ops"],
            },
            "source": "skill_package:neutral.package",
        }
    ]
    assert payload["extensions"] == [
        {
            "name": "neutral-plugin",
            "kind": "extension",
            "status": "available",
            "reason": None,
            "metadata": {
                "tool_names": ["crm_lookup"],
                "skill_names": ["Assistant Extension"],
                "package_names": ["neutral.package"],
                "startup_preview_tool_names": ["crm_lookup"],
                "startup_preview_semantic_families": ["data_ops"],
            },
            "source": "plugin_runtime",
        }
    ]
    assert payload["summary"]["turn_skill_activation_applied"] is True
    assert payload["summary"]["turn_skill_activation_reason"] == "runtime_policy"
    assert payload["summary"]["selection_semantics"] == "inventory_snapshot"
    assert payload["summary"]["selection_live"] is False
    assert payload["summary"]["live_turn_bound"] is False
    assert payload["boundaries"]["selection_semantics"] == "inventory_snapshot"
    assert payload["boundaries"]["selection_live"] is False
    assert payload["boundaries"]["live_turn_bound"] is False


def test_shape_manifest_payload_projects_web_research_from_inventory_snapshot() -> None:
    manifest = RuntimeCapabilityManifest(
        scope="turn",
        tenant_id=9,
        agent_id=1,
        provider=None,
        model=None,
        tools=[],
        skills=[],
        web_research=[
            RuntimeCapabilityItem(
                name="web_research",
                kind="execution_tool",
                status="unavailable",
                reason="web_research_tools_unavailable",
                metadata={"has_web_search": False, "has_fetch_url": False},
                source="tool_registry",
            )
        ],
        disabled_capabilities=[
            RuntimeCapabilityItem(
                name="web_research",
                kind="execution_tool",
                status="unavailable",
                reason="web_research_tools_unavailable",
                metadata={"has_web_search": False, "has_fetch_url": False},
                source="tool_registry",
            )
        ],
        sources=[
            {
                "kind": "skill",
                "name": "skill_resolver",
                "active": True,
                "metadata": {
                    "inventory_selected_tool_names": [
                        "get_current_time",
                        "web_search",
                        "fetch_url",
                    ],
                    "inventory_selected_skill_names": ["web_search"],
                    "turn_skill_activation_applied": False,
                    "turn_skill_activation_reason": None,
                },
            }
        ],
    )
    agent = SimpleNamespace(name="Search Agent", owner_tenant_id=9, model=None)

    payload = shape_manifest_payload(
        scope="runtime",
        tenant_id=9,
        agent=agent,
        manifest=manifest,
        kb_bindings=[],
        skill_result=SkillResolveResult(),
        tools=[],
    )

    web_research = payload["web_research"][0]
    assert web_research["status"] == "available"
    assert web_research["reason"] is None
    assert web_research["metadata"] == {
        "has_web_search": True,
        "has_fetch_url": True,
        "availability_basis": "inventory_selected_tools",
    }
    assert payload["disabled_capabilities"] == []
    assert payload["summary"]["web_research_pair_complete"] is True
    assert payload["summary"]["web_research_status"] == "available"
    assert payload["summary"]["inventory_selected_tool_names"] == [
        "get_current_time",
        "web_search",
        "fetch_url",
    ]
    assert payload["summary"]["inventory_selected_skill_names"] == ["web_search"]
    assert payload["summary"]["selection_live"] is False


def test_runtime_smoke_checks_use_inventory_counts_for_snapshot() -> None:
    checks = RuntimeDiagnosticsCheckSupport().build_manifest_checks(
        {
            "summary": {
                "tool_count": 0,
                "skill_count": 0,
                "inventory_tool_count": 3,
                "inventory_skill_count": 1,
                "selection_live": False,
            },
            "provider": {},
            "model": {},
            "web_research": [
                {
                    "name": "web_research",
                    "status": "available",
                    "reason": None,
                    "metadata": {
                        "has_web_search": True,
                        "has_fetch_url": True,
                    },
                }
            ],
            "memory": [],
            "knowledge_bases": [],
        },
        require_agent=False,
    )

    by_name = {check["name"]: check for check in checks}
    assert by_name["tools"]["status"] == "available"
    assert by_name["tools"]["metadata"] == {
        "tool_count": 0,
        "inventory_tool_count": 3,
        "selection_live": False,
    }
    assert by_name["skills"]["status"] == "available"
    assert by_name["skills"]["metadata"] == {
        "skill_count": 0,
        "inventory_skill_count": 1,
        "selection_live": False,
    }
    assert by_name["web_research_contract"]["status"] == "available"


def test_shape_manifest_payload_marks_plugin_extension_unavailable_from_resolution_issue() -> (
    None
):
    manifest = RuntimeCapabilityManifest(
        scope="turn",
        tenant_id=9,
        agent_id=1,
        provider=None,
        model=None,
        tools=[],
        skills=[
            RuntimeCapabilityItem(
                name="Assistant Extension",
                kind="capability_pack",
                status="available",
                source="skill_resolver",
            )
        ],
        sources=[],
    )
    issue = SkillResolveIssue(
        code="plugin_resolver_missing",
        message="Plugin 'neutral-plugin' resolver is unavailable",
        severity="error",
        skill_id=901,
        skill_name="Assistant Extension",
        skill_type="toolkit",
        package_name="neutral.package",
        source_plugin="neutral-plugin",
    )
    skill_result = SkillResolveResult(
        tools=[],
        resolution_issues=[issue],
        capability_descriptors=[
            CapabilityDescriptor(
                name="Assistant Extension",
                kind="capability_pack",
                source="skill_package:neutral.package",
                metadata={
                    "skill_id": 901,
                    "skill_type": "toolkit",
                    "package_name": "neutral.package",
                    "source_plugin": "neutral-plugin",
                    "startup_preview_tool_names": ["crm_lookup"],
                    "resolved_tool_names": [],
                    "resolved_tool_count": 0,
                    "has_execution_tools": False,
                    "resolution_status": "unavailable",
                    "resolution_reason": "plugin_resolver_missing",
                    "resolution_issues": [issue.to_dict()],
                },
            )
        ],
    )
    agent = SimpleNamespace(name="Support Agent", owner_tenant_id=9, model=None)

    payload = shape_manifest_payload(
        scope="runtime",
        tenant_id=9,
        agent=agent,
        manifest=manifest,
        kb_bindings=[],
        skill_result=skill_result,
        tools=[],
    )

    assert payload["skills"][0]["status"] == "unavailable"
    assert payload["skills"][0]["reason"] == "plugin_resolver_missing"
    assert payload["skills"][0]["metadata"]["resolution_issues"][0]["code"] == (
        "plugin_resolver_missing"
    )
    assert payload["extensions"] == [
        {
            "name": "neutral-plugin",
            "kind": "extension",
            "status": "unavailable",
            "reason": "plugin_resolver_missing",
            "metadata": {
                "tool_names": [],
                "skill_names": ["Assistant Extension"],
                "package_names": ["neutral.package"],
                "startup_preview_tool_names": ["crm_lookup"],
                "startup_preview_semantic_families": [],
                "resolution_issues": [issue.to_dict()],
            },
            "source": "plugin_runtime",
        }
    ]
    assert payload["summary"]["extension_names"] == ["neutral-plugin"]


def test_build_empty_manifest_marks_inventory_snapshot_as_non_live() -> None:
    payload = build_empty_manifest(
        scope="runtime",
        tenant_id=9,
        agent_code="support-agent",
    )

    assert payload["boundaries"]["selection_semantics"] == "inventory_snapshot"
    assert payload["boundaries"]["selection_live"] is False
    assert payload["boundaries"]["live_turn_bound"] is False
    assert payload["summary"]["selection_semantics"] == "inventory_snapshot"
    assert payload["summary"]["selection_live"] is False
    assert payload["summary"]["live_turn_bound"] is False
