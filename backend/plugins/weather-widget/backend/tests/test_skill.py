"""天气技能包单元测试 / Test.

测试 Skill Resolver 和 Executor。"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ai.tools.types import ToolDefinition

# ── 动态导入插件模块 / dynamic plugin import ──

_PLUGIN_DIR = Path(__file__).parent.parent


def _load_module(rel_path: str, mod_name: str):
    """动态加载插件子模块 / Dynamically load plugin submodule."""
    module_file = _PLUGIN_DIR / rel_path
    spec = importlib.util.spec_from_file_location(mod_name, module_file)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


resolver_mod = _load_module("skills/weather_resolver.py", "test_weather_resolver")
resolve = resolver_mod.resolve

executor_mod = _load_module(
    "executors/weather_widget_executor.py", "test_weather_widget_executor"
)
WeatherWidgetExecutor = executor_mod.WeatherWidgetExecutor


# ── Resolver 测试 ──


class TestWeatherResolver:
    """技能解析器 / Skill resolver."""

    def test_resolve_returns_two_tools(self):
        skill = SimpleNamespace(name="weather-realtime")
        tools = resolve(skill, {})
        assert len(tools) == 2

    def test_first_tool_is_current_weather(self):
        skill = SimpleNamespace(name="weather-realtime")
        tools = resolve(skill, {})
        assert tools[0].name == "get_current_weather"
        assert tools[0].tool_type == "toolkit"
        assert any(p.name == "city" and p.required for p in tools[0].parameters)
        assert "凤凰县天气" in tools[0].description

    def test_second_tool_is_forecast(self):
        skill = SimpleNamespace(name="weather-realtime")
        tools = resolve(skill, {})
        assert tools[1].name == "get_weather_forecast"
        assert tools[1].tool_type == "toolkit"
        param_names = {p.name for p in tools[1].parameters}
        assert "city" in param_names
        assert "days" in param_names
        assert "未来七天天气" in tools[1].description

    def test_custom_timeout(self):
        skill = SimpleNamespace(name="weather-realtime")
        tools = resolve(skill, {"timeout": 30})
        assert tools[0].timeout == 30
        assert tools[1].timeout == 30

    def test_default_timeout(self):
        skill = SimpleNamespace(name="weather-realtime")
        tools = resolve(skill, {})
        assert tools[0].timeout == 15

    def test_tools_enabled(self):
        skill = SimpleNamespace(name="weather-realtime")
        tools = resolve(skill, {})
        assert all(t.enabled for t in tools)

    def test_city_param_required(self):
        skill = SimpleNamespace(name="weather-realtime")
        tools = resolve(skill, {})
        for tool in tools:
            city_param = next(p for p in tool.parameters if p.name == "city")
            assert city_param.required is True
            assert "city/county/district/region/scenic area" in city_param.description

    def test_days_param_optional(self):
        skill = SimpleNamespace(name="weather-realtime")
        tools = resolve(skill, {})
        forecast_tool = tools[1]
        days_param = next(p for p in forecast_tool.parameters if p.name == "days")
        assert days_param.required is False


# ── Executor 测试 ──


class TestWeatherWidgetExecutor:
    """天气工具执行器 / Weather tool executor."""

    def setup_method(self):
        self.executor = WeatherWidgetExecutor()

    # ── validate / 参数校验 ──

    @pytest.mark.asyncio
    async def test_validate_with_city(self):
        definition = MagicMock(spec=ToolDefinition)
        result = await self.executor.validate(definition, {"city": "Shanghai"})
        assert result is True

    @pytest.mark.asyncio
    async def test_validate_without_city(self):
        definition = MagicMock(spec=ToolDefinition)
        result = await self.executor.validate(definition, {})
        assert result is False

    @pytest.mark.asyncio
    async def test_validate_empty_city(self):
        definition = MagicMock(spec=ToolDefinition)
        result = await self.executor.validate(definition, {"city": ""})
        assert result is False

    # ── execute: empty city / 执行：城市为空 ──

    @pytest.mark.asyncio
    async def test_execute_empty_city(self):
        definition = MagicMock(spec=ToolDefinition)
        definition.name = "get_current_weather"
        result = await self.executor.execute(definition, "call-1", {"city": ""})
        assert result.success is False
        assert "不能为空" in result.output

    @pytest.mark.asyncio
    async def test_execute_missing_city(self):
        definition = MagicMock(spec=ToolDefinition)
        definition.name = "get_current_weather"
        result = await self.executor.execute(definition, "call-1", {})
        assert result.success is False

    # ── execute: unknown tool / 执行：未知工具 ──

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self):
        definition = MagicMock(spec=ToolDefinition)
        definition.name = "unknown_tool"
        result = await self.executor.execute(
            definition, "call-1", {"city": "Shanghai"}
        )
        assert result.success is False
        assert "unknown" in result.output.lower()

    # ── execute: get_current_weather / 执行：当前天气 ──

    @pytest.mark.asyncio
    async def test_execute_current_weather_success(self):
        mock_open_meteo = MagicMock()
        mock_open_meteo.search_city = AsyncMock(return_value=[
            {"name": "Shanghai", "latitude": 31.23, "longitude": 121.47}
        ])
        mock_open_meteo.get_current_weather = AsyncMock(return_value={
            "temperature": 22.5,
            "weather_text_en": "Clear sky",
            "weather_text_zh": "晴",
            "humidity": 68,
            "wind_speed": 15.2,
            "uv_index": 5.0,
        })

        definition = MagicMock(spec=ToolDefinition)
        definition.name = "get_current_weather"

        with patch.object(executor_mod, "_get_open_meteo", return_value=mock_open_meteo):
            result = await self.executor.execute(
                definition, "call-1", {"city": "Shanghai"}
            )

        assert result.success is True
        assert "Shanghai" in result.output
        assert "22.5" in result.output
        assert "Clear sky" in result.output
        assert result.duration_ms >= 0

    # ── execute: get_weather_forecast / 执行：天气预报 ──

    @pytest.mark.asyncio
    async def test_execute_forecast_success(self):
        mock_open_meteo = MagicMock()
        mock_open_meteo.search_city = AsyncMock(return_value=[
            {"name": "Beijing", "latitude": 39.91, "longitude": 116.40}
        ])
        mock_open_meteo.get_forecast = AsyncMock(return_value=[
            {
                "date": "2026-02-23",
                "temp_max": 25.0,
                "temp_min": 15.0,
                "weather_text_en": "Clear sky",
                "weather_text_zh": "晴",
            },
            {
                "date": "2026-02-24",
                "temp_max": 22.0,
                "temp_min": 12.0,
                "weather_text_en": "Partly cloudy",
                "weather_text_zh": "多云",
            },
        ])

        definition = MagicMock(spec=ToolDefinition)
        definition.name = "get_weather_forecast"

        with patch.object(executor_mod, "_get_open_meteo", return_value=mock_open_meteo):
            result = await self.executor.execute(
                definition, "call-2", {"city": "Beijing", "days": 2}
            )

        assert result.success is True
        assert "Beijing" in result.output
        assert "2026-02-23" in result.output
        assert "25.0" in result.output

    @pytest.mark.asyncio
    async def test_execute_forecast_default_days(self):
        mock_open_meteo = MagicMock()
        mock_open_meteo.search_city = AsyncMock(return_value=[
            {"name": "Tokyo", "latitude": 35.68, "longitude": 139.69}
        ])
        mock_open_meteo.get_forecast = AsyncMock(return_value=[])

        definition = MagicMock(spec=ToolDefinition)
        definition.name = "get_weather_forecast"

        with patch.object(executor_mod, "_get_open_meteo", return_value=mock_open_meteo):
            await self.executor.execute(
                definition, "call-3", {"city": "Tokyo"}
            )

        mock_open_meteo.get_forecast.assert_called_once_with(35.68, 139.69, 3)

    @pytest.mark.asyncio
    async def test_execute_forecast_invalid_days(self):
        mock_open_meteo = MagicMock()
        mock_open_meteo.search_city = AsyncMock(return_value=[
            {"name": "London", "latitude": 51.51, "longitude": -0.13}
        ])
        mock_open_meteo.get_forecast = AsyncMock(return_value=[])

        definition = MagicMock(spec=ToolDefinition)
        definition.name = "get_weather_forecast"

        with patch.object(executor_mod, "_get_open_meteo", return_value=mock_open_meteo):
            await self.executor.execute(
                definition, "call-4", {"city": "London", "days": "abc"}
            )

        # Invalid days falls back to 3 / 非法 days 回退为 3
        mock_open_meteo.get_forecast.assert_called_once_with(51.51, -0.13, 3)

    # ── execute: city not found / 执行：城市未找到 ──

    @pytest.mark.asyncio
    async def test_execute_city_not_found(self):
        mock_open_meteo = MagicMock()
        mock_open_meteo.search_city = AsyncMock(return_value=[])

        definition = MagicMock(spec=ToolDefinition)
        definition.name = "get_current_weather"

        with patch.object(executor_mod, "_get_open_meteo", return_value=mock_open_meteo):
            result = await self.executor.execute(
                definition, "call-5", {"city": "XYZNONEXISTENT"}
            )

        assert result.success is False
        assert "未找到城市" in result.output

    # ── execute: API error / 执行：接口异常 ──

    @pytest.mark.asyncio
    async def test_execute_api_error(self):
        mock_open_meteo = MagicMock()
        mock_open_meteo.search_city = AsyncMock(return_value=[
            {"name": "Shanghai", "latitude": 31.23, "longitude": 121.47}
        ])
        mock_open_meteo.get_current_weather = AsyncMock(
            side_effect=Exception("API timeout")
        )

        definition = MagicMock(spec=ToolDefinition)
        definition.name = "get_current_weather"

        with patch.object(executor_mod, "_get_open_meteo", return_value=mock_open_meteo):
            result = await self.executor.execute(
                definition, "call-6", {"city": "Shanghai"}
            )

        assert result.success is False
        assert "API timeout" in result.output
