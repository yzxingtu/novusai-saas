"""Test type: behavioral.

Regression for: conversation 2362.
中文: 天气插件 skill 已授权但运行进程未注册 resolver 时，runtime inventory 不应停在
`plugin_resolver_missing`；同时 direct-reply 工具发现应能从插件工具元数据识别天气请求。
EN: When the granted weather plugin skill is missing only the process-local
resolver registration, runtime should restore the enabled plugin registration;
direct-reply tool discovery should also match weather requests from generic
tool metadata rather than plugin-specific hardcoding.

Real dependencies: ExtensionRegistry, plugin runtime registration guard,
tool planning helpers, runtime DTOs.
Mocked dependencies: DB transport and startup restore boundary only; no LLM,
intent planner, or tool executor is mocked.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.ai.engine.prepare_execution_tool_helpers import plan_execution_tools
from app.ai.engine.types import ExecutionRequest, IntentPlan
from app.ai.tools.types import ToolDefinition
from app.plugins.registry import ExtensionRegistry
from app.plugins.runtime_registration import (
    ensure_enabled_plugin_skill_runtime_registered,
)


class _RowsResult:
    def __init__(self, rows: list[tuple[str, dict]]) -> None:
        self._rows = rows

    def all(self) -> list[tuple[str, dict]]:
        return self._rows


@pytest.fixture(autouse=True)
def _reset_extension_registry():
    ExtensionRegistry.reset()
    yield
    ExtensionRegistry.reset()


@pytest.mark.asyncio
async def test_conversation_2362_restores_missing_weather_plugin_resolver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test type: behavioral. A cold runtime process should register enabled plugin skill resolvers on demand."""

    db = SimpleNamespace(
        execute=AsyncMock(
            return_value=_RowsResult(
                [
                    (
                        "weather-widget",
                        {
                            "extensions": {
                                "skills": [
                                    {
                                        "name": "weather-realtime",
                                        "type": "toolkit",
                                    }
                                ]
                            }
                        },
                    )
                ]
            )
        )
    )

    async def _restore_enabled_plugins(
        _db,
        *,
        run_heavy: bool,
        mutate_db_status: bool,
        plugin_names: list[str],
    ) -> dict:
        assert run_heavy is False
        assert mutate_db_status is False
        assert plugin_names == ["weather-widget"]

        def _weather_resolver(_skill, _config):
            return [ToolDefinition(name="get_weather_forecast")]

        ExtensionRegistry.get_instance().register_skill(
            "weather-widget",
            "toolkit",
            _weather_resolver,
            skill_name="weather-realtime",
        )
        return {"restored": 1, "failed": 0, "total": 1}

    monkeypatch.setattr(
        "app.plugins.startup.restore_enabled_plugins",
        _restore_enabled_plugins,
    )

    result = await ensure_enabled_plugin_skill_runtime_registered(
        db,
        source_plugins=["weather-widget"],
    )

    assert result == {"restored": 1, "failed": 0, "total": 1}
    assert (
        ExtensionRegistry.get_instance().get_plugin_skill_resolver(
            "weather-widget",
            "weather-realtime",
        )
        is not None
    )


def test_conversation_2362_direct_weather_query_discovers_plugin_tools() -> None:
    """Test type: behavioral. Weather tools should enter candidates through generic metadata matching."""

    request = ExecutionRequest(
        agent_id=59,
        tenant_id=0,
        messages=[],
    )
    messages = [
        SimpleNamespace(role="user", content="近7天 拉萨的天气怎么样？"),
    ]
    weather_tools = [
        ToolDefinition(
            name="get_weather_forecast",
            description="Get multi-day weather forecast.",
            semantic_family="weather",
            semantic_tags=["天气预报", "未来天气", "weather forecast"],
            source_skill_name="实时天气查询",
            source_package_name="天气组件",
            source_plugin="weather-widget",
        ),
        ToolDefinition(
            name="get_current_weather",
            description="Get real-time current weather.",
            semantic_family="weather",
            semantic_tags=["实时天气", "当前天气", "weather"],
            source_skill_name="实时天气查询",
            source_package_name="天气组件",
            source_plugin="weather-widget",
        ),
    ]
    diagnostics = {
        "intent_plan": [
            IntentPlan(
                intent_id="intent-1",
                kind="direct_reply",
                family="none",
                order=1,
                user_visible_label="direct_reply",
                source_text="近7天 拉萨的天气怎么样？",
                requires_tools=False,
                shortcircuit=True,
            ).to_dict()
        ]
    }

    plan = plan_execution_tools(
        agent_id=59,
        conversation_id=2362,
        request=request,
        messages=messages,  # type: ignore[arg-type]
        tools=list(weather_tools),
        all_tools=list(weather_tools),
        diagnostics=diagnostics,
    )

    assert plan.candidate_tool_names == [
        "get_weather_forecast",
        "get_current_weather",
    ]
    assert [tool.name for tool in plan.tools] == [
        "get_weather_forecast",
        "get_current_weather",
    ]
    assert plan.intent_plan[0].kind == "weather_query"
    assert plan.intent_plan[0].family == "weather"
    assert plan.intent_plan[0].requires_tools is True
    assert plan.intent_plan[0].shortcircuit is False
    assert plan.intent_flags["all_shortcircuit"] is False
    assert plan.tool_use_policy.mode == "required"
    assert plan.tool_use_policy.allowed_tool_names == plan.candidate_tool_names
    assert plan.tool_use_policy.reason == "intent:weather_query"


def test_conversation_2362_explicit_weather_skill_request_requires_tool_use() -> None:
    """Test type: behavioral. An explicit request to use a matched skill should require one candidate tool call."""

    request = ExecutionRequest(
        agent_id=59,
        tenant_id=0,
        messages=[],
    )
    messages = [
        SimpleNamespace(role="user", content="使用 实时天气查询"),
    ]
    weather_tools = [
        ToolDefinition(
            name="get_current_weather",
            description="Get real-time current weather.",
            semantic_family="weather",
            semantic_tags=["实时天气", "当前天气"],
            source_skill_name="实时天气查询",
            source_package_name="天气组件",
            source_plugin="weather-widget",
        )
    ]
    diagnostics = {
        "intent_plan": [
            IntentPlan(
                intent_id="intent-1",
                kind="direct_reply",
                family="none",
                order=1,
                user_visible_label="direct_reply",
                source_text="使用 实时天气查询",
                requires_tools=False,
                shortcircuit=True,
            ).to_dict()
        ]
    }

    plan = plan_execution_tools(
        agent_id=59,
        conversation_id=2362,
        request=request,
        messages=messages,  # type: ignore[arg-type]
        tools=list(weather_tools),
        all_tools=list(weather_tools),
        diagnostics=diagnostics,
    )

    assert plan.candidate_tool_names == ["get_current_weather"]
    assert plan.tool_use_policy.mode == "required"
    assert plan.tool_use_policy.allowed_tool_names == ["get_current_weather"]
    assert plan.tool_use_policy.retry_on_contract_breach is True
