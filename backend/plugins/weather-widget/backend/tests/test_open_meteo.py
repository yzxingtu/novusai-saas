"""Weather provider compatibility tests."""

from __future__ import annotations

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

configure = mod.configure
search_city = mod.search_city
reverse_geocode = mod.reverse_geocode
get_current_weather = mod.get_current_weather
get_forecast = mod.get_forecast
get_weather_all = mod.get_weather_all
get_air_quality = mod.get_air_quality
get_wmo_info = mod.get_wmo_info
_cache = mod._cache
_cache_get = mod._cache_get
_cache_set = mod._cache_set
_expand_city_queries = mod._expand_city_queries
_normalize_city_label = mod._normalize_city_label
_rank_city_candidate = mod._rank_city_candidate
_symbol_to_weather = mod._symbol_to_weather


def _configure_test_provider() -> None:
    configure({"cache_ttl": 600})


class TestWmoCodeMapping:
    def test_clear_sky(self):
        info = get_wmo_info(0)
        assert info["icon"] == "sun"
        assert info["zh"] == "晴"

    def test_unknown_code(self):
        info = get_wmo_info(999)
        assert info["icon"] == "cloud"
        assert info["zh"] == "未知"

    def test_describe_exception_uses_repr_for_blank_connect_error(self):
        summary = mod._describe_exception(httpx.ConnectError(""))
        assert "ConnectError" in summary

    def test_symbol_maps_to_expected_weather(self):
        condition = _symbol_to_weather("lightrainshowers_day")
        assert condition["wmo"] == 80
        assert condition["zh"] == "小阵雨"


class TestCache:
    def setup_method(self):
        _cache.clear()
        _configure_test_provider()

    def test_cache_set_and_get(self):
        _cache_set("test_key", {"temp": 22})
        result = _cache_get("test_key")
        assert result == {"temp": 22}

    def test_cache_miss(self):
        assert _cache_get("missing") is None

    def test_cache_expired(self):
        _cache["expired"] = (time.time() - 700, {"temp": 20})
        assert _cache_get("expired") is None

    def test_cache_eviction(self):
        for idx in range(210):
            _cache_set(f"key_{idx}", idx)
        assert len(_cache) <= 200


class TestSearchCity:
    def setup_method(self):
        _cache.clear()
        _configure_test_provider()

    @pytest.mark.asyncio
    async def test_empty_name(self):
        assert await search_city("") == []

    @pytest.mark.asyncio
    async def test_whitespace_name(self):
        assert await search_city("   ") == []

    @pytest.mark.asyncio
    async def test_search_cached(self):
        _cache_set("geo:Shanghai:5", [{"name": "Shanghai", "latitude": 31.23, "longitude": 121.47}])
        result = await search_city("Shanghai")
        assert len(result) == 1
        assert result[0]["name"] == "Shanghai"

    @pytest.mark.asyncio
    async def test_search_success(self):
        with patch.object(
            mod,
            "_search_city_nominatim",
            new=AsyncMock(
                return_value=[
                    {
                        "name": "Shanghai",
                        "country": "China",
                        "admin1": "Shanghai",
                        "latitude": 31.23,
                        "longitude": 121.47,
                    }
                ]
            ),
        ):
            result = await search_city("Shanghai", count=1)

        assert len(result) == 1
        assert result[0]["name"] == "Shanghai"
        assert result[0]["latitude"] == 31.23

    @pytest.mark.asyncio
    async def test_search_city_retries_trimmed_county_variant(self):
        search_mock = AsyncMock(
            side_effect=[
                [],
                [
                    {
                        "name": "凤凰",
                        "country": "China",
                        "admin1": "湖南",
                        "latitude": 27.9483,
                        "longitude": 109.5996,
                    }
                ],
            ]
        )
        with patch.object(mod, "_search_city_nominatim", new=search_mock):
            result = await search_city("凤凰县", count=1)

        assert len(result) == 1
        assert result[0]["name"] == "凤凰"
        assert search_mock.await_args_list[0].args[:2] == ("凤凰县", 1)
        assert search_mock.await_args_list[1].args[:2] == ("凤凰", 1)

    def test_expand_city_queries_adds_common_beijing_aliases(self):
        expanded = _expand_city_queries("北京")
        assert expanded[0] == "北京"
        assert "北京市" in expanded
        assert "Beijing" in expanded

    def test_expand_city_queries_adds_county_fallback_variant(self):
        expanded = _expand_city_queries("凤凰县")
        assert expanded[0] == "凤凰县"
        assert "凤凰" in expanded

    def test_normalize_city_label_trims_county_suffix(self):
        assert _normalize_city_label("凤凰县") == "凤凰"

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

    @pytest.mark.asyncio
    async def test_reverse_geocode_uses_nominatim_result(self):
        with patch.object(
            mod,
            "_reverse_nominatim",
            new=AsyncMock(
                return_value={
                    "name": "上海",
                    "country": "中国",
                    "admin1": "上海",
                    "latitude": 31.23,
                    "longitude": 121.47,
                }
            ),
        ) as reverse_mock:
            result = await reverse_geocode(31.23, 121.47)

        assert result is not None
        assert result["name"] == "上海"
        assert reverse_mock.await_count == 1


