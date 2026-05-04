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
from app.ai.skills.activation import apply_turn_skill_activation
from app.ai.skills.resolver import (
    SkillResolver,
    SkillResolveResult,
    enrich_skill_capability_descriptors_with_tools,
    resolve_for_agent,
)
from app.ai.tools.types import ToolDefinition


@pytest.mark.asyncio
async def test_plugin_skill_without_registered_resolver_is_unavailable(
    monkeypatch,
) -> None:
    """Plugin-owned toolkit skills must fail closed when registry has no resolver."""

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
        key="weather-widget:weather_tools",
        source_ref="weather-widget:weather_tools",
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

    registry_stub = SimpleNamespace(get_plugin_skill_resolver=lambda *_args: None)
    monkeypatch.setattr(
        "app.plugins.registry.ExtensionRegistry.get_instance",
        lambda: registry_stub,
    )

    result = await resolver.resolve([skill])

    assert result.tools == []
    assert [issue.code for issue in result.resolution_issues] == [
        "plugin_resolver_missing"
    ]
    assert result.resolution_issues[0].source_plugin == "weather-widget"
    assert result.resolution_issues[0].skill_id == 101
    assert "resolver is unavailable" in result.warnings[0]


@pytest.mark.asyncio
async def test_plugin_skill_without_registered_resolver_does_not_use_builtin_fallback(
    monkeypatch,
) -> None:
    """Plugin-owned builtin skills must not silently use canonical builtin fallback."""

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
        key="weather-widget:weather_builtin",
        source_ref="weather-widget:weather_builtin",
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

    registry_stub = SimpleNamespace(get_plugin_skill_resolver=lambda *_args: None)
    monkeypatch.setattr(
        "app.plugins.registry.ExtensionRegistry.get_instance",
        lambda: registry_stub,
    )

    result = await resolver.resolve([skill])

    assert result.tools == []
    assert [issue.code for issue in result.resolution_issues] == [
        "plugin_resolver_missing"
    ]
    assert result.resolution_issues[0].source_plugin == "weather-widget"
    assert result.resolution_issues[0].skill_id == 102


@pytest.mark.asyncio
async def test_resolve_one_records_issue_when_source_plugin_has_no_resolver(
    monkeypatch,
) -> None:
    skill = SimpleNamespace(
        id=101,
        name="weather_tools",
        type="toolkit",
        package_id=77,
        key="weather-widget:weather_tools",
        source_ref="weather-widget:weather_tools",
        config=None,
        timeout=30,
        is_active=True,
        is_deleted=False,
    )

    resolver = SkillResolver(db=None)
    registry_stub = SimpleNamespace(get_plugin_skill_resolver=lambda *_args: None)
    monkeypatch.setattr(
        "app.plugins.registry.ExtensionRegistry.get_instance",
        lambda: registry_stub,
    )

    resolver._resolve_toolkit = MagicMock()  # type: ignore[method-assign]

    result = SkillResolveResult()
    await resolver._resolve_one(
        skill, config={}, result=result, source_plugin="weather-widget"
    )

    assert result.tools == []
    assert [issue.code for issue in result.resolution_issues] == [
        "plugin_resolver_missing"
    ]
    resolver._resolve_toolkit.assert_not_called()


@pytest.mark.asyncio
async def test_plugin_skill_without_stable_identity_does_not_use_plugin_fallback(
    monkeypatch,
) -> None:
    skill = SimpleNamespace(
        id=103,
        name="Legacy Display Name",
        type="toolkit",
        package_id=77,
        key=None,
        source_ref=None,
        config=None,
        timeout=30,
        is_active=True,
        is_deleted=False,
    )
    registry_stub = SimpleNamespace(
        get_plugin_skill_resolver=lambda *_args: (
            lambda *_resolver_args: [
                ToolDefinition(name="legacy_tool", description="legacy")
            ]
        )
    )
    monkeypatch.setattr(
        "app.plugins.registry.ExtensionRegistry.get_instance",
        lambda: registry_stub,
    )

    result = SkillResolveResult()
    resolver = SkillResolver(db=None)
    await resolver._resolve_one(
        skill, config={}, result=result, source_plugin="legacy-plugin"
    )

    assert result.tools == []
    assert [issue.code for issue in result.resolution_issues] == [
        "plugin_skill_identity_missing"
    ]
    assert "stable source_ref/key identity" in result.warnings[0]


