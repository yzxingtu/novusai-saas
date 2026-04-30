"""Test type: behavioral
Scope: Skill resolver startup prefiltering, turn activation, and live selected-skill projection
Real dependencies: SkillResolveResult, activation helpers, runtime capability models
Mocked dependencies: SQLAlchemy execute stubs and resolver monkeypatches for grant-filter seams only
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ai.runtime.capabilities import CapabilityRegistry
from app.ai.runtime.types import CapabilityBundle, CapabilityDescriptor
from app.ai.skills.activation import (
    TurnSkillActivation,
    apply_turn_skill_activation,
    execution_tools_for_turn,
    resolve_startup_intent_flags,
)
from app.ai.skills.resolver import (
    SkillResolver,
    SkillResolveResult,
    enrich_skill_capability_descriptors_with_tools,
    resolve_for_agent,
)
from app.ai.tools.types import ToolDefinition


@pytest.mark.asyncio
async def test_plugin_skill_without_registered_resolver_falls_back_to_canonical_toolkit(
    monkeypatch,
) -> None:
    """Plugin-packaged toolkit skills should still resolve via canonical toolkit parsing."""

    skill = SimpleNamespace(
        id=101,
        name="weather_tools",
        type="toolkit",
        package_id=77,
        package=SimpleNamespace(
            id=77,
            name="weather-widget",
            source_plugin="weather-widget",
            is_active=True,
            is_deleted=False,
            valves_config=None,
        ),
        config=None,
        toolkit_content="""
class Tools:
    def get_current_weather(self, city: str) -> str:
        \"\"\"Get the current weather for a city.\"\"\"
        return city
