"""Open-Meteo API 客户端单元测试 / Open-Meteo API client unit tests — weather, forecast, geocoding, cache."""

from __future__ import annotations

# 动态导入 open_meteo 模块（插件名含连字符）
import importlib.util
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

_MODULE_FILE = Path(__file__).parent.parent / "open_meteo.py"
_MODULE_NAME = "plugins.weather_widget_test.open_meteo"

spec = importlib.util.spec_from_file_location(_MODULE_NAME, _MODULE_FILE)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules[_MODULE_NAME] = mod
spec.loader.exec_module(mod)

search_city = mod.search_city
get_current_weather = mod.get_current_weather
get_forecast = mod.get_forecast
get_wmo_info = mod.get_wmo_info
_cache = mod._cache
_cache_get = mod._cache_get
_cache_set = mod._cache_set
_expand_city_queries = mod._expand_city_queries
_rank_city_candidate = mod._rank_city_candidate
_NOMINATIM_TIMEOUT = mod._NOMINATIM_TIMEOUT


# ── WMO Code 映射测试 ──


class TestWmoCodeMapping:
    """WMO 天气代码映射 / WMO weather code mapping."""

    def test_clear_sky(self):
        info = get_wmo_info(0)
        assert info["icon"] == "sun"
        assert info["zh"] == "晴"

    def test_partly_cloudy(self):
        info = get_wmo_info(2)
        assert info["icon"] == "cloud-sun"

    def test_rain(self):
        info = get_wmo_info(63)
        assert info["icon"] == "cloud-rain"
        assert info["zh"] == "中雨"

    def test_snow(self):
        info = get_wmo_info(73)
        assert info["icon"] == "snowflake"

    def test_thunderstorm(self):
        info = get_wmo_info(95)
        assert info["icon"] == "cloud-lightning"
        assert info["zh"] == "雷暴"

    def test_fog(self):
        info = get_wmo_info(45)
        assert info["icon"] == "cloud-fog"

    def test_unknown_code(self):
        info = get_wmo_info(999)
        assert info["icon"] == "cloud"
        assert info["zh"] == "未知"

    def test_describe_exception_uses_repr_for_blank_connect_error(self):
        summary = mod._describe_exception(httpx.ConnectError(""))
        assert "ConnectError" in summary

    def test_nominatim_timeout_allows_more_headroom(self):
        assert _NOMINATIM_TIMEOUT == 10.0


# ── 缓存测试 / cache tests ──


class TestCache:
    """内存缓存机制 / In-memory cache."""

    def setup_method(self):
        _cache.clear()

    def test_cache_set_and_get(self):
        _cache_set("test_key", {"temp": 22})
        result = _cache_get("test_key")
        assert result == {"temp": 22}

    def test_cache_miss(self):
        result = _cache_get("nonexistent")
        assert result is None

    def test_cache_expired(self):
        _cache["expired_key"] = (time.time() - 700, {"temp": 22})
        result = _cache_get("expired_key")
        assert result is None

    def test_cache_not_expired(self):
        _cache["fresh_key"] = (time.time() - 100, {"temp": 22})
        result = _cache_get("fresh_key")
        assert result == {"temp": 22}

    def test_cache_eviction(self):
        for i in range(210):
            _cache_set(f"key_{i}", i)
        assert len(_cache) <= 200


# ── API 调用测试（Mock） ──