def test_selected_skill_names_merges_descriptor_and_tool_sources() -> None:
    result = SkillResolveResult(
        tools=[
            SimpleNamespace(source_skill_name="Weather Tool Skill"),
            SimpleNamespace(source_skill_name="Workflow Skill"),
        ],
        capability_descriptors=[
            CapabilityDescriptor(
                name="Workflow Skill",
                kind="capability_pack",
                source="skill_package:workflow",
            ),
            CapabilityDescriptor(
                name="Knowledge Skill",
                kind="capability_pack",
                source="skill_package:kb",
            ),
        ],
    )

    assert result.selected_skill_names == [
        "Workflow Skill",
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


def test_selected_skill_names_skips_auto_injected_runtime_builtins() -> None:
    result = SkillResolveResult(
        tools=[
            SimpleNamespace(
                source_skill_name="web_search",
                config={"auto_injected": True},
            ),
            SimpleNamespace(
                source_skill_name="Plugin Workflow Skill",
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
                name="Plugin Workflow Skill",
                kind="capability_pack",
                source="skill_package:plugin.workflow",
                metadata={"has_execution_tools": True},
            ),
        ],
    )

    assert result.selected_skill_names == ["Plugin Workflow Skill"]


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
        key=f"{source_plugin}:{name}" if source_plugin else None,
        source_ref=f"{source_plugin}:{name}" if source_plugin else None,
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
    plugin_workflow_skill = _make_runtime_skill(
        skill_id=201,
        name="Plugin Workflow Skill",
        skill_type="toolkit",
        package_name="plugin.workflow",
        source_plugin="plugin.workflow",
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
        _make_grant(plugin_workflow_skill),
        _make_grant(weather_skill),
    ]
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)
    agent = SimpleNamespace(id=1, owner_tenant_id=9)
    request = SimpleNamespace(
        messages=[
            SimpleNamespace(
                role="user",
                content="Please use Plugin Workflow Skill before you answer.",
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

    assert [skill.name for skill in captured["skills"]] == ["Plugin Workflow Skill"]


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
    workflow_skill = _make_runtime_skill(
        skill_id=402,
        name="Plugin Workflow Skill",
        skill_type="toolkit",
        package_name="plugin.workflow",
        source_plugin="plugin.workflow",
    )
    result = MagicMock()
    result.scalars.return_value.all.return_value = [
        _make_grant(weather_skill),
        _make_grant(workflow_skill),
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
        "Plugin Workflow Skill",
    ]


@pytest.mark.asyncio
async def test_resolve_for_agent_prefilters_web_research_runtime_policy_before_resolve(
    monkeypatch,
) -> None:
    plugin_workflow_skill = _make_runtime_skill(
        skill_id=601,
        name="Plugin Workflow Skill",
        skill_type="toolkit",
        package_name="plugin.workflow",
        source_plugin="plugin.workflow",
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
        _make_grant(plugin_workflow_skill),
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

    assert [skill.name for skill in captured["skills"]] == [
        "Plugin Workflow Skill",
        "Plugin Research Skill",
    ]


def test_turn_skill_activation_does_not_treat_generic_web_search_as_skill_mention() -> (
    None
):
    result = SkillResolveResult(
        tools=[
            ToolDefinition(
                name="web_search",
                source_skill_name="联网搜索",
                source_package_name="Web Search",
                semantic_family="web_research",
            ),
            ToolDefinition(
                name="fetch_url",
                source_skill_name="联网搜索",
                source_package_name="Web Search",
                semantic_family="web_research",
            ),
        ],
        capability_descriptors=[
            CapabilityDescriptor(
                name="联网搜索",
                kind="capability_pack",
                source="skill_package:Web Search",
                metadata={
                    "has_execution_tools": True,
                    "resolved_tool_names": ["web_search", "fetch_url"],
                },
            )
        ],
    )
    request = SimpleNamespace(
        messages=[SimpleNamespace(role="user", content="请联网搜索今天新闻")],
    )

    apply_turn_skill_activation(
        skill_result=result,
        request=request,
        intent_flags={
            "has_web_research_intent": True,
            "has_builtin_web_tool_request": False,
        },
    )

    assert result.turn_activation is not None
    assert result.turn_activation.applied is False
    assert result.turn_activation.reason == "no_turn_skill_activation"
    assert result.turn_activation.activated_skill_names == []
    assert result.turn_activation.activated_tool_names == []


def test_turn_skill_activation_keeps_explicit_web_search_skill_request() -> None:
    result = SkillResolveResult(
        tools=[
            ToolDefinition(
                name="web_search",
                source_skill_name="联网搜索",
                source_package_name="Web Search",
                semantic_family="web_research",
            ),
            ToolDefinition(
                name="fetch_url",
                source_skill_name="联网搜索",
                source_package_name="Web Search",
                semantic_family="web_research",
            ),
        ],
        capability_descriptors=[
            CapabilityDescriptor(
                name="联网搜索",
                kind="capability_pack",
                source="skill_package:Web Search",
                metadata={
                    "has_execution_tools": True,
                    "resolved_tool_names": ["web_search", "fetch_url"],
                },
            )
        ],
    )
    request = SimpleNamespace(
        messages=[SimpleNamespace(role="user", content="请使用联网搜索技能查今天新闻")],
    )

    apply_turn_skill_activation(
        skill_result=result,
        request=request,
        intent_flags={
            "has_web_research_intent": True,
            "has_builtin_web_tool_request": True,
        },
    )

    assert result.turn_activation is not None
    assert result.turn_activation.applied is True
    assert result.turn_activation.reason == "explicit_skill_mention"
    assert result.turn_activation.activated_skill_names == ["联网搜索"]
    assert result.turn_activation.activated_tool_names == ["web_search", "fetch_url"]


@pytest.mark.asyncio
async def test_resolve_for_agent_prefilters_selected_bound_skill_package(
    monkeypatch,
) -> None:
    baidu_skill = _make_runtime_skill(
        skill_id=611,
        name="Baidu Public Search Skill",
        skill_type="toolkit",
        package_name="百度公开搜索",
        source_plugin="baidu-public-search",
    )
    weather_skill = _make_runtime_skill(
        skill_id=612,
        name="Weather Skill",
        skill_type="builtin",
        package_name="weather.tools",
        config={"tools": [{"name": "get_current_weather"}]},
    )
    result = MagicMock()
    result.scalars.return_value.all.return_value = [
        _make_grant(baidu_skill),
        _make_grant(weather_skill),
    ]
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)
    agent = SimpleNamespace(id=1, owner_tenant_id=9)
    request = SimpleNamespace(
        messages=[SimpleNamespace(role="user", content="查一下今天新闻")],
        selected_skill_names=["百度公开搜索"],
    )
    captured: dict[str, object] = {}

    async def _capture_resolve(self, skills, config_overrides=None):
        captured["skills"] = skills
        captured["config_overrides"] = config_overrides
        return SkillResolveResult()

    monkeypatch.setattr(SkillResolver, "resolve", _capture_resolve)

    await resolve_for_agent(db, agent, tenant_id=9, request=request)

    assert [skill.name for skill in captured["skills"]] == ["Baidu Public Search Skill"]


@pytest.mark.asyncio
async def test_resolve_for_agent_ignores_unbound_selected_skill_package(
    monkeypatch,
) -> None:
    weather_skill = _make_runtime_skill(
        skill_id=621,
        name="Weather Skill",
        skill_type="builtin",
        package_name="weather.tools",
        config={"tools": [{"name": "get_current_weather"}]},
    )
    result = MagicMock()
    result.scalars.return_value.all.return_value = [_make_grant(weather_skill)]
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)
    agent = SimpleNamespace(id=1, owner_tenant_id=9)
    request = SimpleNamespace(
        messages=[SimpleNamespace(role="user", content="查一下今天新闻")],
        selected_skill_names=["百度公开搜索"],
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
async def test_resolve_for_agent_prefilters_explicit_baidu_public_search_mention(
    monkeypatch,
) -> None:
    baidu_skill = _make_runtime_skill(
        skill_id=631,
        name="Baidu Public Search Skill",
        skill_type="toolkit",
        package_name="百度公开搜索",
        source_plugin="baidu-public-search",
    )
    weather_skill = _make_runtime_skill(
        skill_id=632,
        name="Weather Skill",
        skill_type="builtin",
        package_name="weather.tools",
        config={"tools": [{"name": "get_current_weather"}]},
    )
    result = MagicMock()
    result.scalars.return_value.all.return_value = [
        _make_grant(baidu_skill),
        _make_grant(weather_skill),
    ]
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)
    agent = SimpleNamespace(id=1, owner_tenant_id=9)
    request = SimpleNamespace(
        messages=[SimpleNamespace(role="user", content="请直接用百度公开搜索查一下")],
        selected_skill_names=[],
    )
    captured: dict[str, object] = {}

    async def _capture_resolve(self, skills, config_overrides=None):
        captured["skills"] = skills
        captured["config_overrides"] = config_overrides
        return SkillResolveResult()

    monkeypatch.setattr(SkillResolver, "resolve", _capture_resolve)

    await resolve_for_agent(db, agent, tenant_id=9, request=request)

    assert [skill.name for skill in captured["skills"]] == ["Baidu Public Search Skill"]


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
async def test_resolve_for_agent_marks_plugin_skill_unavailable_when_resolver_missing(
    monkeypatch,
) -> None:
    neutral_plugin_skill = _make_runtime_skill(
        skill_id=711,
        name="Assistant Extension",
        skill_type="toolkit",
        package_name="neutral.package",
        source_plugin="neutral-plugin",
    )
    grant_result = MagicMock()
    grant_result.scalars.return_value.all.return_value = [
        _make_grant(neutral_plugin_skill)
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
    source_plugin_result = [
        SimpleNamespace(
            id=neutral_plugin_skill.package_id, source_plugin="neutral-plugin"
        )
    ]
    db = MagicMock()
    db.execute = AsyncMock(
        side_effect=[grant_result, plugin_preview_result, source_plugin_result]
    )
    registry_stub = SimpleNamespace(get_plugin_skill_resolver=lambda *_args: None)
    monkeypatch.setattr(
        "app.plugins.registry.ExtensionRegistry.get_instance",
        lambda: registry_stub,
    )
    agent = SimpleNamespace(id=1, name="Support Agent", owner_tenant_id=9)
    request = SimpleNamespace(
        messages=[
            SimpleNamespace(role="user", content="Please call crm_lookup for me.")
        ]
    )

    resolved = await resolve_for_agent(db, agent, tenant_id=9, request=request)

    assert resolved is not None
    assert [issue.code for issue in resolved.resolution_issues] == [
        "plugin_resolver_missing"
    ]
    plugin_descriptors = [
        descriptor
        for descriptor in resolved.capability_descriptors
        if descriptor.name == "Assistant Extension"
    ]
    assert len(plugin_descriptors) == 1
    metadata = plugin_descriptors[0].metadata
    assert metadata["startup_preview_tool_names"] == ["crm_lookup"]
    assert metadata["resolved_tool_names"] == []
    assert metadata["has_execution_tools"] is False
    assert metadata["resolution_status"] == "unavailable"
    assert metadata["resolution_reason"] == "plugin_resolver_missing"
    assert [tool.name for tool in resolved.tools] == [
        "get_current_time",
        "web_search",
        "fetch_url",
    ]
    assert resolved.selected_skill_names == []


@pytest.mark.asyncio
async def test_resolve_for_agent_returns_baseline_builtin_tools_when_agent_has_no_grants() -> (
    None
):
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
