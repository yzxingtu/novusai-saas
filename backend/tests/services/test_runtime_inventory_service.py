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