class TestSearchCity:
    """城市搜索 / City search."""

    def setup_method(self):
        _cache.clear()

    @pytest.mark.asyncio
    async def test_empty_name(self):
        result = await search_city("")
        assert result == []

    @pytest.mark.asyncio
    async def test_whitespace_name(self):
        result = await search_city("   ")
        assert result == []

    @pytest.mark.asyncio
    async def test_search_success(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = [
            {
                "lat": "31.23",
                "lon": "121.47",
                "display_name": "Shanghai, China",
                "address": {
                    "city": "Shanghai",
                    "country": "China",
                    "state": "Shanghai",
                },
            }
        ]

        mock_instance = AsyncMock()
        mock_instance.get.return_value = mock_resp

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await search_city("Shanghai", count=1)

        assert len(result) == 1
        assert result[0]["name"] == "Shanghai"
        assert result[0]["latitude"] == 31.23

    @pytest.mark.asyncio
    async def test_search_no_results(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {}

        mock_instance = AsyncMock()
        mock_instance.get.return_value = mock_resp

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await search_city("XYZNONEXISTENT")

        assert result == []

    @pytest.mark.asyncio
    async def test_search_cached(self):
        _cache_set("geo:Shanghai:5", [{"name": "Shanghai", "latitude": 31.23, "longitude": 121.47}])
        result = await search_city("Shanghai")
        assert len(result) == 1
        assert result[0]["name"] == "Shanghai"

    def test_expand_city_queries_adds_common_beijing_aliases(self):
        expanded = _expand_city_queries("北京")
        assert expanded[0] == "北京"
        assert "北京市" in expanded
        assert "Beijing" in expanded

    @pytest.mark.asyncio
    async def test_search_city_falls_back_to_open_meteo_when_nominatim_empty(self):
        with (
            patch.object(mod, "_search_city_nominatim", new=AsyncMock(return_value=[])),
            patch.object(
                mod,
                "_search_city_open_meteo",
                new=AsyncMock(
                    return_value=[
                        {
                            "name": "北京市",
                            "country": "China",
                            "admin1": "北京市",
                            "latitude": 39.9042,
                            "longitude": 116.4074,
                        }
                    ]
                ),
            ),
        ):
            result = await search_city("北京", count=1)

        assert len(result) == 1
        assert result[0]["name"] == "北京市"

    def test_rank_city_candidate_prefers_municipality_match(self):
        expanded = _expand_city_queries("北京")
        beijing_city = {
            "name": "北京市",
            "country": "中国",
            "admin1": "北京",
            "latitude": 39.9075,
            "longitude": 116.39723,
        }
        county_homonym = {
            "name": "北京",
            "country": "中国",
            "admin1": "重庆市",
            "latitude": 30.72608,
            "longitude": 108.67483,
        }

        assert _rank_city_candidate(
            original_query="北京",
            expanded_queries=expanded,
            candidate=beijing_city,
        ) > _rank_city_candidate(
            original_query="北京",
            expanded_queries=expanded,
            candidate=county_homonym,
        )

    def test_rank_city_candidate_prefers_beijing_city_for_english_query(self):
        expanded = _expand_city_queries("Beijing")
        beijing_city = {
            "name": "北京市",
            "country": "中国",
            "admin1": "北京",
            "latitude": 39.9075,
            "longitude": 116.39723,
        }
        county_homonym = {
            "name": "Beijing",
            "country": "中国",
            "admin1": "山西",
            "latitude": 35.20917,
            "longitude": 110.73278,
        }

        assert _rank_city_candidate(
            original_query="Beijing",
            expanded_queries=expanded,
            candidate=beijing_city,
        ) > _rank_city_candidate(
            original_query="Beijing",
            expanded_queries=expanded,
            candidate=county_homonym,
        )


class TestGetCurrentWeather:
    """当前天气 / Current weather."""

    def setup_method(self):
        _cache.clear()

    @pytest.mark.asyncio
    async def test_success(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "current": {
                "temperature_2m": 22.5,
                "weather_code": 0,
                "relative_humidity_2m": 68,
                "wind_speed_10m": 15.2,
                "uv_index": 5.0,
                "is_day": 1,
            }
        }

        mock_instance = AsyncMock()
        mock_instance.get.return_value = mock_resp

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await get_current_weather(31.23, 121.47)

        assert result["temperature"] == 22.5
        assert result["weather_code"] == 0
        assert result["weather_icon"] == "sun"
        assert result["weather_text_zh"] == "晴"
        assert result["humidity"] == 68
        assert result["wind_speed"] == 15.2
        assert result["uv_index"] == 5.0
        assert result["is_day"] is True

    @pytest.mark.asyncio
    async def test_cached(self):
        cached_data = {
            "current": {
                "temperature": 20.0,
                "weather_code": 2,
                "weather_icon": "cloud-sun",
                "weather_text_zh": "多云",
                "weather_text_en": "Partly cloudy",
                "humidity": 55,
                "wind_speed": 10.0,
                "uv_index": 3.0,
                "is_day": True,
            },
            "daily": [],
            "hourly": [],
        }
        _cache_set("all:31.23:121.47:3", cached_data)
        result = await get_current_weather(31.23, 121.47)
        assert result["temperature"] == 20.0


class TestGetForecast:
    """天气预报 / Weather forecast."""

    def setup_method(self):
        _cache.clear()

    @pytest.mark.asyncio
    async def test_success(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "daily": {
                "time": ["2026-02-23", "2026-02-24", "2026-02-25"],
                "temperature_2m_max": [25.0, 22.0, 20.0],
                "temperature_2m_min": [15.0, 12.0, 10.0],
                "weather_code": [0, 2, 61],
            }
        }

        mock_instance = AsyncMock()
        mock_instance.get.return_value = mock_resp

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await get_forecast(31.23, 121.47, 3)

        assert len(result) == 3
        assert result[0]["date"] == "2026-02-23"
        assert result[0]["temp_max"] == 25.0
        assert result[0]["weather_icon"] == "sun"
        assert result[2]["weather_icon"] == "cloud-rain"
        assert result[2]["weather_text_zh"] == "小雨"

    @pytest.mark.asyncio
    async def test_days_clamped(self):
        _cache_set(
            "all:31.23:121.47:7",
            {
                "current": {},
                "daily": [],
                "hourly": [],
            },
        )
        result = await get_forecast(31.23, 121.47, 10)
        # days clamped to 7, so cache key uses 7 / days 上限为 7，缓存键按 7 计算
        assert result == []