""",
        timeout=30,
        is_active=True,
        is_deleted=False,
    )

    resolver = SkillResolver(db=None)
    resolver._load_source_plugins = AsyncMock(return_value={77: "weather-widget"})

    registry_stub = SimpleNamespace(get_plugin_skill_resolver=lambda _plugin_name: None)
    monkeypatch.setattr(
        "app.plugins.registry.ExtensionRegistry.get_instance",
        lambda: registry_stub,
    )

    result = await resolver.resolve([skill])

    assert [tool.name for tool in result.tools] == ["get_current_weather"]
    assert result.tools[0].source_skill_id == 101
    assert result.tools[0].source_skill_name == "weather_tools"
    assert result.tools[0].source_skill_type == "toolkit"
    assert result.tools[0].source_plugin == "weather-widget"


@pytest.mark.asyncio
async def test_plugin_skill_without_registered_resolver_falls_back_to_canonical_builtin(
    monkeypatch,
) -> None:
    """Plugin-packaged builtin skills should fall back to builtin tool resolution."""

    skill = SimpleNamespace(
        id=102,
        name="weather_builtin",
        type="builtin",
        package_id=88,
        package=SimpleNamespace(
            id=88,
            name="weather-widget",
            source_plugin="weather-widget",
            is_active=True,
            is_deleted=False,
            valves_config=None,
        ),
        config={
            "tools": [
                {
                    "name": "get_current_weather",
                    "description": "Fetch current weather",
                }
            ]
        },
        timeout=30,
        is_active=True,
        is_deleted=False,
    )

    resolver = SkillResolver(db=None)
    resolver._load_source_plugins = AsyncMock(return_value={88: "weather-widget"})

    registry_stub = SimpleNamespace(get_plugin_skill_resolver=lambda _plugin_name: None)
    monkeypatch.setattr(
        "app.plugins.registry.ExtensionRegistry.get_instance",
        lambda: registry_stub,
    )

    result = await resolver.resolve([skill])

    assert [tool.name for tool in result.tools] == ["get_current_weather"]
    assert result.tools[0].source_skill_id == 102
    assert result.tools[0].source_skill_name == "weather_builtin"
    assert result.tools[0].source_skill_type == "builtin"
    assert result.tools[0].source_plugin == "weather-widget"


@pytest.mark.asyncio
async def test_resolve_one_falls_back_to_toolkit_when_source_plugin_has_no_resolver(
    monkeypatch,
) -> None:
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
    registry_stub = SimpleNamespace(get_plugin_skill_resolver=lambda _plugin_name: None)
    monkeypatch.setattr(
        "app.plugins.registry.ExtensionRegistry.get_instance",
        lambda: registry_stub,
    )

    def _append_forecast_tool(*, skill, config, result):
        del skill, config
        result.tools.append(SimpleNamespace(name="get_weather_forecast"))

    resolver._resolve_toolkit = MagicMock(  # type: ignore[method-assign]
        side_effect=_append_forecast_tool
    )

    result = SkillResolveResult()
    await resolver._resolve_one(
        skill, config={}, result=result, source_plugin="weather-widget"
    )

    assert [tool.name for tool in result.tools] == ["get_weather_forecast"]
    resolver._resolve_toolkit.assert_called_once()


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


def test_enrich_skill_capability_descriptors_with_tools_attaches_tool_metadata() -> (
    None
):
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


def test_selected_skill_names_ignores_non_capability_pack_descriptors() -> None:
    result = SkillResolveResult(
        tools=[],
        capability_descriptors=[
            CapabilityDescriptor(
                name="Page Context Provider",
                kind="context_provider",
                source="request.page_context",
                metadata={"has_execution_tools": True},
            ),
            CapabilityDescriptor(
                name="Live Capability Pack",
                kind="capability_pack",
                source="skill_package:live",
                metadata={"has_execution_tools": True},
            ),
        ],
    )

    assert result.selected_skill_names == ["Live Capability Pack"]


def test_selected_skill_names_skips_auto_injected_runtime_builtins() -> None:
    result = SkillResolveResult(
        tools=[
            SimpleNamespace(
                source_skill_name="web_search",
                config={"auto_injected": True},
            ),
            SimpleNamespace(
                source_skill_name="Plugin Page Skill",
                config={},
            ),
        ],
        capability_descriptors=[
            CapabilityDescriptor(
                name="web_search",
                kind="capability_pack",
                source="system_baseline_builtin",
                metadata={
                    "auto_injected": True,
                    "has_execution_tools": True,
                },
            ),
            CapabilityDescriptor(
                name="Plugin Page Skill",
                kind="capability_pack",
                source="skill_package:plugin.page",
                metadata={"has_execution_tools": True},
            ),
        ],
    )

    assert result.selected_skill_names == ["Plugin Page Skill"]


def test_skill_resolve_result_keeps_inventory_truth_separate_from_live_activation() -> (
    None
):
    result = SkillResolveResult(
        tools=[
            SimpleNamespace(
                name="web_search",
                source_skill_name="Plugin Research Skill",
            ),
            SimpleNamespace(
                name="ui_get_snapshot",
                source_skill_name="Plugin Page Skill",
            ),
        ],
        inventory_selected_tool_names_override=[
            "web_search",
            "ui_get_snapshot",
        ],
        inventory_selected_skill_names_override=[
            "Plugin Research Skill",
            "Plugin Page Skill",
        ],
        turn_activation=TurnSkillActivation(
            applied=True,
            activated_tool_names=["ui_get_snapshot"],
            activated_skill_names=["Plugin Page Skill"],
            reason="runtime_policy",
        ),
    )

    assert result.inventory_selected_tool_names == [
        "web_search",
        "ui_get_snapshot",
    ]
    assert result.inventory_selected_skill_names == [
        "Plugin Research Skill",
        "Plugin Page Skill",
    ]
    assert result.selected_tool_names == ["ui_get_snapshot"]
    assert result.selected_skill_names == ["Plugin Page Skill"]


def test_selected_skill_names_skips_page_runtime_builtin_capability_truth() -> None:
    result = SkillResolveResult(
        tools=[
            SimpleNamespace(
                name="ui_get_snapshot",
                source_skill_name="ui_get_snapshot",
                config={},
            ),
            SimpleNamespace(
                name="ui_click",
                source_skill_name="page_runtime",
                config={},
            ),
            SimpleNamespace(
                name="ui_read_table",
                source_skill_name="Plugin Page Skill",
                source_skill_id=12,
                source_package_name="plugin.page",
                config={},
            ),
        ],
        capability_descriptors=[
            CapabilityDescriptor(
                name="ui_get_snapshot",
                kind="capability_pack",
                source="page_runtime",
                metadata={"has_execution_tools": True},
            ),
            CapabilityDescriptor(
                name="page_runtime",
                kind="capability_pack",
                source="request.page_context",
                metadata={"has_execution_tools": True},
            ),
            CapabilityDescriptor(
                name="Plugin Page Skill",
                kind="capability_pack",
                source="skill_package:plugin.page",
                metadata={"skill_id": 12, "has_execution_tools": True},
            ),
        ],
    )

    assert result.selected_skill_names == ["Plugin Page Skill"]


@pytest.mark.asyncio
async def test_resolver_does_not_materialize_platform_builtins_as_installable_skills() -> (
    None
):
    resolver = SkillResolver(db=None)
    resolver._load_source_plugins = AsyncMock(return_value={})
    skill = SimpleNamespace(
        id=131,
        name="platform_builtin_bundle",
        type="builtin",
        package_id=7131,
        package=SimpleNamespace(
            id=7131,
            name="platform-builtins",
            source_plugin=None,
            is_active=True,
            is_deleted=False,
            valves_config=None,
        ),
        config={
            "tools": [
                {"name": "ui_get_snapshot", "description": "Read current page"},
                {"name": "editor_ops", "description": "Edit rich text"},
                {"name": "web_search", "description": "Search the web"},
                {"name": "fetch_url", "description": "Fetch a URL"},
                {"name": "vendor_lookup", "description": "Lookup vendor data"},
            ]
        },
        input_schema=None,
        timeout=30,
        is_active=True,
        is_deleted=False,
    )

    result = await resolver.resolve([skill])

    assert [tool.name for tool in result.tools] == ["vendor_lookup"]
    assert result.tools[0].source_skill_name == "platform_builtin_bundle"


def test_enrich_skill_capability_descriptors_keeps_same_name_skills_isolated() -> None:
    descriptors = [
        CapabilityDescriptor(
            name="Shared Skill",
            kind="capability_pack",
            source="skill_package:plugin.alpha",
            metadata={"skill_id": 11},
        ),
        CapabilityDescriptor(
            name="Shared Skill",
            kind="capability_pack",
            source="skill_package:plugin.beta",
            metadata={"skill_id": 22},
        ),
    ]
    tools = [
        SimpleNamespace(
            name="alpha_lookup",
            source_skill_id=11,
            source_skill_name="Shared Skill",
            source_package_name="plugin.alpha",
        ),
        SimpleNamespace(
            name="beta_lookup",
            source_skill_id=22,
            source_skill_name="Shared Skill",
            source_package_name="plugin.beta",
        ),
    ]

    enrich_skill_capability_descriptors_with_tools(
        descriptors=descriptors,
        tools=tools,  # type: ignore[arg-type]
    )

    assert descriptors[0].metadata["resolved_tool_names"] == ["alpha_lookup"]
    assert descriptors[1].metadata["resolved_tool_names"] == ["beta_lookup"]


def test_capability_registry_keeps_same_name_skills_with_distinct_skill_ids() -> None:
    bundle = CapabilityBundle(
        capability_descriptors=[
            CapabilityDescriptor(
                name="Shared Skill",
                kind="capability_pack",
                source="skill_package:plugin.alpha",
                metadata={"skill_id": 11},
            )
        ]
    )

    CapabilityRegistry._merge_descriptors(
        bundle,
        [
            CapabilityDescriptor(
                name="Shared Skill",
                kind="capability_pack",
                source="skill_package:plugin.beta",
                metadata={"skill_id": 22},
            )
        ],
    )

    assert [
        descriptor.metadata.get("skill_id")
        for descriptor in bundle.capability_descriptors
    ] == [11, 22]


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


def test_apply_turn_skill_activation_tracks_explicit_tool_mentions() -> None:
    result = SkillResolveResult(
        tools=[
            SimpleNamespace(
                name="get_current_weather",
                source_skill_name="Weather Skill",
            ),
            SimpleNamespace(
                name="ui_get_snapshot",
                source_skill_name="Plugin Page Skill",
            ),
        ],
        capability_descriptors=[
            CapabilityDescriptor(
                name="Weather Skill",
                kind="capability_pack",
                source="skill_resolver",
            ),
            CapabilityDescriptor(
                name="Plugin Page Skill",
                kind="capability_pack",
                source="skill_resolver",
            ),
        ],
    )
    request = SimpleNamespace(
        messages=[
            SimpleNamespace(
                role="user",
                content="call get_current_weather and then ui_get_snapshot",
            )
        ]
    )

    apply_turn_skill_activation(
        skill_result=result,
        request=request,
        intent_flags=None,
    )

    assert result.turn_activation is not None
    assert result.turn_activation.reason == "explicit_tool_mention"
    assert result.turn_activation.activated_tool_names == [
        "get_current_weather",
        "ui_get_snapshot",
    ]
    assert result.turn_activation.activated_skill_names == [
        "Weather Skill",
        "Plugin Page Skill",
    ]


def test_apply_turn_skill_activation_ignores_retired_page_runtime_policy() -> (
    None
):
    result = SkillResolveResult(
        tools=[],
        capability_descriptors=[
            CapabilityDescriptor(
                name="Plugin Page Skill",
                kind="capability_pack",
                source="skill_package:plugin.page",
                metadata={"preview_semantic_families": ["page_ops"]},
            ),
            CapabilityDescriptor(
                name="Plugin Research Skill",
                kind="capability_pack",
                source="skill_package:plugin.research",
                metadata={"preview_semantic_families": ["web_research"]},
            ),
        ],
    )
    request = SimpleNamespace(
        messages=[SimpleNamespace(role="user", content="帮我看一下当前页面")],
        input_variables={
            "page_context": {
                "page_key": "admin.ai.dashboard",
                "ui_epoch": 3,
            }
        },
    )

    apply_turn_skill_activation(
        skill_result=result,
        request=request,
        intent_flags={"has_page_intent": True, "has_web_research_intent": False},
        allow_catalog_skill_activation=True,
    )

    assert result.turn_activation is not None
    assert result.turn_activation.applied is False
    assert result.turn_activation.reason == "no_turn_skill_activation"
    assert result.turn_activation.activated_tool_names == []
    assert result.turn_activation.activated_skill_names == []


def test_apply_turn_skill_activation_keeps_live_selection_execution_backed() -> None:
    result = SkillResolveResult(
        tools=[
            SimpleNamespace(
                name="get_current_weather",
                source_skill_name="Weather Skill",
            )
        ],
        capability_descriptors=[
            CapabilityDescriptor(
                name="Plugin Page Skill",
                kind="capability_pack",
                source="skill_package:plugin.page",
                metadata={
                    "preview_semantic_families": ["page_ops"],
                    "has_execution_tools": False,
                },
            ),
            CapabilityDescriptor(
                name="Weather Skill",
                kind="capability_pack",
                source="skill_package:weather",
                metadata={"has_execution_tools": True},
            ),
        ],
    )
    request = SimpleNamespace(
        messages=[SimpleNamespace(role="user", content="帮我看一下当前页面")],
        input_variables={
            "page_context": {
                "page_key": "admin.ai.dashboard",
                "ui_epoch": 3,
            }
        },
    )

    apply_turn_skill_activation(
        skill_result=result,
        request=request,
        intent_flags={"has_page_intent": True, "has_web_research_intent": False},
    )

    assert result.turn_activation is not None
    assert result.turn_activation.applied is False
    assert result.turn_activation.reason == "no_turn_skill_activation"
    assert result.turn_activation.activated_tool_names == []
    assert result.turn_activation.activated_skill_names == []
    assert result.selected_skill_names == ["Weather Skill"]
    assert [tool.name for tool in execution_tools_for_turn(result)] == [
        "get_current_weather"
    ]


def test_resolve_startup_intent_flags_require_live_page_runtime_state() -> None:
    request = SimpleNamespace(
        messages=[SimpleNamespace(role="user", content="帮我看一下当前页面")],
        input_variables={
            "page_context": {
                "page_key": "admin.ai.dashboard",
            }
        },
    )

    flags = resolve_startup_intent_flags(request)

    assert flags["has_page_intent"] is False
    assert flags["has_web_research_intent"] is False


def _make_runtime_skill(
    *,
    skill_id: int,
    name: str,
    skill_type: str,
    package_name: str,
    source_plugin: str | None = None,
    config: dict | None = None,
) -> SimpleNamespace:
    package = SimpleNamespace(
        id=skill_id + 1000,
        name=package_name,
        source_plugin=source_plugin,
        valves_config=None,
        is_active=True,
        is_deleted=False,
    )
    return SimpleNamespace(
        id=skill_id,
        name=name,
        type=skill_type,
        package_id=package.id,
        config=config,
        timeout=30,
        is_active=True,
        is_deleted=False,
        package=package,
    )


def _make_grant(skill: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(
        enabled=True,
        is_deleted=False,
        skill=skill,
        config_override=None,
        default_consent_mode="auto",
        capability_consent_overrides=None,
    )


@pytest.mark.asyncio
async def test_resolve_for_agent_falls_back_to_baseline_builtins_when_grants_filter_out() -> (
    None
):
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
    assert [tool.name for tool in resolved.tools] == [
        "get_current_time",
        "web_search",
        "fetch_url",
    ]
    assert resolved.tool_consent_modes == {
        "get_current_time": "auto",
        "web_search": "auto",
        "fetch_url": "auto",
    }
    assert resolved.capability_descriptors[0].name == "get_current_time"


@pytest.mark.asyncio
async def test_resolve_for_agent_prefilters_explicit_skill_mentions_before_resolve(
    monkeypatch,
) -> None:
    plugin_page_skill = _make_runtime_skill(
        skill_id=201,
        name="Plugin Page Skill",
        skill_type="toolkit",
        package_name="plugin.page",
        source_plugin="plugin.page",
    )
    weather_skill = _make_runtime_skill(
        skill_id=202,
        name="Weather Skill",
        skill_type="builtin",
        package_name="weather.tools",
        config={"tools": [{"name": "get_current_weather"}]},
    )
    result = MagicMock()
    result.scalars.return_value.all.return_value = [
        _make_grant(plugin_page_skill),
        _make_grant(weather_skill),
    ]
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)
    agent = SimpleNamespace(id=1, owner_tenant_id=9)
    request = SimpleNamespace(
        messages=[
            SimpleNamespace(
                role="user",
                content="Please use Plugin Page Skill to inspect this page.",
            )
        ]
    )
    captured: dict[str, object] = {}

    async def _capture_resolve(self, skills, config_overrides=None):
        captured["skills"] = skills
        captured["config_overrides"] = config_overrides
        return SkillResolveResult()

    monkeypatch.setattr(SkillResolver, "resolve", _capture_resolve)

    await resolve_for_agent(db, agent, tenant_id=9, request=request)

    assert [skill.name for skill in captured["skills"]] == ["Plugin Page Skill"]


@pytest.mark.asyncio
async def test_resolve_for_agent_prefilters_explicit_tool_mentions_before_resolve(
    monkeypatch,
) -> None:
    weather_skill = _make_runtime_skill(
        skill_id=301,
        name="Weather Skill",
        skill_type="builtin",
        package_name="weather.tools",
        config={"tools": [{"name": "get_current_weather"}]},
    )
    time_skill = _make_runtime_skill(
        skill_id=302,
        name="Time Skill",
        skill_type="builtin",
        package_name="time.tools",
        config={"tools": [{"name": "get_current_time"}]},
    )
    result = MagicMock()
    result.scalars.return_value.all.return_value = [
        _make_grant(weather_skill),
        _make_grant(time_skill),
    ]
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)
    agent = SimpleNamespace(id=1, owner_tenant_id=9)
    request = SimpleNamespace(
        messages=[
            SimpleNamespace(
                role="user",
                content="call get_current_weather before you answer",
            )
        ]
    )
    captured: dict[str, object] = {}

    async def _capture_resolve(self, skills, config_overrides=None):
        captured["skills"] = skills
        captured["config_overrides"] = config_overrides
        return SkillResolveResult()

    monkeypatch.setattr(SkillResolver, "resolve", _capture_resolve)

    await resolve_for_agent(db, agent, tenant_id=9, request=request)

    assert [skill.name for skill in captured["skills"]] == ["Weather Skill"]


@pytest.mark.asyncio
async def test_resolve_for_agent_keeps_full_inventory_for_capability_reporting_query(
    monkeypatch,
) -> None:
    weather_skill = _make_runtime_skill(
        skill_id=401,
        name="Weather Skill",
        skill_type="builtin",
        package_name="weather.tools",
        config={"tools": [{"name": "get_current_weather"}]},
    )
    page_skill = _make_runtime_skill(
        skill_id=402,
        name="Plugin Page Skill",
        skill_type="toolkit",
        package_name="plugin.page",
        source_plugin="plugin.page",
    )
    result = MagicMock()
    result.scalars.return_value.all.return_value = [
        _make_grant(weather_skill),
        _make_grant(page_skill),
    ]
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)
    agent = SimpleNamespace(id=1, owner_tenant_id=9)
    request = SimpleNamespace(
        messages=[SimpleNamespace(role="user", content="what can you do this turn")]
    )
    captured: dict[str, object] = {}

    async def _capture_resolve(self, skills, config_overrides=None):
        captured["skills"] = skills
        captured["config_overrides"] = config_overrides
        return SkillResolveResult()

    monkeypatch.setattr(SkillResolver, "resolve", _capture_resolve)

    await resolve_for_agent(db, agent, tenant_id=9, request=request)

    assert [skill.name for skill in captured["skills"]] == [
        "Weather Skill",
        "Plugin Page Skill",
    ]


@pytest.mark.asyncio
async def test_resolve_for_agent_does_not_prefilter_for_retired_page_policy(
    monkeypatch,
) -> None:
    plugin_page_skill = _make_runtime_skill(
        skill_id=501,
        name="Plugin Page Skill",
        skill_type="toolkit",
        package_name="plugin.page",
        source_plugin="plugin.page",
    )
    plugin_research_skill = _make_runtime_skill(
        skill_id=502,
        name="Plugin Research Skill",
        skill_type="toolkit",
        package_name="plugin.research",
        source_plugin="plugin.research",
    )
    result = MagicMock()
    result.scalars.return_value.all.return_value = [
        _make_grant(plugin_page_skill),
        _make_grant(plugin_research_skill),
    ]
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)
    agent = SimpleNamespace(id=1, owner_tenant_id=9)
    request = SimpleNamespace(
        messages=[SimpleNamespace(role="user", content="帮我看一下当前页面")],
        input_variables={
            "page_context": {
                "page_key": "admin.ai.dashboard",
                "ui_epoch": 4,
            }
        },
    )
    captured: dict[str, object] = {}

    async def _capture_resolve(self, skills, config_overrides=None):
        captured["skills"] = skills
        captured["config_overrides"] = config_overrides
        return SkillResolveResult()

    monkeypatch.setattr(SkillResolver, "resolve", _capture_resolve)

    await resolve_for_agent(db, agent, tenant_id=9, request=request)

    assert [skill.name for skill in captured["skills"]] == [
        "Plugin Page Skill",
        "Plugin Research Skill",
    ]


@pytest.mark.asyncio
async def test_resolve_for_agent_prefilters_web_research_runtime_policy_before_resolve(
    monkeypatch,
) -> None:
    plugin_page_skill = _make_runtime_skill(
        skill_id=601,
        name="Plugin Page Skill",
        skill_type="toolkit",
        package_name="plugin.page",
        source_plugin="plugin.page",
    )
    plugin_research_skill = _make_runtime_skill(
        skill_id=602,
        name="Plugin Research Skill",
        skill_type="toolkit",
        package_name="plugin.research",
        source_plugin="plugin.research",
    )
    result = MagicMock()
    result.scalars.return_value.all.return_value = [
        _make_grant(plugin_page_skill),
        _make_grant(plugin_research_skill),
    ]
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)
    agent = SimpleNamespace(id=1, owner_tenant_id=9)
    request = SimpleNamespace(
        messages=[SimpleNamespace(role="user", content="请联网搜索最新信息")],
        input_variables={},
    )
    captured: dict[str, object] = {}

    async def _capture_resolve(self, skills, config_overrides=None):
        captured["skills"] = skills
        captured["config_overrides"] = config_overrides
        return SkillResolveResult()

    monkeypatch.setattr(SkillResolver, "resolve", _capture_resolve)

    await resolve_for_agent(db, agent, tenant_id=9, request=request)

    assert [skill.name for skill in captured["skills"]] == ["Plugin Research Skill"]


@pytest.mark.asyncio
async def test_resolve_for_agent_prefilters_plugin_tool_mentions_from_manifest_preview(
    monkeypatch,
) -> None:
    neutral_plugin_skill = _make_runtime_skill(
        skill_id=701,
        name="Assistant Extension",
        skill_type="toolkit",
        package_name="neutral.package",
        source_plugin="neutral-plugin",
    )
    weather_skill = _make_runtime_skill(
        skill_id=702,
        name="Weather Skill",
        skill_type="builtin",
        package_name="weather.tools",
        config={"tools": [{"name": "get_current_weather"}]},
    )
    grant_result = MagicMock()
    grant_result.scalars.return_value.all.return_value = [
        _make_grant(neutral_plugin_skill),
        _make_grant(weather_skill),
    ]
    plugin_preview_result = MagicMock()
    plugin_preview_result.all.return_value = [
        (
            "neutral-plugin",
            {
                "extensions": {
                    "skills": [
                        {
                            "name": "assistant-extension",
                            "type": "toolkit",
                            "display_name": {"en": "Assistant Extension"},
                            "entry_point": "skills.neutral_plugin",
                            "preview_tool_names": ["crm_lookup"],
                        }
                    ]
                }
            },
        )
    ]
    db = MagicMock()
    db.execute = AsyncMock(side_effect=[grant_result, plugin_preview_result])
    agent = SimpleNamespace(id=1, owner_tenant_id=9)
    request = SimpleNamespace(
        messages=[
            SimpleNamespace(role="user", content="Please call crm_lookup for me.")
        ]
    )
    captured: dict[str, object] = {}

    async def _capture_resolve(self, skills, config_overrides=None):
        captured["skills"] = skills
        captured["config_overrides"] = config_overrides
        return SkillResolveResult()

    monkeypatch.setattr(SkillResolver, "resolve", _capture_resolve)

    await resolve_for_agent(db, agent, tenant_id=9, request=request)

    assert [skill.name for skill in captured["skills"]] == ["Assistant Extension"]


@pytest.mark.asyncio
async def test_resolve_for_agent_ignores_retired_page_policy_from_manifest_preview(
    monkeypatch,
) -> None:
    neutral_page_skill = _make_runtime_skill(
        skill_id=801,
        name="Assistant Extension",
        skill_type="toolkit",
        package_name="neutral.page",
        source_plugin="neutral-page-plugin",
    )
    neutral_research_skill = _make_runtime_skill(
        skill_id=802,
        name="Search Extension",
        skill_type="toolkit",
        package_name="neutral.search",
        source_plugin="neutral-search-plugin",
    )
    grant_result = MagicMock()
    grant_result.scalars.return_value.all.return_value = [
        _make_grant(neutral_page_skill),
        _make_grant(neutral_research_skill),
    ]
    plugin_preview_result = MagicMock()
    plugin_preview_result.all.return_value = [
        (
            "neutral-page-plugin",
            {
                "extensions": {
                    "skills": [
                        {
                            "name": "assistant-extension",
                            "type": "toolkit",
                            "display_name": {"en": "Assistant Extension"},
                            "entry_point": "skills.neutral_page",
                            "preview_semantic_families": ["page_ops"],
                        }
                    ]
                }
            },
        ),
        (
            "neutral-search-plugin",
            {
                "extensions": {
                    "skills": [
                        {
                            "name": "search-extension",
                            "type": "toolkit",
                            "display_name": {"en": "Search Extension"},
                            "entry_point": "skills.neutral_search",
                            "preview_semantic_families": ["web_research"],
                        }
                    ]
                }
            },
        ),
    ]
    db = MagicMock()
    db.execute = AsyncMock(side_effect=[grant_result, plugin_preview_result])
    agent = SimpleNamespace(id=1, owner_tenant_id=9)
    request = SimpleNamespace(
        messages=[SimpleNamespace(role="user", content="帮我看一下当前页面")],
        input_variables={
            "page_context": {
                "page_key": "admin.ai.dashboard",
                "ui_epoch": 5,
            }
        },
    )
    captured: dict[str, object] = {}

    async def _capture_resolve(self, skills, config_overrides=None):
        captured["skills"] = skills
        captured["config_overrides"] = config_overrides
        return SkillResolveResult()

    monkeypatch.setattr(SkillResolver, "resolve", _capture_resolve)

    await resolve_for_agent(db, agent, tenant_id=9, request=request)

    assert [skill.name for skill in captured["skills"]] == [
        "Assistant Extension",
        "Search Extension",
    ]


@pytest.mark.asyncio
async def test_resolve_for_agent_preserves_manifest_startup_preview_on_descriptors(
    monkeypatch,
) -> None:
    neutral_plugin_skill = _make_runtime_skill(
        skill_id=901,
        name="Assistant Extension",
        skill_type="toolkit",
        package_name="neutral.package",
        source_plugin="neutral-plugin",
    )
    grant_result = MagicMock()
    grant_result.scalars.return_value.all.return_value = [
        _make_grant(neutral_plugin_skill),
    ]
    plugin_preview_result = MagicMock()
    plugin_preview_result.all.return_value = [
        (
            "neutral-plugin",
            {
                "extensions": {
                    "skills": [
                        {
                            "name": "assistant-extension",
                            "type": "toolkit",
                            "display_name": {"en": "Assistant Extension"},
                            "entry_point": "skills.neutral_plugin",
                            "preview_tool_names": ["crm_lookup"],
                            "preview_semantic_families": ["page_ops"],
                        }
                    ]
                }
            },
        )
    ]
    db = MagicMock()
    db.execute = AsyncMock(side_effect=[grant_result, plugin_preview_result])
    agent = SimpleNamespace(id=1, owner_tenant_id=9)

    async def _capture_resolve(self, skills, config_overrides=None):
        del skills, config_overrides
        return SkillResolveResult(
            tools=[
                ToolDefinition(
                    name="crm_lookup",
                    source_skill_id=901,
                    source_skill_name="Assistant Extension",
                    source_skill_type="toolkit",
                    source_package_name="neutral.package",
                    source_plugin="neutral-plugin",
                )
            ]
        )

    monkeypatch.setattr(SkillResolver, "resolve", _capture_resolve)

    resolved = await resolve_for_agent(db, agent, tenant_id=9)

    descriptor = next(
        item
        for item in resolved.capability_descriptors
        if item.name == "Assistant Extension"
    )
    assert descriptor.metadata["startup_preview_tool_names"] == ["crm_lookup"]
    assert descriptor.metadata["startup_preview_semantic_families"] == []
    assert descriptor.metadata["resolved_tool_names"] == ["crm_lookup"]


@pytest.mark.asyncio
async def test_resolve_for_agent_returns_baseline_builtin_tools_when_agent_has_no_grants() -> None:
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)

    agent = SimpleNamespace(id=1, owner_tenant_id=9)

    resolved = await resolve_for_agent(db, agent, tenant_id=9)

    assert resolved is not None
    assert [tool.name for tool in resolved.tools] == [
        "get_current_time",
        "web_search",
        "fetch_url",
    ]
    assert resolved.tool_consent_modes == {
        "get_current_time": "auto",
        "web_search": "auto",
        "fetch_url": "auto",
    }
