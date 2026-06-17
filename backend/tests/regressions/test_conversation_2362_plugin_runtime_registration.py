"""Test type: behavioral.

Regression for: conversation 2362.
中文: 天气插件 skill 已授权但运行进程未注册 resolver 时，runtime inventory 不应停在
`plugin_resolver_missing`；同时 direct-reply 工具发现应能从插件工具元数据识别天气请求。
EN: When the granted weather plugin skill is missing only the process-local
resolver registration, runtime should restore the enabled plugin registration;
direct-reply tool discovery should also match weather requests from generic
tool metadata rather than plugin-specific hardcoding.

Real dependencies: ExtensionRegistry, plugin runtime registration guard,
runtime DTOs.
Mocked dependencies: DB transport and startup restore boundary only.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

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
