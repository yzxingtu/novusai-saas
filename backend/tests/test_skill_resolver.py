"""Skill resolver tests focused on plugin integration / 针对插件集成的技能解析器测试。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ai.runtime.types import CapabilityDescriptor
from app.ai.skills.resolver import (
    SkillResolver,
    SkillResolveResult,
    enrich_skill_capability_descriptors_with_tools,
    resolve_for_agent,
)


@pytest.mark.asyncio
async def test_plugin_skill_without_registered_resolver_logs_warning(monkeypatch) -> None:
    """SkillResolver should skip plugin skills gracefully when no resolver is registered."""

    skill = SimpleNamespace(
        id=101,
        name="weather_tools",
        type="toolkit",
        package_id=77,
        config=None,
        timeout=30,
        is_active=True,
        is_deleted=False,
    )

    resolver = SkillResolver(db=None)
    resolver._load_source_plugins = AsyncMock(return_value={77: "weather-widget"})

    registry_stub = SimpleNamespace(
        get_plugin_skill_resolver=lambda _plugin_name: None
    )
    monkeypatch.setattr(
        "app.plugins.registry.ExtensionRegistry.get_instance",
        lambda: registry_stub,
    )

    result = SkillResolveResult()
    await resolver._resolve_plugin_skill(
        skill,
        config={},
        result=result,
        source_plugin="weather-widget",
    )

    assert result.tools == []


def test_selected_skill_names_merges_descriptor_and_tool_sources() -> None:
    result = SkillResolveResult(
        tools=[
            SimpleNamespace(source_skill_name="Weather Tool Skill"),
            SimpleNamespace(source_skill_name="Page Skill"),
        ],
        capability_descriptors=[
            CapabilityDescriptor(
                name="Page Skill",
                kind="capability_pack",
                source="skill_package:page",
            ),
            CapabilityDescriptor(
                name="Knowledge Skill",
                kind="capability_pack",
                source="skill_package:kb",
            ),
        ],
    )

    assert result.selected_skill_names == [
        "Page Skill",
        "Knowledge Skill",
        "Weather Tool Skill",
    ]


def test_enrich_skill_capability_descriptors_with_tools_attaches_tool_metadata() -> None:
    descriptors = [
        CapabilityDescriptor(
            name="Weather Skill",
            kind="capability_pack",
            source="skill_package:weather",
            metadata={"skill_id": 1},
        ),
        CapabilityDescriptor(
            name="Knowledge Skill",
            kind="capability_pack",
            source="skill_package:kb",
            metadata={"skill_id": 2},
        ),
    ]
    tools = [
        SimpleNamespace(
            name="get_current_weather",
            source_skill_name="Weather Skill",
        ),
        SimpleNamespace(
            name="get_weather_forecast",
            source_skill_name="Weather Skill",
        ),
    ]

    enrich_skill_capability_descriptors_with_tools(
        descriptors=descriptors,
        tools=tools,  # type: ignore[arg-type]
    )

    weather = descriptors[0].metadata
    kb = descriptors[1].metadata
    assert weather["resolved_tool_names"] == [
        "get_current_weather",
        "get_weather_forecast",
    ]
    assert weather["resolved_tool_count"] == 2
    assert weather["has_execution_tools"] is True
    assert weather["skill_id"] == 1
    assert kb["resolved_tool_names"] == []
    assert kb["resolved_tool_count"] == 0
    assert kb["has_execution_tools"] is False


def test_selected_skill_names_skips_descriptor_only_skills_without_execution_tools() -> (
    None
):
    result = SkillResolveResult(
        tools=[],
        capability_descriptors=[
            CapabilityDescriptor(
                name="Catalog Only Skill",
                kind="capability_pack",
                source="skill_package:catalog",
                metadata={"has_execution_tools": False},
            ),
            CapabilityDescriptor(
                name="Executable Skill",
                kind="capability_pack",
                source="skill_package:exec",
                metadata={"has_execution_tools": True},
            ),
        ],
    )

    assert result.selected_skill_names == ["Executable Skill"]


def test_build_params_from_schema_keeps_array_items_schema() -> None:
    params = SkillResolver._build_params_from_schema(
        {
            "type": "object",
            "properties": {
                "tenant_ids": {
                    "type": "array",
                    "description": "Tenant ids",
                    "items": {"type": "integer"},
                }
            },
            "required": ["tenant_ids"],
        }
    )

    assert len(params) == 1
    assert params[0].name == "tenant_ids"
    assert params[0].items == {"type": "integer"}


@pytest.mark.asyncio
async def test_resolve_for_agent_falls_back_to_time_tool_when_grants_filter_out() -> None:
    package = SimpleNamespace(
        id=77,
        name="weather-widget",
        is_active=False,
        is_deleted=False,
        valves_config=None,
    )
    skill = SimpleNamespace(
        id=101,
        name="weather_tools",
        type="toolkit",
        package_id=77,
        config=None,
        timeout=30,
        is_active=True,
        is_deleted=False,
        package=package,
    )
    grant = SimpleNamespace(
        enabled=True,
        is_deleted=False,
        skill=skill,
        config_override=None,
        default_consent_mode="auto",
        capability_consent_overrides=None,
    )
    result = MagicMock()
    result.scalars.return_value.all.return_value = [grant]
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)

    agent = SimpleNamespace(id=1, owner_tenant_id=9)

    resolved = await resolve_for_agent(db, agent, tenant_id=9)

    assert resolved is not None
    assert [tool.name for tool in resolved.tools] == ["get_current_time"]
    assert resolved.tool_consent_modes == {"get_current_time": "auto"}
    assert resolved.capability_descriptors[0].name == "get_current_time"


@pytest.mark.asyncio
async def test_resolve_for_agent_returns_time_tool_when_agent_has_no_grants() -> None:
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)

    agent = SimpleNamespace(id=1, owner_tenant_id=9)

    resolved = await resolve_for_agent(db, agent, tenant_id=9)

    assert resolved is not None
    assert [tool.name for tool in resolved.tools] == ["get_current_time"]
    assert resolved.tool_consent_modes == {"get_current_time": "auto"}
