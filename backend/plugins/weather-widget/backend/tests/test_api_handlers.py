"""
天气 API 代理路由单元测试

测试 3 个 API handler：current / forecast / geocoding。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

# ── 动态导入 handlers 模块 ──

_MODULE_FILE = Path(__file__).parent.parent / "api" / "handlers.py"
_MODULE_NAME = "test_weather_api_handlers"

spec = importlib.util.spec_from_file_location(_MODULE_NAME, _MODULE_FILE)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules[_MODULE_NAME] = mod
spec.loader.exec_module(mod)

get_current_weather = mod.get_current_weather
get_forecast = mod.get_forecast
search_city = mod.search_city


def _make_request(params: dict) -> SimpleNamespace:
    """构造模拟 Request 对象 / Build mock Request."""
    return SimpleNamespace(
        query_params=params,
        method="GET",
    )


def _make_ctx(config: dict | None = None) -> MagicMock:
    """构造模拟 PluginContext 对象 / Build mock PluginContext."""
    ctx = MagicMock()
    ctx.get_config = AsyncMock(return_value=config or {})
    ctx.get_logger = MagicMock(return_value=MagicMock())
    return ctx


# ── get_current_weather / 当前天气 ──


class TestGetCurrentWeather:
    """当前天气 API / Current weather API."""

    def test_describe_exception_uses_repr_for_blank_messages(self):
        summary = mod._describe_exception(httpx.ConnectError(""))
        assert "ConnectError" in summary

    @pytest.mark.asyncio
    async def test_missing_lat(self):
        req = _make_request({"lon": "121.47"})
        result = await get_current_weather(req, ctx=_make_ctx())
        assert result.get("code") == 4001
        assert result["error"]

    @pytest.mark.asyncio
    async def test_missing_lon(self):
        req = _make_request({"lat": "31.23"})
        result = await get_current_weather(req, ctx=_make_ctx())
        assert result.get("code") == 4001

    @pytest.mark.asyncio
    async def test_missing_both(self):
        req = _make_request({})
        result = await get_current_weather(req, ctx=_make_ctx())
        assert result.get("code") == 4001

    @pytest.mark.asyncio
    async def test_invalid_lat(self):
        req = _make_request({"lat": "abc", "lon": "121.47"})
        result = await get_current_weather(req, ctx=_make_ctx())
        assert result.get("code") == 4001
        assert result["error"]

    @pytest.mark.asyncio
    async def test_success(self):
        mock_open_meteo = MagicMock()
        mock_open_meteo.get_weather_all = AsyncMock(return_value={
            "current": {
                "temperature": 22.5,
                "weather_code": 0,
                "weather_icon": "sun",
            },
        })

        req = _make_request({"lat": "31.23", "lon": "121.47"})

        with patch.object(mod, "_get_open_meteo", return_value=mock_open_meteo):
            result = await get_current_weather(req, ctx=_make_ctx())

        assert "weather" in result
        assert result["weather"]["temperature"] == 22.5

    @pytest.mark.asyncio
    async def test_api_error(self):
        mock_open_meteo = MagicMock()
        mock_open_meteo.get_weather_all = AsyncMock(
            side_effect=Exception("timeout")
        )

        req = _make_request({"lat": "31.23", "lon": "121.47"})

        with patch.object(mod, "_get_open_meteo", return_value=mock_open_meteo):
            result = await get_current_weather(req, ctx=_make_ctx())

        assert result.get("code") == 5000
        assert "timeout" in result["error"]

    @pytest.mark.asyncio
    async def test_api_error_logs_connect_error_details(self):
        mock_open_meteo = MagicMock()
        mock_open_meteo.get_weather_all = AsyncMock(
            side_effect=httpx.ConnectError(""),
        )

        req = _make_request({"lat": "31.23", "lon": "121.47"})

        with (
            patch.object(mod, "_get_open_meteo", return_value=mock_open_meteo),
            patch.object(mod.logger, "warning") as warning_mock,
        ):
            result = await get_current_weather(req, ctx=_make_ctx())

        assert result.get("code") == 5000
        assert warning_mock.call_count == 2
        final_call = warning_mock.call_args_list[-1]
        assert final_call.args[0] == (
            "Failed to get current weather after retry for lat={} lon={}: {}"
        )
        assert final_call.args[1] == 31.23
        assert final_call.args[2] == 121.47
        assert "ConnectError" in final_call.args[3]


# ── get_forecast / 天气预报 ──


class TestGetForecast:
    """天气预报 API / Weather forecast API."""

    @pytest.mark.asyncio
    async def test_missing_params(self):
        req = _make_request({})
        result = await get_forecast(req, ctx=_make_ctx())
        assert result.get("code") == 4001

    @pytest.mark.asyncio
    async def test_invalid_coords(self):
        req = _make_request({"lat": "xyz", "lon": "121"})
        result = await get_forecast(req, ctx=_make_ctx())
        assert result.get("code") == 4001

    @pytest.mark.asyncio
    async def test_default_days(self):
        mock_open_meteo = MagicMock()
        mock_open_meteo.get_weather_all = AsyncMock(return_value={"daily": []})

        req = _make_request({"lat": "31.23", "lon": "121.47"})

        with patch.object(mod, "_get_open_meteo", return_value=mock_open_meteo):
            await get_forecast(req, ctx=_make_ctx())

        mock_open_meteo.get_weather_all.assert_called_once_with(31.23, 121.47, 3)

    @pytest.mark.asyncio
    async def test_custom_days(self):
        mock_open_meteo = MagicMock()
        mock_open_meteo.get_weather_all = AsyncMock(return_value={"daily": []})

        req = _make_request({"lat": "31.23", "lon": "121.47", "days": "5"})

        with patch.object(mod, "_get_open_meteo", return_value=mock_open_meteo):
            await get_forecast(req, ctx=_make_ctx())

        mock_open_meteo.get_weather_all.assert_called_once_with(31.23, 121.47, 5)

    @pytest.mark.asyncio
    async def test_invalid_days_fallback(self):
        mock_open_meteo = MagicMock()
        mock_open_meteo.get_weather_all = AsyncMock(return_value={"daily": []})

        req = _make_request({"lat": "31.23", "lon": "121.47", "days": "abc"})

        with patch.object(mod, "_get_open_meteo", return_value=mock_open_meteo):
            await get_forecast(req, ctx=_make_ctx())

        mock_open_meteo.get_weather_all.assert_called_once_with(31.23, 121.47, 3)

    @pytest.mark.asyncio
    async def test_success(self):
        mock_open_meteo = MagicMock()
        mock_open_meteo.get_weather_all = AsyncMock(return_value={
            "daily": [
                {"date": "2026-02-23", "temp_max": 25.0, "temp_min": 15.0},
            ],
        })

        req = _make_request({"lat": "31.23", "lon": "121.47", "days": "1"})

        with patch.object(mod, "_get_open_meteo", return_value=mock_open_meteo):
            result = await get_forecast(req, ctx=_make_ctx())

        assert "forecast" in result
        assert len(result["forecast"]) == 1

    @pytest.mark.asyncio
    async def test_api_error(self):
        mock_open_meteo = MagicMock()
        mock_open_meteo.get_weather_all = AsyncMock(
            side_effect=Exception("network error")
        )

        req = _make_request({"lat": "31.23", "lon": "121.47"})

        with patch.object(mod, "_get_open_meteo", return_value=mock_open_meteo):
            result = await get_forecast(req, ctx=_make_ctx())

        assert result.get("code") == 5000


# ── search_city / 城市搜索 ──


class TestSearchCity:
    """城市搜索 API / City search API."""

    @pytest.mark.asyncio
    async def test_missing_name(self):
        req = _make_request({})
        result = await search_city(req, ctx=_make_ctx())
        assert result.get("code") == 4001

    @pytest.mark.asyncio
    async def test_empty_name(self):
        req = _make_request({"name": "   "})
        result = await search_city(req, ctx=_make_ctx())
        assert result.get("code") == 4001

    @pytest.mark.asyncio
    async def test_default_count(self):
        mock_open_meteo = MagicMock()
        mock_open_meteo.search_city = AsyncMock(return_value=[])

        req = _make_request({"name": "Shanghai"})

        with patch.object(mod, "_get_open_meteo", return_value=mock_open_meteo):
            await search_city(req, ctx=_make_ctx())

        mock_open_meteo.search_city.assert_called_once_with("Shanghai", 5)

    @pytest.mark.asyncio
    async def test_custom_count(self):
        mock_open_meteo = MagicMock()
        mock_open_meteo.search_city = AsyncMock(return_value=[])

        req = _make_request({"name": "Shanghai", "count": "3"})

        with patch.object(mod, "_get_open_meteo", return_value=mock_open_meteo):
            await search_city(req, ctx=_make_ctx())

        mock_open_meteo.search_city.assert_called_once_with("Shanghai", 3)

    @pytest.mark.asyncio
    async def test_success(self):
        mock_open_meteo = MagicMock()
        mock_open_meteo.search_city = AsyncMock(return_value=[
            {"name": "Shanghai", "country": "China", "latitude": 31.23, "longitude": 121.47},
        ])

        req = _make_request({"name": "Shanghai"})

        with patch.object(mod, "_get_open_meteo", return_value=mock_open_meteo):
            result = await search_city(req, ctx=_make_ctx())

        assert "cities" in result
        assert len(result["cities"]) == 1
        assert result["cities"][0]["name"] == "Shanghai"

    @pytest.mark.asyncio
    async def test_api_error(self):
        mock_open_meteo = MagicMock()
        mock_open_meteo.search_city = AsyncMock(
            side_effect=Exception("service down")
        )

        req = _make_request({"name": "Shanghai"})

        with patch.object(mod, "_get_open_meteo", return_value=mock_open_meteo):
            result = await search_city(req, ctx=_make_ctx())

        assert result.get("code") == 5000
