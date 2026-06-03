"""Test type: behavioral.

Regression for: conversation 2362.
中文: 原始症状是授权的「实时天气查询」插件技能没有进入 runtime inventory，AI 回答没有接入实时天气工具。
EN: The original symptom was that the granted realtime weather plugin skill did
not enter runtime inventory, so AI answered without the weather tool.
中文: 插件生命周期同步必须把可用插件技能的 Skill.status 修回 active。
EN: Plugin lifecycle sync must restore usable plugin skills to active status so
the runtime resolver can expose their executable tools.

Real dependencies: plugin lifecycle skill-sync logic and runtime eligibility semantics.
Mocked dependencies: database transport only; no LLM, intent planner, or tool executor is mocked.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ai.skills.resolver_parts.semantics import is_runtime_eligible_skill
from app.enums.skill import SkillStatusEnum
from app.plugins.lifecycle_runtime_state import LifecycleRuntimeStateMixin


class _ScalarOneOrNoneResult:
    def __init__(self, value: object | None) -> None:
        self._value = value

    def scalar_one_or_none(self) -> object | None:
        return self._value


class _ScalarsAllResult:
    def __init__(self, values: list[object]) -> None:
        self._values = values

    def scalars(self):
        return self

    def all(self) -> list[object]:
        return self._values


@pytest.mark.asyncio
async def test_conversation_2362_plugin_skill_sync_restores_runtime_active_status() -> (
    None
):
    """Test type: behavioral. Plugin status drift must not hide a granted weather skill from runtime inventory."""
    package = SimpleNamespace(
        id=103,
        name="旧天气组件",
        is_active=True,
        is_deleted=False,
        source_plugin="weather-widget",
    )
    weather_skill = SimpleNamespace(
        id=51,
        package=package,
        package_id=103,
        name="实时天气查询",
        key="weather-widget:weather-realtime",
        description="获取实时天气",
        type="toolkit",
        source_type="plugin",
        source_ref="weather-widget:weather-realtime",
        version="1.0.0",
        config={},
        is_active=True,
        is_deleted=False,
        status=SkillStatusEnum.DISABLED.value,
    )
    stale_skill = SimpleNamespace(
        id=52,
        package=package,
        package_id=103,
        name="旧天气入口",
        key="weather-widget:old-weather",
        description="stale",
        type="toolkit",
        source_type="plugin",
        source_ref="weather-widget:old-weather",
        version="1.0.0",
        config={},
        is_active=True,
        is_deleted=False,
        status=SkillStatusEnum.ACTIVE.value,
    )
    db = AsyncMock()
    db.add = MagicMock()
    db.execute = AsyncMock(
        side_effect=[
            _ScalarOneOrNoneResult(package),
            _ScalarsAllResult([weather_skill, stale_skill]),
        ]
    )
    db.flush = AsyncMock()
    lifecycle = LifecycleRuntimeStateMixin()
    lifecycle._db = db

    await lifecycle._ensure_plugin_skill_records(
        "weather-widget",
        SimpleNamespace(
            display_name={"zh-CN": "天气组件"},
            description={"zh-CN": "天气组件"},
            version="1.0.0",
        ),
        [
            SimpleNamespace(
                name="weather-realtime",
                display_name={"zh-CN": "实时天气查询"},
                description={"zh-CN": "获取实时天气"},
                type="toolkit",
                config_schema={"location": "string"},
            )
        ],
        active=True,
    )

    assert weather_skill.status == SkillStatusEnum.ACTIVE.value
    assert weather_skill.is_active is True
    assert weather_skill.source_ref == "weather-widget:weather-realtime"
    assert is_runtime_eligible_skill(weather_skill) is True
    assert stale_skill.status == SkillStatusEnum.DISABLED.value
    assert stale_skill.is_active is False
    assert is_runtime_eligible_skill(stale_skill) is False
    db.add.assert_not_called()
    assert db.flush.await_count == 2