class TestWeatherAggregation:
    def setup_method(self):
        _cache.clear()
        _configure_test_provider()

    @pytest.mark.asyncio
    async def test_get_weather_all_success(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "properties": {
                "timeseries": [
                    {
                        "time": "2026-02-23T02:00:00Z",
                        "data": {
                            "instant": {
                                "details": {
                                    "air_temperature": 22.5,
                                    "relative_humidity": 68,
                                    "wind_speed": 4.2,
                                }
                            },
                            "next_1_hours": {"summary": {"symbol_code": "clearsky_day"}},
                        },
                    },
                    {
                        "time": "2026-02-23T03:00:00Z",
                        "data": {
                            "instant": {
                                "details": {
                                    "air_temperature": 23.0,
                                    "relative_humidity": 66,
                                    "wind_speed": 4.0,
                                }
                            },
                            "next_1_hours": {"summary": {"symbol_code": "partlycloudy_day"}},
                        },
                    },
                    {
                        "time": "2026-02-23T04:00:00Z",
                        "data": {
                            "instant": {
                                "details": {
                                    "air_temperature": 24.0,
                                    "relative_humidity": 60,
                                    "wind_speed": 5.0,
                                }
                            },
                            "next_1_hours": {"summary": {"symbol_code": "lightrainshowers_day"}},
                        },
                    },
                    {
                        "time": "2026-02-24T02:00:00Z",
                        "data": {
                            "instant": {
                                "details": {
                                    "air_temperature": 18.0,
                                    "relative_humidity": 70,
                                    "wind_speed": 3.0,
                                }
                            },
                            "next_1_hours": {"summary": {"symbol_code": "cloudy"}},
                        },
                    },
                ]
            }
        }

        mock_instance = AsyncMock()
        mock_instance.get.return_value = mock_resp

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await get_weather_all(31.23, 121.47, 2)

        assert result["current"]["temperature"] == 22.5
        assert result["current"]["weather_code"] == 0
        assert result["current"]["weather_text_en"] == "Clear sky"
        assert result["current"]["uv_index"] is None
        assert result["current"]["is_day"] is True
        assert len(result["daily"]) == 2
        assert result["daily"][0]["temp_max"] == 24.0
        assert result["daily"][1]["weather_code"] == 3
        assert len(result["hourly"]) == 4
        assert result["hourly"][0]["is_current"] is True

    @pytest.mark.asyncio
    async def test_get_current_weather_wraps_aggregate_payload(self):
        with patch.object(
            mod,
            "get_weather_all",
            new=AsyncMock(return_value={"current": {"temperature": 20.0}}),
        ):
            result = await get_current_weather(31.23, 121.47)

        assert result == {"temperature": 20.0}

    @pytest.mark.asyncio
    async def test_get_forecast_wraps_aggregate_payload(self):
        with patch.object(
            mod,
            "get_weather_all",
            new=AsyncMock(return_value={"daily": [{"date": "2026-02-23"}]}),
        ):
            result = await get_forecast(31.23, 121.47, 1)

        assert result == [{"date": "2026-02-23"}]


class TestAirQuality:
    def setup_method(self):
        _cache.clear()
        _configure_test_provider()

    @pytest.mark.asyncio
    async def test_get_air_quality_returns_empty_shape(self):
        result = await get_air_quality(31.23, 121.47)
        assert result == {
            "aqi": None,
            "pm2_5": None,
            "pm10": None,
            "european_aqi": None,
        }
